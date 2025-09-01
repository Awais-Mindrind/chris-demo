"""Unit tests for CRUD operations."""
import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.crud import (
    create_account, get_account, get_accounts, search_accounts,
    create_pricebook, get_pricebook, get_pricebooks,
    create_sku, get_sku, get_skus,
    create_quote, get_quote, get_quotes
)
from app.schemas import (
    AccountCreate, PricebookCreate, SkuCreate, QuoteCreate, QuoteLineCreate
)
from app.models import Base, QuoteStatus


# Test database setup
@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


class TestAccountCRUD:
    """Test account CRUD operations."""
    
    def test_create_account_success(self, db_session):
        """Test successful account creation."""
        account_data = AccountCreate(
            name="Test Company",
            domain="test.com",
            confidence_score=0.95
        )
        
        result = create_account(db_session, account_data)
        
        assert result.name == "Test Company"
        assert result.domain == "test.com"
        assert result.confidence_score == 0.95
        assert result.id is not None
    
    def test_create_account_duplicate_name(self, db_session):
        """Test account creation with duplicate name fails."""
        account_data = AccountCreate(name="Test Company")
        create_account(db_session, account_data)
        
        # Try to create another with same name
        duplicate_data = AccountCreate(name="Test Company")
        with pytest.raises(ValueError, match="already exists"):
            create_account(db_session, duplicate_data)
    
    def test_create_account_empty_name(self, db_session):
        """Test account creation with empty name fails."""
        account_data = AccountCreate(name="")
        with pytest.raises(ValueError, match="required"):
            create_account(db_session, account_data)
    
    def test_get_account_success(self, db_session):
        """Test successful account retrieval."""
        account_data = AccountCreate(name="Test Company")
        created = create_account(db_session, account_data)
        
        result = get_account(db_session, created.id)
        
        assert result is not None
        assert result.name == "Test Company"
    
    def test_get_account_not_found(self, db_session):
        """Test account retrieval for non-existent ID."""
        result = get_account(db_session, 999)
        assert result is None


class TestPricebookCRUD:
    """Test pricebook CRUD operations."""
    
    def test_create_pricebook_success(self, db_session):
        """Test successful pricebook creation."""
        pricebook_data = PricebookCreate(
            name="Standard",
            currency="USD",
            is_default=True
        )
        
        result = create_pricebook(db_session, pricebook_data)
        
        assert result.name == "Standard"
        assert result.currency == "USD"
        assert result.is_default is True
        assert result.id is not None
    
    def test_create_pricebook_duplicate_name(self, db_session):
        """Test pricebook creation with duplicate name fails."""
        pricebook_data = PricebookCreate(name="Standard", currency="USD")
        create_pricebook(db_session, pricebook_data)
        
        # Try to create another with same name
        duplicate_data = PricebookCreate(name="Standard", currency="EUR")
        with pytest.raises(ValueError, match="already exists"):
            create_pricebook(db_session, duplicate_data)
    
    def test_get_pricebooks_with_filters(self, db_session):
        """Test pricebook retrieval with filters."""
        # Create test pricebooks
        create_pricebook(db_session, PricebookCreate(name="USD", currency="USD", is_default=True))
        create_pricebook(db_session, PricebookCreate(name="EUR", currency="EUR", is_default=False))
        
        results = get_pricebooks(db_session, currency_filter="USD")
        assert len(results) == 1
        assert results[0].currency == "USD"


class TestSkuCRUD:
    """Test SKU CRUD operations."""
    
    def test_create_sku_success(self, db_session):
        """Test successful SKU creation."""
        # Create pricebook first
        pricebook = create_pricebook(db_session, PricebookCreate(name="Test", currency="USD"))
        
        sku_data = SkuCreate(
            code="TEST-001",
            name="Test Product",
            pricebook_id=pricebook.id,
            unit_price=Decimal("99.99")
        )
        
        result = create_sku(db_session, sku_data)
        
        assert result.code == "TEST-001"
        assert result.name == "Test Product"
        assert result.unit_price == Decimal("99.99")
        assert result.id is not None
    
    def test_create_sku_invalid_pricebook(self, db_session):
        """Test SKU creation with invalid pricebook ID fails."""
        sku_data = SkuCreate(
            code="TEST-001",
            name="Test Product",
            pricebook_id=999,
            unit_price=Decimal("99.99")
        )
        
        with pytest.raises(ValueError, match="does not exist"):
            create_sku(db_session, sku_data)


class TestQuoteCRUD:
    """Test quote CRUD operations."""
    
    def test_create_quote_success(self, db_session):
        """Test successful quote creation."""
        # Create required dependencies
        account = create_account(db_session, AccountCreate(name="Test Customer"))
        pricebook = create_pricebook(db_session, PricebookCreate(name="Test", currency="USD"))
        sku = create_sku(db_session, SkuCreate(
            code="TEST-001",
            name="Test Product",
            pricebook_id=pricebook.id,
            unit_price=Decimal("99.99")
        ))
        
        quote_data = QuoteCreate(
            account_id=account.id,
            pricebook_id=pricebook.id,
            lines=[
                QuoteLineCreate(
                    sku_id=sku.id,
                    qty=2,
                    discount_pct=0.1
                )
            ]
        )
        
        result = create_quote(db_session, quote_data)
        
        assert result.account_id == account.id
        assert result.pricebook_id == pricebook.id
        assert result.status == "draft"
        assert len(result.lines) == 1
        assert result.lines[0].qty == 2
        assert result.lines[0].discount_pct == 0.1
    
    def test_create_quote_no_lines(self, db_session):
        """Test quote creation without lines fails."""
        account = create_account(db_session, AccountCreate(name="Test Customer"))
        pricebook = create_pricebook(db_session, PricebookCreate(name="Test", currency="USD"))
        
        with pytest.raises(ValueError, match="List should have at least 1 item"):
            QuoteCreate(
                account_id=account.id,
                pricebook_id=pricebook.id,
                lines=[]
            )
