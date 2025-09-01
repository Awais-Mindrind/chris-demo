"""Database CRUD operations with safe read/write functions."""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc
from sqlalchemy.exc import IntegrityError, NoResultFound
from decimal import Decimal

from app.models import Account, Pricebook, Sku, Quote, QuoteLine, QuoteStatus, IdempotencyKey, ChatSession, ChatMessage
from app.schemas import (
    AccountCreate, AccountRead, PricebookCreate, PricebookRead,
    SkuCreate, SkuRead, QuoteCreate, QuoteRead, QuoteLineCreate, QuoteLineRead
)


# =============================================================================
# ACCOUNT CRUD OPERATIONS
# =============================================================================

def create_account(db: Session, account_data: AccountCreate) -> AccountRead:
    """Create a new account with validation."""
    # Validate required fields
    if not account_data.name or not account_data.name.strip():
        raise ValueError("Account name is required and cannot be empty")
    
    # Check for duplicate names (case-insensitive)
    existing_account = db.query(Account).filter(
        Account.name.ilike(account_data.name.strip())
    ).first()
    
    if existing_account:
        raise ValueError(f"Account with name '{account_data.name}' already exists")
    
    # Create account instance
    db_account = Account(
        name=account_data.name.strip(),
        domain=account_data.domain.strip() if account_data.domain else None,
        external_crm_ids=account_data.external_crm_ids,
        confidence_score=account_data.confidence_score
    )
    
    try:
        db.add(db_account)
        db.commit()
        db.refresh(db_account)
        return AccountRead.model_validate(db_account)
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Failed to create account: {str(e)}")


def get_account(db: Session, account_id: int) -> Optional[AccountRead]:
    """Get account by ID."""
    if not account_id or account_id <= 0:
        raise ValueError("Invalid account ID")
    
    db_account = db.query(Account).filter(Account.id == account_id).first()
    if not db_account:
        return None
    
    return AccountRead.model_validate(db_account)


def get_accounts(
    db: Session, 
    skip: int = 0, 
    limit: int = 100,
    name_filter: Optional[str] = None,
    domain_filter: Optional[str] = None
) -> List[AccountRead]:
    """Get accounts with optional filtering and pagination."""
    query = db.query(Account)
    
    # Apply filters
    if name_filter:
        query = query.filter(Account.name.ilike(f"%{name_filter}%"))
    
    if domain_filter:
        query = query.filter(Account.domain.ilike(f"%{domain_filter}%"))
    
    # Apply pagination and ordering
    accounts = query.order_by(Account.name).offset(skip).limit(limit).all()
    
    return [AccountRead.model_validate(account) for account in accounts]


def search_accounts(db: Session, query: str) -> List[AccountRead]:
    """Search accounts by name or domain."""
    if not query or not query.strip():
        return []
    
    search_term = f"%{query.strip()}%"
    accounts = db.query(Account).filter(
        or_(
            Account.name.ilike(search_term),
            Account.domain.ilike(search_term)
        )
    ).order_by(Account.name).all()
    
    return [AccountRead.model_validate(account) for account in accounts]


def update_account(
    db: Session, 
    account_id: int, 
    account_data: AccountCreate
) -> Optional[AccountRead]:
    """Update an existing account."""
    if not account_id or account_id <= 0:
        raise ValueError("Invalid account ID")
    
    if not account_data.name or not account_data.name.strip():
        raise ValueError("Account name is required and cannot be empty")
    
    # Check if account exists
    db_account = db.query(Account).filter(Account.id == account_id).first()
    if not db_account:
        return None
    
    # Check for duplicate names (excluding current account)
    existing_account = db.query(Account).filter(
        and_(
            Account.name.ilike(account_data.name.strip()),
            Account.id != account_id
        )
    ).first()
    
    if existing_account:
        raise ValueError(f"Account with name '{account_data.name}' already exists")
    
    # Update fields
    db_account.name = account_data.name.strip()
    db_account.domain = account_data.domain.strip() if account_data.domain else None
    db_account.external_crm_ids = account_data.external_crm_ids
    db_account.confidence_score = account_data.confidence_score
    
    try:
        db.commit()
        db.refresh(db_account)
        return AccountRead.model_validate(db_account)
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Failed to update account: {str(e)}")


def delete_account(db: Session, account_id: int) -> bool:
    """Delete an account if it has no associated quotes."""
    if not account_id or account_id <= 0:
        raise ValueError("Invalid account ID")
    
    db_account = db.query(Account).filter(Account.id == account_id).first()
    if not db_account:
        return False
    
    # Check if account has quotes
    if db_account.quotes:
        raise ValueError("Cannot delete account with existing quotes")
    
    try:
        db.delete(db_account)
        db.commit()
        return True
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Failed to delete account: {str(e)}")


# =============================================================================
# PRICEBOOK CRUD OPERATIONS
# =============================================================================

def create_pricebook(db: Session, pricebook_data: PricebookCreate) -> PricebookRead:
    """Create a new pricebook with validation."""
    if not pricebook_data.name or not pricebook_data.name.strip():
        raise ValueError("Pricebook name is required and cannot be empty")
    
    if not pricebook_data.currency or not pricebook_data.currency.strip():
        raise ValueError("Currency is required and cannot be empty")
    
    # Check for duplicate names
    existing_pricebook = db.query(Pricebook).filter(
        Pricebook.name.ilike(pricebook_data.name.strip())
    ).first()
    
    if existing_pricebook:
        raise ValueError(f"Pricebook with name '{pricebook_data.name}' already exists")
    
    # If setting as default, unset other defaults
    if pricebook_data.is_default:
        db.query(Pricebook).filter(Pricebook.is_default == True).update(
            {"is_default": False}
        )
    
    db_pricebook = Pricebook(
        name=pricebook_data.name.strip(),
        currency=pricebook_data.currency.strip().upper(),
        is_default=pricebook_data.is_default
    )
    
    try:
        db.add(db_pricebook)
        db.commit()
        db.refresh(db_pricebook)
        return PricebookRead.model_validate(db_pricebook)
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Failed to create pricebook: {str(e)}")


def get_pricebook(db: Session, pricebook_id: int) -> Optional[PricebookRead]:
    """Get pricebook by ID."""
    if not pricebook_id or pricebook_id <= 0:
        raise ValueError("Invalid pricebook ID")
    
    db_pricebook = db.query(Pricebook).filter(Pricebook.id == pricebook_id).first()
    if not db_pricebook:
        return None
    
    return PricebookRead.model_validate(db_pricebook)


def get_pricebooks(
    db: Session, 
    skip: int = 0, 
    limit: int = 100,
    currency_filter: Optional[str] = None,
    is_default: Optional[bool] = None
) -> List[PricebookRead]:
    """Get pricebooks with optional filtering and pagination."""
    query = db.query(Pricebook)
    
    if currency_filter:
        query = query.filter(Pricebook.currency.ilike(f"%{currency_filter}%"))
    
    if is_default is not None:
        query = query.filter(Pricebook.is_default == is_default)
    
    pricebooks = query.order_by(desc(Pricebook.is_default), Pricebook.name).offset(skip).limit(limit).all()
    
    return [PricebookRead.model_validate(pricebook) for pricebook in pricebooks]


def get_default_pricebook(db: Session) -> Optional[PricebookRead]:
    """Get the default pricebook."""
    db_pricebook = db.query(Pricebook).filter(Pricebook.is_default == True).first()
    if not db_pricebook:
        return None
    
    return PricebookRead.model_validate(db_pricebook)


def update_pricebook(
    db: Session, 
    pricebook_id: int, 
    pricebook_data: PricebookCreate
) -> Optional[PricebookRead]:
    """Update an existing pricebook."""
    if not pricebook_id or pricebook_id <= 0:
        raise ValueError("Invalid pricebook ID")
    
    if not pricebook_data.name or not pricebook_data.name.strip():
        raise ValueError("Pricebook name is required and cannot be empty")
    
    if not pricebook_data.currency or not pricebook_data.currency.strip():
        raise ValueError("Currency is required and cannot be empty")
    
    db_pricebook = db.query(Pricebook).filter(Pricebook.id == pricebook_id).first()
    if not db_pricebook:
        return None
    
    # Check for duplicate names (excluding current pricebook)
    existing_pricebook = db.query(Pricebook).filter(
        and_(
            Pricebook.name.ilike(pricebook_data.name.strip()),
            Pricebook.id != pricebook_id
        )
    ).first()
    
    if existing_pricebook:
        raise ValueError(f"Pricebook with name '{pricebook_data.name}' already exists")
    
    # If setting as default, unset other defaults
    if pricebook_data.is_default and not db_pricebook.is_default:
        db.query(Pricebook).filter(Pricebook.is_default == True).update(
            {"is_default": False}
        )
    
    # Update fields
    db_pricebook.name = pricebook_data.name.strip()
    db_pricebook.currency = pricebook_data.currency.strip().upper()
    db_pricebook.is_default = pricebook_data.is_default
    
    try:
        db.commit()
        db.refresh(db_pricebook)
        return PricebookRead.model_validate(db_pricebook)
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Failed to update pricebook: {str(e)}")


def delete_pricebook(db: Session, pricebook_id: int) -> bool:
    """Delete a pricebook if it has no associated SKUs or quotes."""
    if not pricebook_id or pricebook_id <= 0:
        raise ValueError("Invalid pricebook ID")
    
    db_pricebook = db.query(Pricebook).filter(Pricebook.id == pricebook_id).first()
    if not db_pricebook:
        return False
    
    # Check if pricebook has SKUs or quotes
    if db_pricebook.skus or db_pricebook.quotes:
        raise ValueError("Cannot delete pricebook with existing SKUs or quotes")
    
    try:
        db.delete(db_pricebook)
        db.commit()
        return True
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Failed to delete pricebook: {str(e)}")


# =============================================================================
# SKU CRUD OPERATIONS
# =============================================================================

def create_sku(db: Session, sku_data: SkuCreate) -> SkuRead:
    """Create a new SKU with validation."""
    if not sku_data.code or not sku_data.code.strip():
        raise ValueError("SKU code is required and cannot be empty")
    
    if not sku_data.name or not sku_data.name.strip():
        raise ValueError("SKU name is required and cannot be empty")
    
    if not sku_data.pricebook_id or sku_data.pricebook_id <= 0:
        raise ValueError("Valid pricebook ID is required")
    
    if sku_data.unit_price is None or sku_data.unit_price < 0:
        raise ValueError("Unit price must be non-negative")
    
    # Validate pricebook exists
    pricebook = db.query(Pricebook).filter(Pricebook.id == sku_data.pricebook_id).first()
    if not pricebook:
        raise ValueError(f"Pricebook with ID {sku_data.pricebook_id} does not exist")
    
    # Check for duplicate codes within the same pricebook
    existing_sku = db.query(Sku).filter(
        and_(
            Sku.code.ilike(sku_data.code.strip()),
            Sku.pricebook_id == sku_data.pricebook_id
        )
    ).first()
    
    if existing_sku:
        raise ValueError(f"SKU with code '{sku_data.code}' already exists in this pricebook")
    
    # Validate parent SKU if provided
    if sku_data.parent_sku_id:
        parent_sku = db.query(Sku).filter(Sku.id == sku_data.parent_sku_id).first()
        if not parent_sku:
            raise ValueError(f"Parent SKU with ID {sku_data.parent_sku_id} does not exist")
    
    db_sku = Sku(
        code=sku_data.code.strip(),
        name=sku_data.name.strip(),
        pricebook_id=sku_data.pricebook_id,
        unit_price=sku_data.unit_price,
        parent_sku_id=sku_data.parent_sku_id,
        attributes=sku_data.attributes
    )
    
    try:
        db.add(db_sku)
        db.commit()
        db.refresh(db_sku)
        return SkuRead.model_validate(db_sku)
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Failed to create SKU: {str(e)}")


def get_sku(db: Session, sku_id: int) -> Optional[SkuRead]:
    """Get SKU by ID."""
    if not sku_id or sku_id <= 0:
        raise ValueError("Invalid SKU ID")
    
    db_sku = db.query(Sku).filter(Sku.id == sku_id).first()
    if not db_sku:
        return None
    
    return SkuRead.model_validate(db_sku)


def get_skus(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    pricebook_id: Optional[int] = None,
    parent_sku_id: Optional[int] = None,
    name_filter: Optional[str] = None,
    code_filter: Optional[str] = None
) -> List[SkuRead]:
    """Get SKUs with optional filtering and pagination."""
    query = db.query(Sku)
    
    if pricebook_id:
        query = query.filter(Sku.pricebook_id == pricebook_id)
    
    if parent_sku_id is not None:
        if parent_sku_id == 0:
            query = query.filter(Sku.parent_sku_id.is_(None))  # Root SKUs only
        else:
            query = query.filter(Sku.parent_sku_id == parent_sku_id)
    
    if name_filter:
        query = query.filter(Sku.name.ilike(f"%{name_filter}%"))
    
    if code_filter:
        query = query.filter(Sku.code.ilike(f"%{code_filter}%"))
    
    skus = query.order_by(Sku.code).offset(skip).limit(limit).all()
    
    return [SkuRead.model_validate(sku) for sku in skus]


def search_skus(db: Session, query: str, pricebook_id: Optional[int] = None) -> List[SkuRead]:
    """Search SKUs by name or code."""
    if not query or not query.strip():
        return []
    
    search_term = f"%{query.strip()}%"
    db_query = db.query(Sku).filter(
        or_(
            Sku.name.ilike(search_term),
            Sku.code.ilike(search_term)
        )
    )
    
    if pricebook_id:
        db_query = db_query.filter(Sku.pricebook_id == pricebook_id)
    
    skus = db_query.order_by(Sku.code).all()
    
    return [SkuRead.model_validate(sku) for sku in skus]


def update_sku(
    db: Session,
    sku_id: int,
    sku_data: SkuCreate
) -> Optional[SkuRead]:
    """Update an existing SKU."""
    if not sku_id or sku_id <= 0:
        raise ValueError("Invalid SKU ID")
    
    if not sku_data.code or not sku_data.code.strip():
        raise ValueError("SKU code is required and cannot be empty")
    
    if not sku_data.name or not sku_data.name.strip():
        raise ValueError("SKU name is required and cannot be empty")
    
    if not sku_data.pricebook_id or sku_data.pricebook_id <= 0:
        raise ValueError("Valid pricebook ID is required")
    
    if sku_data.unit_price is None or sku_data.unit_price < 0:
        raise ValueError("Unit price must be non-negative")
    
    db_sku = db.query(Sku).filter(Sku.id == sku_id).first()
    if not db_sku:
        return None
    
    # Validate pricebook exists
    pricebook = db.query(Pricebook).filter(Pricebook.id == sku_data.pricebook_id).first()
    if not pricebook:
        raise ValueError(f"Pricebook with ID {sku_data.pricebook_id} does not exist")
    
    # Check for duplicate codes within the same pricebook (excluding current SKU)
    existing_sku = db.query(Sku).filter(
        and_(
            Sku.code.ilike(sku_data.code.strip()),
            Sku.pricebook_id == sku_data.pricebook_id,
            Sku.id != sku_id
        )
    ).first()
    
    if existing_sku:
        raise ValueError(f"SKU with code '{sku_data.code}' already exists in this pricebook")
    
    # Validate parent SKU if provided
    if sku_data.parent_sku_id:
        if sku_data.parent_sku_id == sku_id:
            raise ValueError("SKU cannot be its own parent")
        
        parent_sku = db.query(Sku).filter(Sku.id == sku_data.parent_sku_id).first()
        if not parent_sku:
            raise ValueError(f"Parent SKU with ID {sku_data.parent_sku_id} does not exist")
    
    # Update fields
    db_sku.code = sku_data.code.strip()
    db_sku.name = sku_data.name.strip()
    db_sku.pricebook_id = sku_data.pricebook_id
    db_sku.unit_price = sku_data.unit_price
    db_sku.parent_sku_id = sku_data.parent_sku_id
    db_sku.attributes = sku_data.attributes
    
    try:
        db.commit()
        db.refresh(db_sku)
        return SkuRead.model_validate(db_sku)
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Failed to update SKU: {str(e)}")


def delete_sku(db: Session, sku_id: int) -> bool:
    """Delete a SKU if it has no associated quote lines or child SKUs."""
    if not sku_id or sku_id <= 0:
        raise ValueError("Invalid SKU ID")
    
    db_sku = db.query(Sku).filter(Sku.id == sku_id).first()
    if not db_sku:
        return False
    
    # Check if SKU has quote lines or child SKUs
    if db_sku.quote_lines or db_sku.child_skus:
        raise ValueError("Cannot delete SKU with existing quote lines or child SKUs")
    
    try:
        db.delete(db_sku)
        db.commit()
        return True
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Failed to delete SKU: {str(e)}")


# =============================================================================
# QUOTE CRUD OPERATIONS
# =============================================================================

def create_quote(db: Session, quote_data: QuoteCreate, idempotency_key: Optional[str] = None) -> QuoteRead:
    """Create a new quote with validation."""
    if not quote_data.account_id or quote_data.account_id <= 0:
        raise ValueError("Valid account ID is required")
    
    if not quote_data.pricebook_id or quote_data.pricebook_id <= 0:
        raise ValueError("Valid pricebook ID is required")
    
    if not quote_data.lines or len(quote_data.lines) == 0:
        raise ValueError("Quote must have at least one line item")
    
    # Check idempotency key if provided
    if idempotency_key:
        existing_quote_id = check_idempotency_key(db, idempotency_key)
        if existing_quote_id:
            # Return existing quote
            existing_quote = get_quote(db, existing_quote_id)
            if existing_quote:
                return existing_quote
            else:
                # Quote was deleted, remove the idempotency key
                db.query(IdempotencyKey).filter(IdempotencyKey.key == idempotency_key).delete()
                db.commit()
    
    # Validate account exists
    account = db.query(Account).filter(Account.id == quote_data.account_id).first()
    if not account:
        raise ValueError(f"Account with ID {quote_data.account_id} does not exist")
    
    # Validate pricebook exists
    pricebook = db.query(Pricebook).filter(Pricebook.id == quote_data.pricebook_id).first()
    if not pricebook:
        raise ValueError(f"Pricebook with ID {quote_data.pricebook_id} does not exist")
    
    # Validate line items
    for line in quote_data.lines:
        if not line.sku_id or line.sku_id <= 0:
            raise ValueError("Valid SKU ID is required for all line items")
        
        if not line.qty or line.qty <= 0:
            raise ValueError("Quantity must be greater than 0 for all line items")
        
        if line.discount_pct < 0 or line.discount_pct >= 1:
            raise ValueError("Discount percentage must be between 0 and 1")
        
        # Validate SKU exists and belongs to the pricebook
        sku = db.query(Sku).filter(
            and_(
                Sku.id == line.sku_id,
                Sku.pricebook_id == quote_data.pricebook_id
            )
        ).first()
        
        if not sku:
            raise ValueError(f"SKU with ID {line.sku_id} does not exist in the specified pricebook")
    
    # Create quote
    db_quote = Quote(
        account_id=quote_data.account_id,
        pricebook_id=quote_data.pricebook_id,
        status=QuoteStatus.draft
    )
    
    try:
        db.add(db_quote)
        db.flush()  # Get the quote ID
        
        # Create quote lines
        for line_data in quote_data.lines:
            # Get SKU to determine unit price if not provided
            sku = db.query(Sku).filter(Sku.id == line_data.sku_id).first()
            unit_price = line_data.unit_price if line_data.unit_price is not None else sku.unit_price
            
            quote_line = QuoteLine(
                quote_id=db_quote.id,
                sku_id=line_data.sku_id,
                qty=line_data.qty,
                unit_price=unit_price,
                discount_pct=line_data.discount_pct
            )
            db.add(quote_line)
        
        # Store idempotency key if provided
        if idempotency_key:
            store_idempotency_key(db, idempotency_key, "quote", db_quote.id)
        
        db.commit()
        db.refresh(db_quote)
        
        # Return the complete quote with lines
        return get_quote(db, db_quote.id)
        
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Failed to create quote: {str(e)}")


def get_quote(db: Session, quote_id: int) -> Optional[QuoteRead]:
    """Get quote by ID with all line items."""
    if not quote_id or quote_id <= 0:
        raise ValueError("Invalid quote ID")
    
    db_quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not db_quote:
        return None
    
    # Convert to Pydantic schema
    quote_dict = {
        "id": db_quote.id,
        "account_id": db_quote.account_id,
        "pricebook_id": db_quote.pricebook_id,
        "status": db_quote.status.value,
        "created_at": db_quote.created_at.isoformat() if db_quote.created_at else None,
        "lines": []
    }
    
    # Add line items
    for line in db_quote.lines:
        line_dict = {
            "id": line.id,
            "quote_id": line.quote_id,
            "sku_id": line.sku_id,
            "qty": line.qty,
            "unit_price": line.unit_price,
            "discount_pct": line.discount_pct
        }
        quote_dict["lines"].append(line_dict)
    
    return QuoteRead.model_validate(quote_dict)


def get_quotes(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    account_id: Optional[int] = None,
    pricebook_id: Optional[int] = None,
    status: Optional[QuoteStatus] = None
) -> List[QuoteRead]:
    """Get quotes with optional filtering and pagination."""
    query = db.query(Quote)
    
    if account_id:
        query = query.filter(Quote.account_id == account_id)
    
    if pricebook_id:
        query = query.filter(Quote.pricebook_id == pricebook_id)
    
    if status:
        query = query.filter(Quote.status == status)
    
    quotes = query.order_by(desc(Quote.created_at)).offset(skip).limit(limit).all()
    
    return [get_quote(db, quote.id) for quote in quotes if quote]


def update_quote_status(db: Session, quote_id: int, status: QuoteStatus) -> Optional[QuoteRead]:
    """Update quote status."""
    if not quote_id or quote_id <= 0:
        raise ValueError("Invalid quote ID")
    
    if not status:
        raise ValueError("Valid status is required")
    
    db_quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not db_quote:
        return None
    
    # Validate status transition
    if db_quote.status == QuoteStatus.accepted and status != QuoteStatus.accepted:
        raise ValueError("Cannot change status of accepted quote")
    
    db_quote.status = status
    
    try:
        db.commit()
        db.refresh(db_quote)
        return get_quote(db, quote_id)
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Failed to update quote status: {str(e)}")


def delete_quote(db: Session, quote_id: int) -> bool:
    """Delete a quote and all its line items."""
    if not quote_id or quote_id <= 0:
        raise ValueError("Invalid quote ID")
    
    db_quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not db_quote:
        return False
    
    # Check if quote can be deleted (only draft quotes)
    if db_quote.status != QuoteStatus.draft:
        raise ValueError("Only draft quotes can be deleted")
    
    try:
        # Delete quote lines first
        db.query(QuoteLine).filter(QuoteLine.quote_id == quote_id).delete()
        
        # Delete quote
        db.delete(db_quote)
        db.commit()
        return True
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Failed to delete quote: {str(e)}")


# =============================================================================
# QUOTE LINE CRUD OPERATIONS
# =============================================================================

def add_quote_line(
    db: Session,
    quote_id: int,
    line_data: QuoteLineCreate
) -> Optional[QuoteLineRead]:
    """Add a line item to an existing quote."""
    if not quote_id or quote_id <= 0:
        raise ValueError("Valid quote ID is required")
    
    if not line_data.sku_id or line_data.sku_id <= 0:
        raise ValueError("Valid SKU ID is required")
    
    if not line_data.qty or line_data.qty <= 0:
        raise ValueError("Quantity must be greater than 0")
    
    if line_data.discount_pct < 0 or line_data.discount_pct >= 1:
        raise ValueError("Discount percentage must be between 0 and 1")
    
    # Validate quote exists and is editable
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote:
        raise ValueError(f"Quote with ID {quote_id} does not exist")
    
    if quote.status != QuoteStatus.draft:
        raise ValueError("Cannot modify non-draft quotes")
    
    # Validate SKU exists and belongs to the quote's pricebook
    sku = db.query(Sku).filter(
        and_(
            Sku.id == line_data.sku_id,
            Sku.pricebook_id == quote.pricebook_id
        )
    ).first()
    
    if not sku:
        raise ValueError(f"SKU with ID {line_data.sku_id} does not exist in the quote's pricebook")
    
    # Get unit price from SKU if not provided
    unit_price = line_data.unit_price if line_data.unit_price is not None else sku.unit_price
    
    quote_line = QuoteLine(
        quote_id=quote_id,
        sku_id=line_data.sku_id,
        qty=line_data.qty,
        unit_price=unit_price,
        discount_pct=line_data.discount_pct
    )
    
    try:
        db.add(quote_line)
        db.commit()
        db.refresh(quote_line)
        return QuoteLineRead.model_validate(quote_line)
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Failed to add quote line: {str(e)}")


def update_quote_line(
    db: Session,
    line_id: int,
    line_data: QuoteLineCreate
) -> Optional[QuoteLineRead]:
    """Update an existing quote line."""
    if not line_id or line_id <= 0:
        raise ValueError("Invalid line ID")
    
    if not line_data.qty or line_data.qty <= 0:
        raise ValueError("Quantity must be greater than 0")
    
    if line_data.discount_pct < 0 or line_data.discount_pct >= 1:
        raise ValueError("Discount percentage must be between 0 and 1")
    
    db_line = db.query(QuoteLine).filter(QuoteLine.id == line_id).first()
    if not db_line:
        return None
    
    # Validate quote is editable
    quote = db.query(Quote).filter(Quote.id == db_line.quote_id).first()
    if not quote or quote.status != QuoteStatus.draft:
        raise ValueError("Cannot modify non-draft quotes")
    
    # Update fields
    db_line.qty = line_data.qty
    db_line.unit_price = line_data.unit_price
    db_line.discount_pct = line_data.discount_pct
    
    try:
        db.commit()
        db.refresh(db_line)
        return QuoteLineRead.model_validate(db_line)
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Failed to update quote line: {str(e)}")


def delete_quote_line(db: Session, line_id: int) -> bool:
    """Delete a quote line."""
    if not line_id or line_id <= 0:
        raise ValueError("Invalid line ID")
    
    db_line = db.query(QuoteLine).filter(QuoteLine.id == line_id).first()
    if not db_line:
        return False
    
    # Validate quote is editable
    quote = db.query(Quote).filter(Quote.id == db_line.quote_id).first()
    if not quote or quote.status != QuoteStatus.draft:
        raise ValueError("Cannot modify non-draft quotes")
    
    try:
        db.delete(db_line)
        db.commit()
        return True
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Failed to delete quote line: {str(e)}")


# =============================================================================
# IDEMPOTENCY FUNCTIONS
# =============================================================================

def check_idempotency_key(db: Session, key: str) -> Optional[int]:
    """Check if idempotency key exists and return resource ID if found."""
    if not key:
        return None
    
    # Clean up expired keys first
    cleanup_expired_idempotency_keys(db)
    
    # Check for existing key
    idempotency_record = db.query(IdempotencyKey).filter(
        IdempotencyKey.key == key
    ).first()
    
    if idempotency_record:
        return idempotency_record.resource_id
    
    return None


def store_idempotency_key(db: Session, key: str, resource_type: str, resource_id: int, ttl_hours: int = 24) -> None:
    """Store idempotency key with resource reference."""
    if not key or not resource_type or not resource_id:
        raise ValueError("Invalid idempotency key parameters")
    
    from datetime import datetime, timedelta
    
    expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
    
    idempotency_record = IdempotencyKey(
        key=key,
        resource_type=resource_type,
        resource_id=resource_id,
        expires_at=expires_at
    )
    
    try:
        db.add(idempotency_record)
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Failed to store idempotency key: {str(e)}")


def cleanup_expired_idempotency_keys(db: Session) -> int:
    """Clean up expired idempotency keys and return count of deleted records."""
    from datetime import datetime
    
    expired_keys = db.query(IdempotencyKey).filter(
        IdempotencyKey.expires_at < datetime.utcnow()
    ).all()
    
    count = len(expired_keys)
    if count > 0:
        for key in expired_keys:
            db.delete(key)
        db.commit()
    
    return count


# =============================================================================
# CHAT HISTORY FUNCTIONS
# =============================================================================

def create_chat_session(db: Session, session_id: str) -> ChatSession:
    """Create a new chat session."""
    if not session_id:
        raise ValueError("Session ID is required")
    
    # Check if session already exists
    existing_session = db.query(ChatSession).filter(
        ChatSession.session_id == session_id
    ).first()
    
    if existing_session:
        # Reactivate if inactive
        if not existing_session.is_active:
            existing_session.is_active = True
            db.commit()
            db.refresh(existing_session)
        return existing_session
    
    # Create new session
    chat_session = ChatSession(session_id=session_id)
    
    try:
        db.add(chat_session)
        db.commit()
        db.refresh(chat_session)
        return chat_session
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Failed to create chat session: {str(e)}")


def get_chat_session(db: Session, session_id: str) -> Optional[ChatSession]:
    """Get chat session by ID."""
    if not session_id:
        return None
    
    return db.query(ChatSession).filter(
        ChatSession.session_id == session_id,
        ChatSession.is_active == True
    ).first()


def add_chat_message(
    db: Session, 
    session_id: str, 
    role: str, 
    content: str, 
    metadata: Optional[Dict[str, Any]] = None
) -> ChatMessage:
    """Add a message to a chat session."""
    if not session_id or not role or not content:
        raise ValueError("Session ID, role, and content are required")
    
    # Ensure session exists
    session = get_chat_session(db, session_id)
    if not session:
        session = create_chat_session(db, session_id)
    
    # Create message
    chat_message = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        message_metadata=metadata or {}
    )
    
    try:
        db.add(chat_message)
        db.commit()
        db.refresh(chat_message)
        return chat_message
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Failed to add chat message: {str(e)}")


def get_chat_messages(
    db: Session, 
    session_id: str, 
    limit: int = 50
) -> List[ChatMessage]:
    """Get recent chat messages for a session."""
    if not session_id:
        return []
    
    return db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(desc(ChatMessage.created_at)).limit(limit).all()


def get_chat_history_for_langchain(
    db: Session, 
    session_id: str, 
    limit: int = 20
) -> List[Dict[str, Any]]:
    """Get chat history formatted for LangChain memory."""
    messages = get_chat_messages(db, session_id, limit)
    
    # Convert to LangChain format (newest first, then reverse)
    history = []
    for msg in reversed(messages):
        if msg.role == "user":
            history.append({"role": "user", "content": msg.content})
        elif msg.role == "assistant":
            history.append({"role": "assistant", "content": msg.content})
        elif msg.role == "system":
            history.append({"role": "system", "content": msg.content})
    
    return history


def clear_chat_session(db: Session, session_id: str) -> bool:
    """Clear all messages for a chat session."""
    if not session_id:
        return False
    
    try:
        # Mark session as inactive
        session = get_chat_session(db, session_id)
        if session:
            session.is_active = False
            db.commit()
        
        # Delete all messages
        deleted_count = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).delete()
        
        db.commit()
        return deleted_count > 0
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Failed to clear chat session: {str(e)}")


def cleanup_old_chat_sessions(db: Session, days_old: int = 30) -> int:
    """Clean up old chat sessions and messages."""
    from datetime import datetime, timedelta
    
    cutoff_date = datetime.utcnow() - timedelta(days=days_old)
    
    # Find old sessions
    old_sessions = db.query(ChatSession).filter(
        ChatSession.updated_at < cutoff_date
    ).all()
    
    count = 0
    for session in old_sessions:
        try:
            # Delete messages first (cascade should handle this)
            session.is_active = False
            count += 1
        except Exception:
            pass
    
    db.commit()
    return count
