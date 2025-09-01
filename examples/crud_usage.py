#!/usr/bin/env python3
"""Example usage of CRUD functions."""
from decimal import Decimal
from app.crud import (
    create_account, get_account, search_accounts,
    create_pricebook, get_pricebook, get_default_pricebook,
    create_sku, get_sku, search_skus,
    create_quote, get_quote, update_quote_status
)
from app.schemas import (
    AccountCreate, PricebookCreate, SkuCreate, QuoteCreate, QuoteLineCreate
)
from app.models import QuoteStatus


def example_account_operations(db_session):
    """Example of account CRUD operations."""
    print("=== Account Operations ===")
    
    # Create accounts
    account1 = create_account(db_session, AccountCreate(
        name="Acme Corporation",
        domain="acme.com",
        confidence_score=0.95
    ))
    print(f"Created account: {account1.name} (ID: {account1.id})")
    
    account2 = create_account(db_session, AccountCreate(
        name="Tech Solutions Inc",
        domain="techsolutions.com",
        confidence_score=0.88
    ))
    print(f"Created account: {account2.name} (ID: {account2.id})")
    
    # Search accounts
    search_results = search_accounts(db_session, "tech")
    print(f"Search results for 'tech': {len(search_results)} accounts found")
    
    # Get account by ID
    retrieved_account = get_account(db_session, account1.id)
    print(f"Retrieved account: {retrieved_account.name}")


def example_pricebook_operations(db_session):
    """Example of pricebook CRUD operations."""
    print("\n=== Pricebook Operations ===")
    
    # Create pricebooks
    usd_pricebook = create_pricebook(db_session, PricebookCreate(
        name="USD Standard",
        currency="USD",
        is_default=True
    ))
    print(f"Created pricebook: {usd_pricebook.name} ({usd_pricebook.currency})")
    
    eur_pricebook = create_pricebook(db_session, PricebookCreate(
        name="EUR Standard",
        currency="EUR",
        is_default=False
    ))
    print(f"Created pricebook: {eur_pricebook.name} ({eur_pricebook.currency})")
    
    # Get default pricebook
    default_pb = get_default_pricebook(db_session)
    print(f"Default pricebook: {default_pb.name}")


def example_sku_operations(db_session):
    """Example of SKU CRUD operations."""
    print("\n=== SKU Operations ===")
    
    # Get default pricebook for SKUs
    default_pb = get_default_pricebook(db_session)
    
    # Create SKUs
    sku1 = create_sku(db_session, SkuCreate(
        code="LAPTOP-001",
        name="Premium Laptop",
        pricebook_id=default_pb.id,
        unit_price=Decimal("1299.99"),
        attributes={"category": "electronics", "brand": "TechCorp"}
    ))
    print(f"Created SKU: {sku1.code} - {sku1.name} (${sku1.unit_price})")
    
    sku2 = create_sku(db_session, SkuCreate(
        code="MOUSE-001",
        name="Wireless Mouse",
        pricebook_id=default_pb.id,
        unit_price=Decimal("49.99"),
        attributes={"category": "accessories", "wireless": True}
    ))
    print(f"Created SKU: {sku2.code} - {sku2.name} (${sku2.unit_price})")
    
    # Search SKUs
    search_results = search_skus(db_session, "laptop")
    print(f"Search results for 'laptop': {len(search_results)} SKUs found")


def example_quote_operations(db_session):
    """Example of quote CRUD operations."""
    print("\n=== Quote Operations ===")
    
    # Get required entities
    account = get_account(db_session, 1)  # Assuming account with ID 1 exists
    pricebook = get_default_pricebook(db_session)
    sku1 = get_sku(db_session, 1)  # Assuming SKU with ID 1 exists
    sku2 = get_sku(db_session, 2)  # Assuming SKU with ID 2 exists
    
    if not all([account, pricebook, sku1, sku2]):
        print("Required entities not found. Please create accounts and SKUs first.")
        return
    
    # Create quote
    quote = create_quote(db_session, QuoteCreate(
        account_id=account.id,
        pricebook_id=pricebook.id,
        lines=[
            QuoteLineCreate(
                sku_id=sku1.id,
                qty=1,
                discount_pct=0.05  # 5% discount
            ),
            QuoteLineCreate(
                sku_id=sku2.id,
                qty=2,
                discount_pct=0.0  # No discount
            )
        ]
    ))
    
    print(f"Created quote: ID {quote.id} for {account.name}")
    print(f"Status: {quote.status}")
    print(f"Line items: {len(quote.lines)}")
    
    # Update quote status
    updated_quote = update_quote_status(db_session, quote.id, QuoteStatus.sent)
    print(f"Updated quote status to: {updated_quote.status}")


def main():
    """Main function to run examples."""
    print("CRUD Operations Examples")
    print("=" * 50)
    
    # Note: This is just a demonstration of the API
    # In a real application, you would use these functions with actual database sessions
    print("This file demonstrates the CRUD function APIs.")
    print("To use these functions, you need a database session from app.db.get_db()")
    print("\nExample usage in your application:")
    print("""
    from app.db import get_db
    from app.crud import create_account
    
    db = next(get_db())
    try:
        account = create_account(db, AccountCreate(name="Test Company"))
        print(f"Created account: {account.name}")
    finally:
        db.close()
    """)


if __name__ == "__main__":
    main()
