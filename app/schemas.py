"""Pydantic models for API input/output validation."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime


# =============================================================================
# BASE SCHEMAS
# =============================================================================

class BaseResponse(BaseModel):
    """Base response schema with common fields."""
    model_config = ConfigDict(from_attributes=True)


class ErrorResponse(BaseModel):
    """Standard error response schema."""
    error: str = Field(description="Error type/code")
    message: str = Field(description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(description="Additional error details", default=None)
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")


class SuccessResponse(BaseModel):
    """Standard success response schema."""
    message: str = Field(description="Success message")
    data: Optional[Dict[str, Any]] = Field(description="Response data", default=None)
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


# =============================================================================
# ACCOUNT SCHEMAS
# =============================================================================

class AccountBase(BaseModel):
    """Base account schema."""
    name: str = Field(description="Account name")
    domain: Optional[str] = Field(description="Account domain", default=None)
    external_crm_ids: Optional[Dict[str, Any]] = Field(description="External CRM identifiers", default=None)
    confidence_score: Optional[float] = Field(description="Confidence score", ge=0.0, le=1.0, default=None)


class AccountCreate(AccountBase):
    """Schema for creating an account."""
    pass


class AccountRead(AccountBase, BaseResponse):
    """Schema for reading an account."""
    id: int = Field(description="Account identifier")
    
    # Override external_crm_ids to handle JSON string from database
    external_crm_ids: Optional[Union[Dict[str, Any], str]] = Field(description="External CRM identifiers", default=None)


class AccountCandidate(BaseModel):
    """Account search result candidate."""
    account_id: int = Field(description="Account identifier")
    name: str = Field(description="Account name")
    domain: Optional[str] = Field(description="Account domain", default=None)
    confidence_score: Optional[float] = Field(description="Confidence score", ge=0.0, le=1.0, default=None)


# =============================================================================
# PRICEBOOK SCHEMAS
# =============================================================================

class PricebookBase(BaseModel):
    """Base pricebook schema."""
    name: str = Field(description="Pricebook name")
    currency: str = Field(description="Currency code (e.g., USD, EUR)")
    is_default: bool = Field(description="Whether this is the default pricebook", default=False)


class PricebookCreate(PricebookBase):
    """Schema for creating a pricebook."""
    pass


class PricebookRead(PricebookBase, BaseResponse):
    """Schema for reading a pricebook."""
    id: int = Field(description="Pricebook identifier")


# =============================================================================
# SKU SCHEMAS
# =============================================================================

class SkuBase(BaseModel):
    """Base SKU schema."""
    code: str = Field(description="SKU code")
    name: str = Field(description="SKU name")
    pricebook_id: int = Field(description="Pricebook identifier")
    unit_price: Decimal = Field(description="Unit price", ge=0)
    parent_sku_id: Optional[int] = Field(description="Parent SKU identifier", default=None)
    attributes: Optional[Dict[str, Any]] = Field(description="Additional SKU attributes", default=None)


class SkuCreate(SkuBase):
    """Schema for creating a SKU."""
    pass


class SkuRead(SkuBase, BaseResponse):
    """Schema for reading a SKU."""
    id: int = Field(description="SKU identifier")
    
    # Override attributes to handle JSON string from database
    attributes: Optional[Union[Dict[str, Any], str]] = Field(description="Additional SKU attributes", default=None)


# =============================================================================
# QUOTE LINE SCHEMAS
# =============================================================================

class QuoteLineBase(BaseModel):
    """Base quote line schema."""
    sku_id: int = Field(description="SKU identifier")
    qty: int = Field(description="Quantity", ge=1)
    unit_price: Optional[Decimal] = Field(description="Unit price", ge=0, default=None)
    discount_pct: float = Field(description="Discount percentage", ge=0.0, lt=1.0, default=0.0)


class QuoteLineCreate(QuoteLineBase):
    """Schema for creating a quote line."""
    pass


class QuoteLineRead(QuoteLineBase, BaseResponse):
    """Schema for reading a quote line."""
    id: int = Field(description="Quote line identifier")
    quote_id: int = Field(description="Quote identifier")


# =============================================================================
# QUOTE SCHEMAS
# =============================================================================

class QuoteBase(BaseModel):
    """Base quote schema."""
    account_id: int = Field(description="Account identifier")
    pricebook_id: int = Field(description="Pricebook identifier")


class QuoteCreate(QuoteBase):
    """Schema for creating a quote."""
    lines: List[QuoteLineCreate] = Field(description="Quote line items", min_length=1)


class QuoteRead(QuoteBase, BaseResponse):
    """Schema for reading a quote."""
    id: int = Field(description="Quote identifier")
    status: str = Field(description="Quote status")
    created_at: datetime = Field(description="Creation timestamp")
    lines: List[QuoteLineRead] = Field(description="Quote line items")


# =============================================================================
# API REQUEST/RESPONSE SCHEMAS
# =============================================================================

class ChatRequest(BaseModel):
    """Chat request schema."""
    message: str = Field(description="User message")
    session_id: Optional[str] = Field(description="Session identifier", default=None)


class ChatResponse(BaseModel):
    """Chat response schema."""
    response: str = Field(description="AI response")
    session_id: str = Field(description="Session identifier")


class CreateQuoteRequest(BaseModel):
    """Create quote request schema."""
    account_id: int = Field(description="Account identifier")
    pricebook_id: int = Field(description="Pricebook identifier")
    lines: List[Dict[str, Any]] = Field(description="Quote line items", min_length=1)
    idempotency_key: Optional[str] = Field(description="Idempotency key", default=None)


class CreateQuoteResponse(BaseModel):
    """Create quote response schema."""
    quote_id: int = Field(description="Quote identifier")
    status: str = Field(description="Quote status")
    message: str = Field(description="Response message")


class QuoteDetailResponse(BaseModel):
    """Quote detail response schema."""
    quote_id: int = Field(description="Quote identifier")
    account_id: int = Field(description="Account identifier")
    pricebook_id: int = Field(description="Pricebook identifier")
    status: str = Field(description="Quote status")
    created_at: str = Field(description="Creation timestamp")
    lines: List[Dict[str, Any]] = Field(description="Quote line items")
    total_amount: float = Field(description="Total quote amount")


class SessionHistoryResponse(BaseModel):
    """Session history response schema."""
    session_id: str = Field(description="Session identifier")
    history: List[Dict[str, Any]] = Field(description="Conversation history")


class SessionResponse(BaseModel):
    """Session response schema."""
    session_id: str = Field(description="Session identifier")
    cleared: bool = Field(description="Whether session was cleared")


class StatsResponse(BaseModel):
    """Stats response schema."""
    sessions: Dict[str, Any] = Field(description="Session statistics")
    timestamp: datetime = Field(description="Stats timestamp")


# =============================================================================
# TOOL SCHEMAS (for LangChain tools)
# =============================================================================

class FindAccountInput(BaseModel):
    """Input for account search."""
    query: str = Field(description="Search query for account name or domain")


class FindAccountOutput(BaseModel):
    """Output for account search."""
    candidates: List[AccountCandidate] = Field(description="List of matching accounts")
    total_count: int = Field(description="Total number of matches found")


class ListPricebooksOutput(BaseModel):
    """Output for pricebook listing."""
    pricebooks: List[Dict[str, Any]] = Field(description="List of available pricebooks")
    total_count: int = Field(description="Total number of pricebooks")


class SkuFilters(BaseModel):
    """Filters for SKU listing."""
    name: Optional[str] = Field(description="Filter by SKU name (partial match)", default=None)
    code: Optional[str] = Field(description="Filter by SKU code (partial match)", default=None)
    pricebook_id: Optional[int] = Field(description="Filter by pricebook ID", default=None)
    parent_sku_id: Optional[int] = Field(description="Filter by parent SKU ID", default=None)


class ListSkusOutput(BaseModel):
    """Output for SKU listing."""
    skus: List[Dict[str, Any]] = Field(description="List of matching SKUs")
    total_count: int = Field(description="Total number of matching SKUs")


class QuoteLineInput(BaseModel):
    """Input for quote line creation."""
    sku_id: int = Field(description="SKU identifier")
    qty: int = Field(description="Quantity", ge=1)
    unit_price: Optional[Decimal] = Field(description="Unit price", ge=0, default=None)
    discount_pct: float = Field(description="Discount percentage", ge=0.0, lt=1.0, default=0.0)


class CreateQuoteInput(BaseModel):
    """Input for quote creation."""
    account_id: int = Field(description="Account identifier")
    pricebook_id: int = Field(description="Pricebook identifier")
    lines: List[QuoteLineInput] = Field(description="List of quote line items", min_length=1)
    idempotency_key: Optional[str] = Field(description="Idempotency key", default=None)


class CreateQuoteOutput(BaseModel):
    """Output for quote creation."""
    quote_id: int = Field(description="Created quote identifier")
    status: str = Field(description="Quote status")
    total_lines: int = Field(description="Number of line items in the quote")


class GetQuoteInput(BaseModel):
    """Input for quote retrieval."""
    quote_id: int = Field(description="Quote identifier")


class GetQuoteOutput(BaseModel):
    """Output for quote retrieval."""
    quote_id: int = Field(description="Quote identifier")
    account_id: int = Field(description="Account identifier")
    pricebook_id: int = Field(description="Pricebook identifier")
    status: str = Field(description="Quote status")
    created_at: str = Field(description="Quote creation timestamp")
    lines: List[Dict[str, Any]] = Field(description="Quote line items")
    total_amount: Decimal = Field(description="Total quote amount")


class RenderQuotePdfInput(BaseModel):
    """Input for PDF generation."""
    quote_id: int = Field(description="Quote identifier")


class RenderQuotePdfOutput(BaseModel):
    """Output for PDF generation."""
    quote_id: int = Field(description="Quote identifier")
    pdf_url: str = Field(description="URL to the generated PDF")
    status: str = Field(description="PDF generation status")
