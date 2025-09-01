"""Unit tests for LangChain agent functionality."""
import pytest
from unittest.mock import Mock, patch, MagicMock
import os

from app.agent import (
    create_llm, create_system_prompt, create_agent_prompt,
    SessionStore, get_agent_for_session, process_message,
    get_conversation_history, clear_conversation, get_session_stats
)


class TestAgentConfiguration:
    """Test agent configuration and setup."""
    
    def test_create_system_prompt(self):
        """Test system prompt creation."""
        prompt = create_system_prompt()
        
        # Check that key elements are present
        assert "quoting assistant" in prompt.lower()
        assert "never invent ids or prices" in prompt.lower()
        assert "use tools for all data reads/writes" in prompt.lower()
        assert "find_account" in prompt
        assert "create_quote" in prompt
        assert "render_quote_pdf" in prompt
    
    def test_create_agent_prompt(self):
        """Test agent prompt template creation."""
        prompt = create_agent_prompt()
        
        # Check that it's a ChatPromptTemplate
        from langchain_core.prompts import ChatPromptTemplate
        assert isinstance(prompt, ChatPromptTemplate)
        
        # Check that it has the expected variables
        variables = prompt.input_variables
        assert "input" in variables
        assert "chat_history" in variables
        assert "agent_scratchpad" in variables
    
    @patch.dict(os.environ, {'GOOGLE_API_KEY': 'test_key'})
    @patch('app.agent.settings')
    def test_create_llm_success(self, mock_settings):
        """Test successful LLM creation."""
        mock_settings.google_api_key = "test_key"
        
        llm = create_llm()
        
        from langchain_google_genai import ChatGoogleGenerativeAI
        assert isinstance(llm, ChatGoogleGenerativeAI)
        assert llm.temperature == 0.3
        # The actual model name includes 'models/' prefix
        assert "gemini-1.5-flash" in llm.model
    
    @patch('app.agent.settings')
    def test_create_llm_missing_api_key(self, mock_settings):
        """Test LLM creation with missing API key."""
        mock_settings.google_api_key = None
        
        with pytest.raises(ValueError, match="GOOGLE_API_KEY must be set"):
            create_llm()


class TestSessionStore:
    """Test session store functionality."""
    
    def test_session_store_initialization(self):
        """Test session store initialization."""
        store = SessionStore()
        assert store._sessions == {}
    
    def test_get_session_new(self):
        """Test getting a new session."""
        store = SessionStore()
        session = store.get_session("test_session")
        
        assert "test_session" in store._sessions
        assert store._sessions["test_session"] == session
        
        from langchain.memory import ConversationBufferMemory
        assert isinstance(session, ConversationBufferMemory)
    
    def test_get_session_existing(self):
        """Test getting an existing session."""
        store = SessionStore()
        session1 = store.get_session("test_session")
        session2 = store.get_session("test_session")
        
        assert session1 is session2  # Same object reference
        assert len(store._sessions) == 1
    
    def test_clear_session_existing(self):
        """Test clearing an existing session."""
        store = SessionStore()
        store.get_session("test_session")
        
        assert "test_session" in store._sessions
        result = store.clear_session("test_session")
        
        assert result is True
        assert "test_session" not in store._sessions
    
    def test_clear_session_non_existing(self):
        """Test clearing a non-existing session."""
        store = SessionStore()
        result = store.clear_session("non_existing")
        
        assert result is False
    
    def test_get_session_count(self):
        """Test getting session count."""
        store = SessionStore()
        assert store.get_session_count() == 0
        
        store.get_session("session1")
        assert store.get_session_count() == 1
        
        store.get_session("session2")
        assert store.get_session_count() == 2
    
    def test_cleanup_old_sessions(self):
        """Test cleanup of old sessions."""
        store = SessionStore()
        
        # Create more than max_sessions
        for i in range(105):
            store.get_session(f"session_{i}")
        
        assert store.get_session_count() == 105
        
        # Cleanup should reduce to max_sessions
        store.cleanup_old_sessions(max_sessions=100)
        assert store.get_session_count() == 100


class TestAgentFunctions:
    """Test agent function implementations."""
    
    @patch('app.agent.create_agent')
    def test_get_agent_for_session(self, mock_create_agent):
        """Test getting agent for session."""
        mock_agent = Mock()
        mock_create_agent.return_value = mock_agent
        
        result = get_agent_for_session("test_session")
        
        assert result == mock_agent
        mock_create_agent.assert_called_once()
    
    @patch('app.agent.get_agent_for_session')
    def test_process_message_success(self, mock_get_agent):
        """Test successful message processing."""
        mock_agent = Mock()
        mock_agent.memory.chat_memory.messages = []
        mock_agent.invoke.return_value = {"output": "Test response"}
        mock_get_agent.return_value = mock_agent
        
        result = process_message("test_session", "Hello")
        
        assert result == "Test response"
        mock_agent.invoke.assert_called_once()
    
    @patch('app.agent.get_agent_for_session')
    def test_process_message_error(self, mock_get_agent):
        """Test message processing with error."""
        mock_get_agent.side_effect = Exception("Test error")
        
        result = process_message("test_session", "Hello")
        
        assert "I apologize, but I encountered an error" in result
        assert "Test error" in result
    
    @patch('app.agent.session_store')
    def test_get_conversation_history(self, mock_session_store):
        """Test getting conversation history."""
        from langchain_core.messages import HumanMessage, AIMessage
        
        mock_memory = Mock()
        mock_memory.chat_memory.messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!")
        ]
        mock_session_store.get_session.return_value = mock_memory
        
        history = get_conversation_history("test_session")
        
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello"
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == "Hi there!"
    
    @patch('app.agent.session_store')
    def test_clear_conversation(self, mock_session_store):
        """Test clearing conversation."""
        mock_session_store.clear_session.return_value = True
        
        result = clear_conversation("test_session")
        
        assert result is True
        mock_session_store.clear_session.assert_called_once_with("test_session")
    
    @patch('app.agent.session_store')
    def test_get_session_stats(self, mock_session_store):
        """Test getting session statistics."""
        mock_session_store.get_session_count.return_value = 5
        
        stats = get_session_stats()
        
        assert stats["active_sessions"] == 5
        assert stats["max_sessions"] == 100
        assert stats["cleanup_threshold"] == 100


class TestAgentIntegration:
    """Test agent integration with tools."""
    
    @patch('app.agent.create_llm')
    @patch('app.agent.get_all_tools')
    @patch('app.agent.create_openai_tools_agent')
    @patch('app.agent.AgentExecutor')
    def test_create_agent_success(self, mock_executor, mock_create_agent, mock_get_tools, mock_create_llm):
        """Test successful agent creation."""
        # Mock dependencies
        mock_llm = Mock()
        mock_create_llm.return_value = mock_llm
        
        mock_tools = [Mock(), Mock()]
        mock_get_tools.return_value = mock_tools
        
        mock_agent = Mock()
        mock_create_agent.return_value = mock_agent
        
        mock_executor_instance = Mock()
        mock_executor.return_value = mock_executor_instance
        
        # Test agent creation
        from app.agent import create_agent
        result = create_agent()
        
        assert result == mock_executor_instance
        mock_create_llm.assert_called_once()
        mock_get_tools.assert_called_once()
        # Check that create_openai_tools_agent was called with the right arguments
        mock_create_agent.assert_called_once()
        call_args = mock_create_agent.call_args
        assert call_args[0][0] == mock_llm  # First positional argument is llm
        assert call_args[0][1] == mock_tools  # Second positional argument is tools
        assert call_args[0][2] is not None  # Third positional argument is prompt (ChatPromptTemplate)
        # The prompt will be the actual ChatPromptTemplate, not a mock


class TestAgentErrorHandling:
    """Test agent error handling."""
    
    @patch('app.agent.create_llm')
    def test_create_agent_llm_error(self, mock_create_llm):
        """Test agent creation with LLM error."""
        mock_create_llm.side_effect = Exception("LLM creation failed")
        
        from app.agent import create_agent
        with pytest.raises(Exception, match="LLM creation failed"):
            create_agent()
    
    @patch('app.agent.get_all_tools')
    def test_create_agent_tools_error(self, mock_get_tools):
        """Test agent creation with tools error."""
        mock_get_tools.side_effect = Exception("Tools loading failed")
        
        from app.agent import create_agent
        with pytest.raises(Exception, match="Tools loading failed"):
            create_agent()

