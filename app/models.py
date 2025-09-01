"""SQLAlchemy database models."""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, JSON, DECIMAL, Enum, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db import Base
import enum


class QuoteStatus(enum.Enum):
    """Quote status enumeration."""
    draft = "draft"
    sent = "sent"
    accepted = "accepted"


class Account(Base):
    """Account model."""
    __tablename__ = "accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    domain = Column(String)
    external_crm_ids = Column(JSON)
    confidence_score = Column(Float)
    
    # Relationships
    quotes = relationship("Quote", back_populates="account")


class Pricebook(Base):
    """Pricebook model."""
    __tablename__ = "pricebooks"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    currency = Column(String, nullable=False)
    is_default = Column(Boolean, default=False)
    
    # Relationships
    skus = relationship("Sku", back_populates="pricebook")
    quotes = relationship("Quote", back_populates="pricebook")


class Sku(Base):
    """SKU model."""
    __tablename__ = "skus"
    
    id = Column(Integer, primary_key=True, index=True)
    parent_sku_id = Column(Integer, ForeignKey("skus.id"))
    code = Column(String, nullable=False)
    name = Column(String, nullable=False)
    attributes = Column(JSON)
    pricebook_id = Column(Integer, ForeignKey("pricebooks.id"))
    unit_price = Column(DECIMAL(10, 2))
    
    # Relationships
    pricebook = relationship("Pricebook", back_populates="skus")
    parent_sku = relationship("Sku", remote_side=[id])
    child_skus = relationship("Sku", overlaps="parent_sku")
    quote_lines = relationship("QuoteLine", back_populates="sku")


class Quote(Base):
    """Quote model."""
    __tablename__ = "quotes"
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"))
    pricebook_id = Column(Integer, ForeignKey("pricebooks.id"))
    status = Column(Enum(QuoteStatus), default=QuoteStatus.draft)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    account = relationship("Account", back_populates="quotes")
    pricebook = relationship("Pricebook", back_populates="quotes")
    lines = relationship("QuoteLine", back_populates="quote")


class QuoteLine(Base):
    """Quote line item model."""
    __tablename__ = "quote_lines"
    
    id = Column(Integer, primary_key=True, index=True)
    quote_id = Column(Integer, ForeignKey("quotes.id"))
    sku_id = Column(Integer, ForeignKey("skus.id"))
    qty = Column(Integer, nullable=False)
    unit_price = Column(DECIMAL(10, 2))
    discount_pct = Column(Float, default=0.0)
    
    # Relationships
    quote = relationship("Quote", back_populates="lines")
    sku = relationship("Sku", back_populates="quote_lines")


class IdempotencyKey(Base):
    """Idempotency key model for preventing duplicate requests."""
    __tablename__ = "idempotency_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ChatSession(Base):
    """Chat session model for persistent conversation history."""
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    
    # Relationships
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    """Chat message model for storing conversation history."""
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("chat_sessions.session_id"), nullable=False)
    role = Column(String, nullable=False)  # 'user', 'assistant', 'system'
    content = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    message_metadata = Column(JSON)  # For storing additional info like tool calls, etc.
    
    # Relationships
    session = relationship("ChatSession", back_populates="messages")
    
    # Index for efficient querying
    __table_args__ = (
        Index('idx_session_role_created', 'session_id', 'role', 'created_at'),
    )
