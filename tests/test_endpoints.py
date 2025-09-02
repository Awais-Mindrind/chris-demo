"""Unit tests for API endpoints."""
import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint."""
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/healthz")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "timestamp" in data


class TestChatEndpoints:
    """Test chat endpoints."""
    
    def test_chat_endpoint_success(self, client):
        """Test successful streaming chat endpoint."""
        async def mock_stream():
            yield {"type": "token", "content": "Hello! I can help you create a quote.", "partial": "Hello! I can help you create a quote."}
            yield {"type": "done", "response": "Hello! I can help you create a quote.", "session_id": "test_session"}
        
        with patch('app.main.process_message_stream') as mock_process_stream:
            mock_process_stream.return_value = mock_stream()
            
            response = client.post("/chat", json={
                "message": "Hello",
                "session_id": "test_session"
            })
            
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
    
    def test_chat_endpoint_generates_session_id(self, client):
        """Test chat endpoint generates session ID when not provided."""
        async def mock_stream():
            yield {"type": "session", "session_id": "generated_session"}
            yield {"type": "token", "content": "Hello!", "partial": "Hello!"}
            yield {"type": "done", "response": "Hello!", "session_id": "generated_session"}
        
        with patch('app.main.process_message_stream') as mock_process_stream:
            mock_process_stream.return_value = mock_stream()
            
            response = client.post("/chat", json={"message": "Hello"})
            
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
    
    def test_chat_endpoint_error(self, client):
        """Test chat endpoint error handling."""
        async def mock_stream():
            yield {"type": "error", "error": "Processing failed", "message": "Processing failed", "session_id": "test_session"}
        
        with patch('app.main.process_message_stream') as mock_process_stream:
            mock_process_stream.return_value = mock_stream()
            
            response = client.post("/chat", json={"message": "Hello"})
            
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]


class TestCreateQuoteEndpoint:
    """Test quote creation endpoint."""
    
    def test_create_quote_success(self, client):
        """Test successful quote creation."""
        with patch('app.main.create_quote') as mock_create, \
             patch('app.main.generate_quote_pdf') as mock_pdf:
            mock_quote = Mock()
            mock_quote.id = 123
            mock_quote.status = "draft"
            mock_create.return_value = mock_quote
            
            response = client.post("/actions/create_quote", json={
                "account_id": 1,
                "pricebook_id": 1,
                "lines": [
                    {"sku_id": 1, "qty": 2, "discount_pct": 0.1}
                ],
                "idempotency_key": "test_key_123"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["quote_id"] == 123
            assert data["status"] == "draft"
            assert "created successfully" in data["message"]
    
    def test_create_quote_validation_error(self, client):
        """Test quote creation with validation error."""
        with patch('app.main.create_quote') as mock_create:
            mock_create.side_effect = ValueError("Invalid data")
            
            response = client.post("/actions/create_quote", json={
                "account_id": 1,
                "pricebook_id": 1,
                "lines": []
            })
            
            assert response.status_code == 400
            data = response.json()
            assert "Validation error" in data["detail"]
    
    def test_create_quote_without_idempotency_key(self, client):
        """Test quote creation without idempotency key."""
        with patch('app.main.create_quote') as mock_create, \
             patch('app.main.generate_quote_pdf') as mock_pdf:
            mock_quote = Mock()
            mock_quote.id = 456
            mock_quote.status = "draft"
            mock_create.return_value = mock_quote
            
            response = client.post("/actions/create_quote", json={
                "account_id": 1,
                "pricebook_id": 1,
                "lines": [{"sku_id": 1, "qty": 1}]
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["quote_id"] == 456


class TestGetQuoteEndpoint:
    """Test quote retrieval endpoint."""
    
    def test_get_quote_success(self, client):
        """Test successful quote retrieval."""
        with patch('app.main.get_quote') as mock_get:
            mock_quote = Mock()
            mock_quote.id = 123
            mock_quote.account_id = 1
            mock_quote.pricebook_id = 1
            mock_quote.status = "draft"
            mock_quote.created_at = "2024-01-01T00:00:00"
            
            mock_line = Mock()
            mock_line.id = 1
            mock_line.sku_id = 1
            mock_line.qty = 2
            mock_line.unit_price = 100.0
            mock_line.discount_pct = 0.1
            
            mock_quote.lines = [mock_line]
            mock_get.return_value = mock_quote
            
            response = client.get("/quotes/123")
            
            assert response.status_code == 200
            data = response.json()
            assert data["quote_id"] == 123
            assert data["account_id"] == 1
            assert data["pricebook_id"] == 1
            assert data["status"] == "draft"
            assert len(data["lines"]) == 1
            assert data["total_amount"] > 0
    
    def test_get_quote_not_found(self, client):
        """Test quote retrieval for non-existent quote."""
        with patch('app.main.get_quote') as mock_get:
            mock_get.return_value = None
            
            response = client.get("/quotes/999")
            
            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["detail"]


class TestGetQuotePDFEndpoint:
    """Test PDF generation endpoint."""
    
    def test_get_quote_pdf_success(self, client):
        """Test successful PDF generation."""
        with patch('app.main.get_quote') as mock_get, \
             patch('app.main.generate_quote_pdf') as mock_generate:
            
            mock_quote = Mock()
            mock_quote.id = 123
            mock_get.return_value = mock_quote
            
            # Use the path that the PDF function actually generates
            mock_generate.return_value = "public/quote_123.pdf"
            
            response = client.get("/quotes/123/pdf")
            
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/pdf"
            assert "quote_123.pdf" in response.headers["content-disposition"]
    
    def test_get_quote_pdf_not_found(self, client):
        """Test PDF generation for non-existent quote."""
        with patch('app.main.get_quote') as mock_get:
            mock_get.return_value = None
            
            response = client.get("/quotes/999/pdf")
            
            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["detail"]


class TestSessionEndpoints:
    """Test session management endpoints."""
    
    def test_get_session_history(self, client):
        """Test getting session history."""
        with patch('app.main.get_conversation_history') as mock_get:
            mock_get.return_value = [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"}
            ]
            
            response = client.get("/sessions/test_session/history")
            
            assert response.status_code == 200
            data = response.json()
            assert data["session_id"] == "test_session"
            assert len(data["history"]) == 2
    
    def test_clear_session(self, client):
        """Test clearing session."""
        with patch('app.main.clear_conversation') as mock_clear:
            mock_clear.return_value = True
            
            response = client.delete("/sessions/test_session")
            
            assert response.status_code == 200
            data = response.json()
            assert data["session_id"] == "test_session"
            assert data["cleared"] is True


class TestStatsEndpoint:
    """Test statistics endpoint."""
    
    def test_get_stats(self, client):
        """Test getting application statistics."""
        with patch('app.main.get_session_stats') as mock_get:
            mock_get.return_value = {
                "active_sessions": 5,
                "max_sessions": 100,
                "cleanup_threshold": 100
            }
            
            response = client.get("/stats")
            
            assert response.status_code == 200
            data = response.json()
            assert "sessions" in data
            assert "timestamp" in data
            assert data["sessions"]["active_sessions"] == 5




