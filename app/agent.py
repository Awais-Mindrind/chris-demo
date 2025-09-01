"""LangChain agent configuration and system prompt."""
from typing import Dict, List, Optional, Any, AsyncGenerator
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain.memory import ConversationBufferMemory
from sqlalchemy.orm import Session
from app.config import settings
from app.crud import get_chat_session, create_chat_session, add_chat_message, get_chat_history_for_langchain
import logging
import asyncio
import json

logger = logging.getLogger(__name__)


class PersistentSessionStore:
    """Database-backed session store for persistent conversation history."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_session(self, session_id: str) -> ConversationBufferMemory:
        """Get or create a session for the given session_id."""
        # Ensure session exists in database
        session = get_chat_session(self.db, session_id)
        if not session:
            session = create_chat_session(self.db, session_id)
            logger.info(f"Created new persistent session: {session_id}")
        
        # Create LangChain memory with existing history
        memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        
        # Load existing messages from database
        history = get_chat_history_for_langchain(self.db, session_id, limit=20)
        for msg in history:
            if msg["role"] == "user":
                memory.chat_memory.add_user_message(msg["content"])
            elif msg["role"] == "assistant":
                memory.chat_memory.add_ai_message(msg["content"])
            elif msg["role"] == "system":
                memory.chat_memory.add_message(SystemMessage(content=msg["content"]))
        
        logger.info(f"Loaded {len(history)} messages for session: {session_id}")
        return memory
    
    def save_message(self, session_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Save a message to the database."""
        try:
            add_chat_message(self.db, session_id, role, content, metadata)
            logger.debug(f"Saved {role} message for session: {session_id}")
        except Exception as e:
            logger.error(f"Failed to save message for session {session_id}: {str(e)}")
    
    def clear_session(self, session_id: str) -> bool:
        """Clear a session's memory from database."""
        try:
            from app.crud import clear_chat_session
            result = clear_chat_session(self.db, session_id)
            logger.info(f"Cleared persistent session: {session_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to clear session {session_id}: {str(e)}")
            return False


# Global session store instance (will be replaced with database-backed version)
session_store = None


def create_llm() -> ChatGoogleGenerativeAI:
    """Create and configure the Google GenAI LLM."""
    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY must be set in environment variables")
    
    return ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        temperature=0.3,  # As specified in project rules (0.2-0.4)
        google_api_key=settings.google_api_key,
        convert_system_message_to_human=True,  # Gemini works better with human messages
        verbose=True
    )


def create_streaming_llm() -> ChatGoogleGenerativeAI:
    """Create and configure the Google GenAI LLM with streaming support."""
    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY must be set in environment variables")
    
    return ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        temperature=0.3,
        google_api_key=settings.google_api_key,
        convert_system_message_to_human=True,
        streaming=True,  # Enable streaming
        verbose=True
    )


def create_system_prompt() -> str:
    """Create the system prompt as specified in project rules."""
    return """You are a quoting assistant. Ask the minimum clarifying questions. 
Never invent IDs or prices. Use tools for all data reads/writes. 
If multiple accounts match, ask the user to choose. 
When ready, create the quote, render a PDF, and ask for review.

Key Guidelines:
1. Always use tools for database operations - never invent data
2. Ask clarifying questions only when necessary
3. For account searches with multiple matches, ask user to choose if confidence < 0.9
4. Validate all inputs before creating quotes
5. After creating a quote, verify it with get_quote tool
6. Generate PDF and provide download link
7. Ask user to review and confirm the quote
8. Be proactive - if you have enough information, proceed with quote creation
9. Use default pricebook if not specified
10. Search for SKUs by name if exact code not provided

IMPORTANT - SKU and Pricebook Relationships:
- SKUs can exist in multiple pricebooks with different IDs
- When listing SKUs, pay attention to the pricebook_id and currency
- When creating quotes, ensure SKUs exist in the specified pricebook
- If a SKU doesn't exist in the target pricebook, suggest the correct pricebook
- Default to USD pricebook (Standard) when currency is not specified
- When multiple SKUs match, show them grouped by pricebook/currency

SKU Selection Strategy:
- If user says "Widget" → default to USD pricebook (Standard)
- If user says "Widget EUR" → use EUR pricebook (European)
- If user specifies SKU ID → verify it exists in the target pricebook
- If SKU not found in pricebook → suggest alternative pricebook or SKU

Available Tools:
- find_account: Search for accounts by name or domain
- list_pricebooks: Get available pricebooks
- list_skus: Search for products/SKUs (now includes pricebook context)
- create_quote: Create new quote with line items (validates SKU-pricebook matches)
- get_quote: Retrieve quote details
- render_quote_pdf: Generate PDF for quote

Remember: Be helpful, efficient, and always use the appropriate tools. If you have enough information to create a quote, do so automatically. Pay special attention to SKU-pricebook relationships to avoid validation errors."""


def create_agent_prompt() -> ChatPromptTemplate:
    """Create the agent prompt template."""
    return ChatPromptTemplate.from_messages([
        ("system", create_system_prompt()),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])


def create_agent_with_db(db: Session) -> AgentExecutor:
    """Create a LangChain agent with tools that have database session."""
    from app.tools import create_tools_with_db
    
    print(f"DEBUG: Creating agent with database session: {db}")
    llm = create_llm()
    tools = create_tools_with_db(db)
    print(f"DEBUG: Created {len(tools)} tools")
    for tool in tools:
        print(f"DEBUG: Tool: {tool.name} - {tool.description}")
    
    prompt = create_agent_prompt()
    
    agent = create_openai_tools_agent(llm, tools, prompt)
    
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=10
    )


def create_streaming_agent_with_db(db: Session) -> AgentExecutor:
    """Create a LangChain agent with streaming support and database session."""
    from app.tools import create_tools_with_db
    
    llm = create_streaming_llm()
    tools = create_tools_with_db(db)
    prompt = create_agent_prompt()
    
    agent = create_openai_tools_agent(llm, tools, prompt)
    
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=10
    )


def get_agent_for_session(session_id: str, db: Session) -> AgentExecutor:
    """Get or create an agent for a specific session with memory and database session."""
    # Create persistent session store with database
    persistent_store = PersistentSessionStore(db)
    
    # Create agent with memory and database session
    agent = create_agent_with_db(db)
    
    # Add memory to the agent
    memory = persistent_store.get_session(session_id)
    agent.memory = memory
    
    return agent


def get_streaming_agent_for_session(session_id: str, db: Session) -> AgentExecutor:
    """Get or create a streaming agent for a specific session with memory and database session."""
    # Create persistent session store with database
    persistent_store = PersistentSessionStore(db)
    
    # Create streaming agent with memory and database session
    agent = create_streaming_agent_with_db(db)
    
    # Add memory to the agent
    memory = persistent_store.get_session(session_id)
    agent.memory = memory
    
    return agent


def process_message(session_id: str, message: str, db: Session) -> str:
    """Process a user message with the agent.
    
    Args:
        session_id: Session identifier for conversation memory
        message: User's message
        db: Database session
        
    Returns:
        Agent's response
    """
    try:
        # Create persistent session store
        persistent_store = PersistentSessionStore(db)
        
        # Save user message to database
        persistent_store.save_message(session_id, "user", message)
        
        # Get or create agent for this session with database session
        agent = get_agent_for_session(session_id, db)
        
        # Process the message
        response = agent.invoke({
            "input": message,
            "chat_history": agent.memory.chat_memory.messages if agent.memory else []
        })
        
        # Save assistant response to database
        response_text = response.get("output", "I apologize, but I encountered an error processing your request.")
        persistent_store.save_message(session_id, "assistant", response_text)
        
        logger.info(f"Processed message for session {session_id}")
        return response_text
        
    except Exception as e:
        logger.error(f"Error processing message for session {session_id}: {str(e)}")
        error_msg = f"I apologize, but I encountered an error: {str(e)}"
        
        # Save error message to database
        try:
            persistent_store = PersistentSessionStore(db)
            persistent_store.save_message(session_id, "assistant", error_msg, {"error": True})
        except Exception:
            pass
        
        return error_msg


async def process_message_stream(session_id: str, message: str, db: Session) -> AsyncGenerator[Dict[str, Any], None]:
    """Process a user message with the agent and stream the response.
    
    Args:
        session_id: Session identifier for conversation memory
        message: User's message
        db: Database session
        
    Yields:
        Dictionary with streaming data
    """
    try:
        # Create persistent session store
        persistent_store = PersistentSessionStore(db)
        
        # Save user message to database
        persistent_store.save_message(session_id, "user", message)
        
        # Get or create streaming agent for this session with database session
        agent = get_streaming_agent_for_session(session_id, db)
        
        # Process the message with streaming
        response_stream = agent.astream({
            "input": message,
            "chat_history": agent.memory.chat_memory.messages if agent.memory else []
        })
        
        full_response = ""
        pdf_url = None
        
        async for chunk in response_stream:
            if "output" in chunk:
                output = chunk["output"]
                if isinstance(output, str):
                    # Stream the output token by token
                    if not full_response:
                        full_response = output
                    else:
                        full_response += output
                    
                    # Yield each token
                    yield {
                        "type": "token",
                        "content": output,
                        "partial": full_response
                    }
                else:
                    # Handle non-string outputs (like tool calls)
                    full_response += str(output)
                    yield {
                        "type": "token",
                        "content": str(output),
                        "partial": full_response
                    }
            
            # Check if any tools were called that might generate a PDF
            if "intermediate_steps" in chunk:
                for step in chunk["intermediate_steps"]:
                    if len(step) >= 2:
                        tool_name = step[0].tool if hasattr(step[0], 'tool') else str(step[0])
                        tool_result = step[1]
                        
                        # Check if create_quote was called
                        if "create_quote" in str(tool_name).lower():
                            try:
                                # Extract quote ID from result
                                if isinstance(tool_result, dict) and "quote_id" in tool_result:
                                    quote_id = tool_result["quote_id"]
                                    pdf_url = f"/quotes/{quote_id}/pdf"
                                    yield {
                                        "type": "pdf_ready",
                                        "pdf_url": pdf_url,
                                        "quote_id": quote_id
                                    }
                            except Exception as e:
                                logger.error(f"Error extracting PDF URL: {str(e)}")
        
        # Save assistant response to database
        persistent_store.save_message(session_id, "assistant", full_response)
        
        # Send completion event
        yield {
            "type": "done",
            "response": full_response,
            "session_id": session_id,
            "pdf_url": pdf_url
        }
        
        logger.info(f"Streamed message for session {session_id}")
        
    except Exception as e:
        logger.error(f"Error streaming message for session {session_id}: {str(e)}")
        error_msg = f"I apologize, but I encountered an error: {str(e)}"
        
        # Save error message to database
        try:
            persistent_store = PersistentSessionStore(db)
            persistent_store.save_message(session_id, "assistant", error_msg, {"error": True})
        except Exception:
            pass
        
        yield {
            "type": "error",
            "error": "Processing failed",
            "message": str(e),
            "session_id": session_id
        }


def get_conversation_history(session_id: str) -> List[Dict[str, str]]:
    """Get conversation history for a session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        List of conversation messages with role and content
    """
    try:
        memory = session_store.get_session(session_id)
        messages = memory.chat_memory.messages
        
        history = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                history.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                history.append({"role": "assistant", "content": msg.content})
            elif isinstance(msg, SystemMessage):
                history.append({"role": "system", "content": msg.content})
        
        return history
        
    except Exception as e:
        logger.error(f"Error getting conversation history for session {session_id}: {str(e)}")
        return []


def clear_conversation(session_id: str) -> bool:
    """Clear conversation history for a session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        True if session was cleared, False if not found
    """
    return session_store.clear_session(session_id)


def get_session_stats() -> Dict[str, Any]:
    """Get statistics about active sessions.
    
    Returns:
        Dictionary with session statistics
    """
    return {
        "active_sessions": session_store.get_session_count(),
        "max_sessions": 100,  # Current limit
        "cleanup_threshold": 100
    }


def cleanup_sessions():
    """Clean up old sessions if needed."""
    session_store.cleanup_old_sessions()


# Convenience function for backward compatibility
def create_agent_simple() -> AgentExecutor:
    """Create a simple agent without session memory (for testing)."""
    return create_agent()


# Export main functions
__all__ = [
    "create_agent",
    "get_agent_for_session", 
    "process_message",
    "process_message_stream",
    "get_conversation_history",
    "clear_conversation",
    "get_session_stats",
    "cleanup_sessions"
]
