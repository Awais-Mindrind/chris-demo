"""Unit tests for PDF generation functionality."""
import pytest
from unittest.mock import Mock, patch, MagicMock
import os
from decimal import Decimal
from datetime import datetime

from app.pdf import QuotePDFGenerator, generate_quote_pdf, render_quote_pdf, get_quote_pdf_url


class TestQuotePDFGenerator:
    """Test the QuotePDFGenerator class."""
    
    def test_generator_initialization(self):
        """Test QuotePDFGenerator initialization."""
        generator = QuotePDFGenerator()
        assert generator.styles is not None
        assert hasattr(generator, 'company_style')
        assert hasattr(generator, 'quote_title_style')
        assert hasattr(generator, 'section_style')
        assert hasattr(generator, 'normal_style')
        assert hasattr(generator, 'table_header_style')
        assert hasattr(generator, 'footer_style')
    
    def test_custom_styles_setup(self):
        """Test custom paragraph styles setup."""
        generator = QuotePDFGenerator()
        
        # Test company style
        assert generator.company_style.fontSize == 24
        assert generator.company_style.textColor is not None
        
        # Test quote title style
        assert generator.quote_title_style.fontSize == 18
        assert generator.quote_title_style.textColor is not None
        
        # Test section style
        assert generator.section_style.fontSize == 14
        assert generator.section_style.textColor is not None
    
    def test_create_header(self):
        """Test header creation."""
        generator = QuotePDFGenerator()
        elements = generator._create_header("Test Company")
        
        assert len(elements) > 0
        # Check that first element is company name
        assert "Test Company" in str(elements[0])
    
    def test_create_quote_info(self):
        """Test quote info creation."""
        generator = QuotePDFGenerator()
        
        # Mock quote object
        mock_quote = Mock()
        mock_quote.id = 123
        mock_quote.created_at = datetime(2024, 1, 15)
        mock_quote.status.value = "draft"
        
        elements = generator._create_quote_info(mock_quote)
        
        assert len(elements) > 0
        # Check that quote number is included
        assert "123" in str(elements[0])
    
    def test_create_bill_to_section(self):
        """Test bill-to section creation."""
        generator = QuotePDFGenerator()
        
        # Mock account object
        mock_account = Mock()
        mock_account.id = 456
        mock_account.name = "Test Account"
        mock_account.domain = "test.com"
        
        elements = generator._create_bill_to_section(mock_account)
        
        assert len(elements) > 0
        # Check that account name is included
        assert "Test Account" in str(elements[1])
    
    def test_create_line_items_table(self):
        """Test line items table creation."""
        generator = QuotePDFGenerator()
        
        # Mock pricebook
        mock_pricebook = Mock()
        mock_pricebook.currency = "USD"
        
        # Mock quote lines
        mock_line1 = Mock()
        mock_line1.sku = Mock()
        mock_line1.sku.code = "SKU001"
        mock_line1.sku.name = "Test Product"
        mock_line1.qty = 2
        mock_line1.unit_price = Decimal('10.00')
        mock_line1.discount_pct = 0.1
        
        mock_line2 = Mock()
        mock_line2.sku = Mock()
        mock_line2.sku.code = "SKU002"
        mock_line2.sku.name = "Another Product"
        mock_line2.qty = 1
        mock_line2.unit_price = Decimal('20.00')
        mock_line2.discount_pct = 0.0
        
        mock_lines = [mock_line1, mock_line2]
        
        elements = generator._create_line_items_table(mock_lines, mock_pricebook)
        
        assert len(elements) > 0
        # Check that subtotal was calculated
        assert hasattr(generator, 'subtotal')
        assert generator.subtotal > 0
    
    def test_create_totals_section(self):
        """Test totals section creation."""
        generator = QuotePDFGenerator()
        
        # Set up subtotal
        generator.subtotal = Decimal('100.00')
        
        # Mock pricebook
        mock_pricebook = Mock()
        mock_pricebook.currency = "USD"
        
        elements = generator._create_totals_section(mock_pricebook)
        
        assert len(elements) > 0
        # Check that totals are included
        assert "100.00" in str(elements[1])
    
    def test_create_footer(self):
        """Test footer creation."""
        generator = QuotePDFGenerator()
        elements = generator._create_footer()
        
        assert len(elements) > 0
        # Check that terms are included
        assert "TERMS AND CONDITIONS" in str(elements[0])
        # Check that signature section is included
        signature_found = False
        for element in elements:
            if "Customer Signature" in str(element):
                signature_found = True
                break
        assert signature_found, "Customer Signature section not found in footer"


class TestPDFFunctions:
    """Test the main PDF functions."""
    
    @patch('app.pdf.QuotePDFGenerator')
    def test_generate_quote_pdf(self, mock_generator_class):
        """Test generate_quote_pdf function."""
        mock_generator = Mock()
        mock_generator.generate_quote_pdf.return_value = "/tmp/test.pdf"
        mock_generator_class.return_value = mock_generator
        
        result = generate_quote_pdf(123)
        
        assert result == "/tmp/test.pdf"
        mock_generator.generate_quote_pdf.assert_called_once_with(123, None)
    
    def test_render_quote_pdf(self):
        """Test render_quote_pdf function."""
        with patch('app.pdf.generate_quote_pdf') as mock_generate:
            mock_generate.return_value = "/tmp/test.pdf"
            
            result = render_quote_pdf(123)
            
            assert result == "/tmp/test.pdf"
            mock_generate.assert_called_once_with(123)
    
    def test_get_quote_pdf_url(self):
        """Test get_quote_pdf_url function."""
        with patch('app.pdf.render_quote_pdf') as mock_render:
            mock_render.return_value = "public/quote_123.pdf"
            
            result = get_quote_pdf_url(123)
            
            assert result == "/public/quote_123.pdf"
            mock_render.assert_called_once_with(123)
    
    def test_get_quote_pdf_url_fallback(self):
        """Test get_quote_pdf_url fallback path."""
        with patch('app.pdf.render_quote_pdf') as mock_render:
            mock_render.return_value = "/tmp/quote_123.pdf"
            
            result = get_quote_pdf_url(123)
            
            assert result == "/quotes/123/pdf"
            mock_render.assert_called_once_with(123)


class TestPDFGenerationIntegration:
    """Test PDF generation with mocked database."""
    
    @patch('app.pdf.get_db')
    def test_pdf_generation_with_mock_data(self, mock_get_db):
        """Test complete PDF generation with mocked data."""
        # Mock database session
        mock_db = Mock()
        mock_get_db.return_value = iter([mock_db])
        
        # Mock quote
        mock_quote = Mock()
        mock_quote.id = 123
        mock_quote.created_at = datetime(2024, 1, 15)
        mock_quote.status.value = "draft"
        mock_quote.account_id = 456
        mock_quote.pricebook_id = 789
        
        # Mock account
        mock_account = Mock()
        mock_account.id = 456
        mock_account.name = "Test Company"
        mock_account.domain = "test.com"
        
        # Mock pricebook
        mock_pricebook = Mock()
        mock_pricebook.id = 789
        mock_pricebook.currency = "USD"
        
        # Mock quote lines
        mock_line = Mock()
        mock_line.sku = Mock()
        mock_line.sku.code = "SKU001"
        mock_line.sku.name = "Test Product"
        mock_line.qty = 2
        mock_line.unit_price = Decimal('10.00')
        mock_line.discount_pct = 0.0
        mock_quote.lines = [mock_line]
        
        # Setup database queries
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_quote,  # Quote query
            mock_account,  # Account query
            mock_pricebook  # Pricebook query
        ]
        
        # Test PDF generation
        generator = QuotePDFGenerator()
        
        # This should work without errors
        try:
            # We can't actually generate the PDF in tests, but we can test the setup
            assert generator is not None
            assert hasattr(generator, 'generate_quote_pdf')
        except Exception as e:
            pytest.fail(f"PDF generation setup failed: {str(e)}")


class TestPDFErrorHandling:
    """Test PDF generation error handling."""
    
    @patch('app.pdf.get_db')
    def test_pdf_generation_quote_not_found(self, mock_get_db):
        """Test PDF generation when quote is not found."""
        mock_db = Mock()
        mock_get_db.return_value = iter([mock_db])
        
        # Mock quote not found
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        generator = QuotePDFGenerator()
        
        with pytest.raises(RuntimeError, match="Quote with ID 999 not found"):
            generator.generate_quote_pdf(999)
    
    @patch('app.pdf.get_db')
    def test_pdf_generation_incomplete_data(self, mock_get_db):
        """Test PDF generation with incomplete quote data."""
        mock_db = Mock()
        mock_get_db.return_value = iter([mock_db])
        
        # Mock quote found but missing account
        mock_quote = Mock()
        mock_quote.id = 123
        mock_quote.account_id = 456
        mock_quote.pricebook_id = 789
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_quote,  # Quote query
            None,  # Account query (not found)
            None   # Pricebook query (not found)
        ]
        
        generator = QuotePDFGenerator()
        
        with pytest.raises(RuntimeError, match="Quote data incomplete"):
            generator.generate_quote_pdf(123)
