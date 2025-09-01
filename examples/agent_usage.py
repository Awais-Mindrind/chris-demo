#!/usr/bin/env python3
"""Example usage of the LangChain agent."""
import os
from app.agent import (
    create_agent, get_agent_for_session, process_message,
    get_conversation_history, clear_conversation, get_session_stats
)


def demonstrate_agent_creation():
    """Demonstrate agent creation and configuration."""
    print("=== Agent Creation Demo ===\n")
    
    try:
        # Create a simple agent (without session memory)
        print("Creating simple agent...")
        agent = create_agent()
        print("✅ Agent created successfully!")
        print(f"Agent type: {type(agent).__name__}")
        print(f"Has memory: {agent.memory is not None}")
        
        # Create an agent with session memory
        print("\nCreating agent with session memory...")
        session_agent = get_agent_for_session("demo_session_123")
        print("✅ Session agent created successfully!")
        print(f"Has memory: {session_agent.memory is not None}")
        
    except Exception as e:
        print(f"❌ Error creating agent: {str(e)}")
        print("Make sure GOOGLE_API_KEY is set in your .env file")


def demonstrate_session_management():
    """Demonstrate session management functionality."""
    print("\n=== Session Management Demo ===\n")
    
    # Get session statistics
    stats = get_session_stats()
    print(f"Active sessions: {stats['active_sessions']}")
    print(f"Max sessions: {stats['max_sessions']}")
    print(f"Cleanup threshold: {stats['cleanup_threshold']}")
    
    # Create a new session
    session_id = "demo_session_456"
    print(f"\nCreating session: {session_id}")
    
    try:
        agent = get_agent_for_session(session_id)
        print("✅ Session created successfully")
        
        # Get conversation history (should be empty initially)
        history = get_conversation_history(session_id)
        print(f"Initial conversation history: {len(history)} messages")
        
        # Clear the session
        print(f"\nClearing session: {session_id}")
        cleared = clear_conversation(session_id)
        print(f"Session cleared: {cleared}")
        
    except Exception as e:
        print(f"❌ Error with session management: {str(e)}")


def demonstrate_message_processing():
    """Demonstrate message processing with the agent."""
    print("\n=== Message Processing Demo ===\n")
    
    session_id = "demo_message_session"
    
    try:
        # Process a simple message
        print("Processing message: 'Hello, can you help me create a quote?'")
        response = process_message(session_id, "Hello, can you help me create a quote?")
        print(f"Agent response: {response}")
        
        # Get conversation history
        history = get_conversation_history(session_id)
        print(f"\nConversation history: {len(history)} messages")
        
        for i, msg in enumerate(history):
            print(f"  {i+1}. {msg['role']}: {msg['content'][:100]}...")
        
    except Exception as e:
        print(f"❌ Error processing message: {str(e)}")


def demonstrate_agent_workflow():
    """Demonstrate a complete agent workflow."""
    print("\n=== Complete Agent Workflow Demo ===\n")
    
    session_id = "demo_workflow_session"
    
    try:
        print("1. Creating agent for workflow...")
        agent = get_agent_for_session(session_id)
        print("✅ Agent created")
        
        print("\n2. Processing initial request...")
        response1 = process_message(session_id, "I need to create a quote for Acme Corporation")
        print(f"Response: {response1[:200]}...")
        
        print("\n3. Processing follow-up...")
        response2 = process_message(session_id, "What products do you have available?")
        print(f"Response: {response2[:200]}...")
        
        print("\n4. Getting conversation summary...")
        history = get_conversation_history(session_id)
        print(f"Total messages in conversation: {len(history)}")
        
        print("\n5. Cleaning up...")
        clear_conversation(session_id)
        print("✅ Session cleared")
        
    except Exception as e:
        print(f"❌ Error in workflow demo: {str(e)}")


def demonstrate_error_handling():
    """Demonstrate error handling in the agent."""
    print("\n=== Error Handling Demo ===\n")
    
    try:
        # Try to create agent without API key (this should fail gracefully)
        print("Testing error handling...")
        
        # This would normally fail without proper API key
        print("Note: Error handling is demonstrated in the test suite")
        print("The agent includes comprehensive error handling for:")
        print("- Missing API keys")
        print("- Tool execution errors")
        print("- Database connection issues")
        print("- Invalid user inputs")
        
    except Exception as e:
        print(f"Expected error caught: {str(e)}")


def main():
    """Main function to run examples."""
    print("LangChain Agent Examples for Sales Quoting Engine")
    print("=" * 60)
    
    # Check if API key is available
    if not os.getenv("GOOGLE_API_KEY"):
        print("⚠️  GOOGLE_API_KEY not found in environment")
        print("Please set it in your .env file to run these examples")
        print("\nExample .env content:")
        print("GOOGLE_API_KEY=your_actual_api_key_here")
        print("APP_ENV=development")
        print("DB_URL=sqlite:///./dev.db")
        print("LOG_LEVEL=INFO")
        return
    
    print("✅ GOOGLE_API_KEY found, proceeding with examples\n")
    
    # Run demonstrations
    demonstrate_agent_creation()
    demonstrate_session_management()
    demonstrate_message_processing()
    demonstrate_agent_workflow()
    demonstrate_error_handling()
    
    print("\n=== Implementation Notes ===\n")
    print("The agent is designed to:")
    print("- Use all available tools (find_account, list_pricebooks, etc.)")
    print("- Maintain conversation context per session")
    print("- Handle errors gracefully")
    print("- Follow the exact system prompt from project rules")
    print("- Integrate seamlessly with the CRUD operations")
    
    print("\nTo use in production:")
    print("1. Set GOOGLE_API_KEY in environment")
    print("2. Initialize database with migrations")
    print("3. Use get_agent_for_session() for user conversations")
    print("4. Monitor session usage and cleanup as needed")


if __name__ == "__main__":
    main()
