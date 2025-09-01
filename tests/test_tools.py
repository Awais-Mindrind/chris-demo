"""Unit tests for LangChain tools."""
import pytest
from unittest.mock import Mock, patch
from decimal import Decimal

from app.tools import (
    find_account_tool, list_pricebooks_tool, list_skus_tool,
    create_quote_tool, get_quote_tool, render_quote_pdf_tool,
    get_all_tools, get_tool_by_name
)
from app.tools import (
    FindAccountInput, FindAccountOutput, ListPricebooksOutput,
    ListSkusOutput, CreateQuoteInput, CreateQuoteOutput,
    GetQuoteInput, GetQuoteOutput, RenderQuotePdfInput, RenderQuotePdfOutput
)


class TestToolSchemas:
    """Test tool input/output schemas."""
    
    def test_find_account_input(self):
        """Test FindAccountInput schema validation."""
        # Valid input
        valid_input = FindAccountInput(query="test company")
        assert valid_input.query == "test company"
        
        # Empty query should be valid (will be handled by tool logic)
        empty_input = FindAccountInput(query="")
        assert empty_input.query == ""
    
    def test_quote_line_input_validation(self):
        """Test QuoteLineInput validation."""
        from app.tools import QuoteLineInput
        
        # Valid input
        valid_line = QuoteLineInput(sku_id=1, qty=5, discount_pct=0.1)
        assert valid_line.sku_id == 1
        assert valid_line.qty == 5
        assert valid_line.discount_pct == 0.1
        
        # Invalid quantity
        with pytest.raises(ValueError, match="Input should be greater than or equal to 1"):
            QuoteLineInput(sku_id=1, qty=0)
        
        # Invalid discount
        with pytest.raises(ValueError, match="Input should be less than 1"):
            QuoteLineInput(sku_id=1, qty=1, discount_pct=1.5)
        
        with pytest.raises(ValueError, match="Input should be greater than or equal to 0"):
            QuoteLineInput(sku_id=1, qty=1, discount_pct=-0.1)


class TestToolFunctions:
    """Test tool function implementations."""
    
    @patch('app.tools._get_db_session')
    def test_find_account_tool_success(self, mock_get_db):
        """Test successful account search."""
        # Mock database session and search results
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        
        # Mock search_accounts to return test data
        with patch('app.tools.search_accounts') as mock_search:
            # Create proper mock objects with attributes
            mock_account1 = Mock()
            mock_account1.id = 1
            mock_account1.name = "Test Company"
            mock_account1.domain = "test.com"
            
            mock_account2 = Mock()
            mock_account2.id = 2
            mock_account2.name = "Another Test"
            mock_account2.domain = "another.com"
            
            mock_search.return_value = [mock_account1, mock_account2]
            
            result = find_account_tool("test")
            
            assert isinstance(result, FindAccountOutput)
            assert len(result.candidates) == 2
            assert result.total_count == 2
            assert result.candidates[0].name == "Test Company"
            assert result.candidates[0].confidence_score is not None
    
    @patch('app.tools._get_db_session')
    def test_find_account_tool_empty_query(self, mock_get_db):
        """Test account search with empty query."""
        result = find_account_tool("")
        
        assert isinstance(result, FindAccountOutput)
        assert len(result.candidates) == 0
        assert result.total_count == 0
    
    @patch('app.tools._get_db_session')
    def test_list_pricebooks_tool_success(self, mock_get_db):
        """Test successful pricebook listing."""
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        
        with patch('app.tools.get_pricebooks') as mock_get:
            # Create proper mock objects with attributes
            mock_pb1 = Mock()
            mock_pb1.id = 1
            mock_pb1.name = "USD"
            mock_pb1.currency = "USD"
            mock_pb1.is_default = True
            
            mock_pb2 = Mock()
            mock_pb2.id = 2
            mock_pb2.name = "EUR"
            mock_pb2.currency = "EUR"
            mock_pb2.is_default = False
            
            mock_get.return_value = [mock_pb1, mock_pb2]
            
            result = list_pricebooks_tool()
            
            assert isinstance(result, ListPricebooksOutput)
            assert len(result.pricebooks) == 2
            assert result.total_count == 2
            assert result.pricebooks[0]["name"] == "USD"
            assert result.pricebooks[0]["is_default"] is True
    
    @patch('app.tools._get_db_session')
    def test_list_skus_tool_with_filters(self, mock_get_db):
        """Test SKU listing with filters."""
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        
        with patch('app.tools.get_skus') as mock_get:
            mock_sku = Mock()
            mock_sku.id = 1
            mock_sku.code = "TEST-001"
            mock_sku.name = "Test Product"
            mock_sku.pricebook_id = 1
            mock_sku.unit_price = Decimal("99.99")
            
            mock_get.return_value = [mock_sku]
            
            filters = {"name": "test", "pricebook_id": 1}
            result = list_skus_tool(filters)
            
            assert isinstance(result, ListSkusOutput)
            assert len(result.skus) == 1
            assert result.total_count == 1
            assert result.skus[0]["code"] == "TEST-001"
    
    def test_create_quote_tool_validation(self):
        """Test quote creation validation."""
        # Test invalid account ID
        with pytest.raises(ValueError, match="Invalid account ID"):
            create_quote_tool(0, 1, [{"sku_id": 1, "qty": 1}])
        
        # Test invalid pricebook ID
        with pytest.raises(ValueError, match="Invalid pricebook ID"):
            create_quote_tool(1, 0, [{"sku_id": 1, "qty": 1}])
        
        # Test empty lines
        with pytest.raises(ValueError, match="Quote must have at least one line item"):
            create_quote_tool(1, 1, [])
        
        # Test invalid line data
        with pytest.raises(ValueError, match="Each line must have sku_id and qty"):
            create_quote_tool(1, 1, [{"sku_id": 1}])  # Missing qty
        
        # Test invalid quantity
        with pytest.raises(ValueError, match="Quantity must be at least 1"):
            create_quote_tool(1, 1, [{"sku_id": 1, "qty": 0}])
        
        # Test invalid discount
        with pytest.raises(ValueError, match="Discount percentage must be between 0.0 and 1.0"):
            create_quote_tool(1, 1, [{"sku_id": 1, "qty": 1, "discount_pct": 1.5}])
    
    def test_get_quote_tool_validation(self):
        """Test quote retrieval validation."""
        # Test invalid quote ID
        with pytest.raises(ValueError, match="Invalid quote ID"):
            get_quote_tool(0)
    
    def test_render_quote_pdf_tool_validation(self):
        """Test PDF generation validation."""
        # Test invalid quote ID
        with pytest.raises(ValueError, match="Invalid quote ID"):
            render_quote_pdf_tool(0)


class TestToolRegistry:
    """Test tool registry functions."""
    
    def test_get_all_tools(self):
        """Test getting all tools."""
        tools = get_all_tools()
        
        assert len(tools) == 6
        tool_names = [tool.name for tool in tools]
        expected_names = [
            "find_account", "list_pricebooks", "list_skus",
            "create_quote", "get_quote", "render_quote_pdf"
        ]
        
        for name in expected_names:
            assert name in tool_names
    
    def test_get_tool_by_name(self):
        """Test getting tool by name."""
        # Test existing tool
        find_account_tool = get_tool_by_name("find_account")
        assert find_account_tool is not None
        assert find_account_tool.name == "find_account"
        
        # Test non-existing tool
        non_existing = get_tool_by_name("non_existing")
        assert non_existing is None


class TestToolIntegration:
    """Test tool integration with LangChain."""
    
    def test_structured_tool_creation(self):
        """Test that tools are properly created as StructuredTools."""
        from langchain_core.tools import StructuredTool
        
        tools = get_all_tools()
        
        for tool in tools:
            assert isinstance(tool, StructuredTool)
            assert hasattr(tool, 'name')
            assert hasattr(tool, 'description')
            assert hasattr(tool, 'args_schema')
    
    def test_tool_descriptions(self):
        """Test that tools have meaningful descriptions."""
        tools = get_all_tools()
        
        for tool in tools:
            assert tool.description is not None
            assert len(tool.description) > 10  # Should have meaningful description
            # Note: Some descriptions may end with periods, which is fine
    
    def test_tool_names_consistency(self):
        """Test that tool names are consistent with project requirements."""
        tools = get_all_tools()
        tool_names = [tool.name for tool in tools]
        
        # Check that all required tool names are present
        required_tools = [
            "find_account", "list_pricebooks", "list_skus",
            "create_quote", "get_quote", "render_quote_pdf"
        ]
        
        for required in required_tools:
            assert required in tool_names, f"Missing required tool: {required}"

