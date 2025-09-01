#!/usr/bin/env python3
"""Seed demo data for Sales Quoting Engine - idempotent upserts."""

import os
import sys
from decimal import Decimal
from typing import Dict, Any, List
import json

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.models import Base, Account, Pricebook, Sku, Quote, QuoteLine, QuoteStatus
from app.db import get_db


def create_session():
    """Create database session."""
    engine = create_engine(settings.db_url)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def upsert_account(db, name: str, domain: str, confidence_score: float, external_crm_ids: List[str] = None) -> Account:
    """Upsert account by name."""
    external_crm_ids = external_crm_ids or []
    
    account = db.query(Account).filter(Account.name == name).first()
    if account:
        # Update existing
        account.domain = domain
        account.confidence_score = confidence_score
        account.external_crm_ids = json.dumps(external_crm_ids)
        return account
    else:
        # Create new
        account = Account(
            name=name,
            domain=domain,
            confidence_score=confidence_score,
            external_crm_ids=json.dumps(external_crm_ids)
        )
        db.add(account)
        db.flush()  # Get ID
        return account


def upsert_pricebook(db, name: str, currency: str, is_default: bool = False) -> Pricebook:
    """Upsert pricebook by name."""
    pricebook = db.query(Pricebook).filter(Pricebook.name == name).first()
    if pricebook:
        # Update existing
        pricebook.currency = currency
        pricebook.is_default = is_default
        return pricebook
    else:
        # Create new
        pricebook = Pricebook(
            name=name,
            currency=currency,
            is_default=is_default
        )
        db.add(pricebook)
        db.flush()  # Get ID
        return pricebook


def upsert_sku(db, code: str, name: str, pricebook_id: int, unit_price: Decimal, 
               parent_sku_id: int = None, attributes: Dict[str, Any] = None) -> Sku:
    """Upsert SKU by code and pricebook."""
    attributes = attributes or {}
    
    sku = db.query(Sku).filter(
        Sku.code == code,
        Sku.pricebook_id == pricebook_id
    ).first()
    
    if sku:
        # Update existing
        sku.name = name
        sku.unit_price = unit_price
        sku.parent_sku_id = parent_sku_id
        sku.attributes = json.dumps(attributes)
        return sku
    else:
        # Create new
        sku = Sku(
            code=code,
            name=name,
            pricebook_id=pricebook_id,
            unit_price=unit_price,
            parent_sku_id=parent_sku_id,
            attributes=json.dumps(attributes)
        )
        db.add(sku)
        db.flush()  # Get ID
        return sku


def seed_demo_quote(db, account_id: int, pricebook_id: int, widget_sku_id: int) -> Quote:
    """Create a demo quote if none exists."""
    existing = db.query(Quote).filter(Quote.account_id == account_id).first()
    if existing:
        return existing
    
    quote = Quote(
        account_id=account_id,
        pricebook_id=pricebook_id,
        status=QuoteStatus.draft
    )
    db.add(quote)
    db.flush()
    
    # Add a line item
    line = QuoteLine(
        quote_id=quote.id,
        sku_id=widget_sku_id,
        qty=5,
        unit_price=Decimal('10.00'),
        discount_pct=0.0
    )
    db.add(line)
    db.flush()
    
    return quote


def main():
    """Main seeding function."""
    print("🌱 Seeding demo data...")
    
    db = create_session()
    counts = {
        'accounts': 0,
        'pricebooks': 0,
        'skus': 0,
        'quotes': 0
    }
    
    try:
        # 1. Seed Accounts
        print("  📋 Seeding accounts...")
        acme_ltd = upsert_account(db, "Acme Ltd", "acme.com", 0.98)
        acme_uk = upsert_account(db, "Acme, Inc (UK)", "acme.co.uk", 0.96)
        edge_comm = upsert_account(db, "Edge Communications", "edge.com", 0.95)
        counts['accounts'] = 3
        
        # 2. Seed Pricebooks
        print("  💰 Seeding pricebooks...")
        pb_std = upsert_pricebook(db, "Standard", "USD", is_default=True)
        pb_eur = upsert_pricebook(db, "European", "EUR", is_default=False)
        counts['pricebooks'] = 2
        
        # 3. Seed SKUs with hierarchy
        print("  📦 Seeding SKUs...")
        
        # Bundle parent - Desktop Computer
        desktop_bundle = upsert_sku(
            db, "DESKTOP_BUNDLE", "Desktop Computer (Bundle)", 
            pb_std.id, Decimal('1200.00'), 
            attributes={"is_bundle": True, "bundle_type": "desktop"}
        )
        
        # Bundle children/options
        ssd_512 = upsert_sku(
            db, "SSD_512", "SSD 512GB (Required)", 
            pb_std.id, Decimal('150.00'), 
            parent_sku_id=desktop_bundle.id,
            attributes={"replaces": "HDD", "required": True}
        )
        
        optical_drive = upsert_sku(
            db, "OPTICAL_DRIVE", "Optical Drive (Required)", 
            pb_std.id, Decimal('50.00'), 
            parent_sku_id=desktop_bundle.id,
            attributes={"required": True}
        )
        
        laser_printer = upsert_sku(
            db, "LASER_PRINTER", "Laser Printer", 
            pb_std.id, Decimal('300.00'), 
            parent_sku_id=desktop_bundle.id,
            attributes={"required": False}
        )
        
        # Printer accessories (children of printer)
        toner_cartridge = upsert_sku(
            db, "TONER_CART", "Toner Cartridge (Required)", 
            pb_std.id, Decimal('80.00'), 
            parent_sku_id=laser_printer.id,
            attributes={"required": True}
        )
        
        high_cap_tray = upsert_sku(
            db, "TRAY_HIGHCAP", "High-Capacity Tray (Required)", 
            pb_std.id, Decimal('120.00'), 
            parent_sku_id=laser_printer.id,
            attributes={"required": True}
        )
        
        # Standalone products
        widget_std = upsert_sku(
            db, "WIDGET_STD", "Widget - Standard", 
            pb_std.id, Decimal('10.00')
        )
        
        vpn_license = upsert_sku(
            db, "VPN_LICENSE", "VPN License", 
            pb_std.id, Decimal('10.00'), 
            attributes={"billing": "per_month", "default_term_months": 36}
        )
        
        # EUR pricebook versions (mirror pricing in EUR)
        upsert_sku(db, "WIDGET_STD", "Widget - Standard", pb_eur.id, Decimal('9.00'))
        upsert_sku(db, "VPN_LICENSE", "VPN License", pb_eur.id, Decimal('9.00'), 
                  attributes={"billing": "per_month", "default_term_months": 36})
        
        counts['skus'] = 10
        
        # 4. Seed a demo quote
        print("  📋 Seeding demo quote...")
        demo_quote = seed_demo_quote(db, acme_ltd.id, pb_std.id, widget_std.id)
        counts['quotes'] = 1
        
        # Commit all changes
        db.commit()
        
        print("✅ Demo data seeded successfully!")
        print(f"   📋 Accounts: {counts['accounts']}")
        print(f"   💰 Pricebooks: {counts['pricebooks']}")
        print(f"   📦 SKUs: {counts['skus']}")
        print(f"   📋 Quotes: {counts['quotes']}")
        print(f"   🔗 Demo quote ID: {demo_quote.id}")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding data: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
