"""LangChain StructuredTools for database operations and PDF generation."""
from typing import List, Optional, Dict, Any, Union
from decimal import Decimal
from pydantic import BaseModel, Field, validator
from langchain_core.tools import StructuredTool
from sqlalchemy.orm import Session

from app.crud import (
    search_accounts, get_account, get_pricebooks, get_skus, 
    create_quote, get_quote
)
from app.logging_conf import log_tool_execution
from app.schemas import (
    QuoteCreate, QuoteLineCreate, AccountRead, PricebookRead, SkuRead,
    FindAccountInput, FindAccountOutput, ListPricebooksOutput, ListSkusOutput,
    CreateQuoteInput, CreateQuoteOutput, GetQuoteInput, GetQuoteOutput,
    RenderQuotePdfInput, RenderQuotePdfOutput, AccountCandidate, SkuFilters,
    QuoteLineInput, ErrorResponse
)
from app.pdf import generate_quote_pdf


# =============================================================================
# TOOL IMPLEMENTATIONS
# =============================================================================

def create_tools_with_db(db: Session) -> List[StructuredTool]:
    """Create tools with database session injected."""
    
    def find_account_tool(query: str) -> FindAccountOutput:
        """Find accounts by name or domain query."""
        try:
            print(f"DEBUG: find_account_tool called with query: '{query}'")
            if not query or not query.strip():
                print("DEBUG: Empty query, returning empty result")
                return FindAccountOutput(candidates=[], total_count=0)
            
            with log_tool_execution("find_account", None, query=query) as logger:
                print(f"DEBUG: Calling search_accounts with query: '{query.strip()}'")
                accounts = search_accounts(db, query.strip())
                print(f"DEBUG: search_accounts returned {len(accounts)} accounts")
            
            candidates = []
            for account in accounts:
                print(f"DEBUG: Processing account: {account.name} (ID: {account.id})")
                confidence = 0.5
                if account.name.lower() == query.lower():
                    confidence = 0.95
                elif account.name.lower().startswith(query.lower()):
                    confidence = 0.8
                elif query.lower() in account.name.lower():
                    confidence = 0.7
                
                if account.domain and query.lower() in account.domain.lower():
                    confidence = min(confidence + 0.1, 0.9)
                
                candidates.append(AccountCandidate(
                    account_id=account.id,
                    name=account.name,
                    domain=account.domain,
                    confidence_score=confidence
                ))
            
            candidates.sort(key=lambda x: x.confidence_score or 0, reverse=True)
            print(f"DEBUG: Returning {len(candidates)} candidates")
            return FindAccountOutput(candidates=candidates, total_count=len(candidates))
            
        except Exception as e:
            print(f"DEBUG: Exception in find_account_tool: {e}")
            return FindAccountOutput(candidates=[], total_count=0)
    
    def list_pricebooks_tool() -> ListPricebooksOutput:
        """List all available pricebooks."""
        try:
            with log_tool_execution("list_pricebooks", None) as logger:
                pricebooks = get_pricebooks(db)
            
            pricebook_list = []
            for pricebook in pricebooks:
                pricebook_list.append({
                    "id": pricebook.id,
                    "name": pricebook.name,
                    "currency": pricebook.currency,
                    "is_default": pricebook.is_default
                })
            
            return ListPricebooksOutput(pricebooks=pricebook_list, total_count=len(pricebook_list))
            
        except Exception as e:
            return ListPricebooksOutput(pricebooks=[], total_count=0)
    
    def list_skus_tool(
        name: Optional[str] = None,
        code: Optional[str] = None,
        pricebook_id: Optional[int] = None,
        parent_sku_id: Optional[int] = None
    ) -> ListSkusOutput:
        """List SKUs with optional filters."""
        try:
            filters = {}
            if name:
                filters["name_filter"] = name
            if code:
                filters["code_filter"] = code
            if pricebook_id:
                filters["pricebook_id"] = pricebook_id
            if parent_sku_id:
                filters["parent_sku_id"] = parent_sku_id
            
            with log_tool_execution("list_skus", None, **filters) as logger:
                skus = get_skus(db, **filters)
            
            # Get pricebook info for better context
            pricebooks = {pb.id: pb for pb in get_pricebooks(db)}
            
            sku_list = []
            for sku in skus:
                pricebook = pricebooks.get(sku.pricebook_id)
                sku_info = {
                    "id": sku.id,
                    "code": sku.code,
                    "name": sku.name,
                    "pricebook_id": sku.pricebook_id,
                    "pricebook_name": pricebook.name if pricebook else "Unknown",
                    "currency": pricebook.currency if pricebook else "Unknown",
                    "unit_price": float(sku.unit_price),
                    "parent_sku_id": sku.parent_sku_id,
                    "attributes": sku.attributes
                }
                sku_list.append(sku_info)
            
            # If we have multiple SKUs with same code, add context
            if len(sku_list) > 1 and any(sku.get('code') for sku in sku_list):
                codes = [sku['code'] for sku in sku_list if sku.get('code')]
                if len(set(codes)) == 1:  # All same code
                    code = codes[0]
                    # Group by pricebook for better presentation
                    grouped = {}
                    for sku in sku_list:
                        pb_key = f"{sku['pricebook_name']} ({sku['currency']})"
                        if pb_key not in grouped:
                            grouped[pb_key] = []
                        grouped[pb_key].append(sku)
                    
                    # Add context to each SKU
                    for sku in sku_list:
                        pb_key = f"{sku['pricebook_name']} ({sku['currency']})"
                        sku['context'] = f"Available in {pb_key} - Price: {sku['currency']} {sku['unit_price']}"
            
            return ListSkusOutput(skus=sku_list, total_count=len(sku_list))
            
        except Exception as e:
            return ListSkusOutput(skus=[], total_count=0)
    
    def create_quote_tool(
        account_id: int,
        pricebook_id: int,
        lines: List[Dict[str, Any]],
        idempotency_key: Optional[str] = None
    ) -> CreateQuoteOutput:
        """Create a new quote with line items."""
        try:
            # Validate inputs
            if not lines or len(lines) == 0:
                return CreateQuoteOutput(
                    success=False,
                    error="At least one line item is required"
                )
            
            # Pre-validate SKUs exist in the specified pricebook
            sku_ids = [line.get('sku_id') for line in lines if line.get('sku_id')]
            if sku_ids:
                # Check if SKUs exist in the specified pricebook
                skus_in_pricebook = get_skus(db, pricebook_id=pricebook_id)
                sku_ids_in_pricebook = {sku.id for sku in skus_in_pricebook}
                
                invalid_skus = [sku_id for sku_id in sku_ids if sku_id not in sku_ids_in_pricebook]
                if invalid_skus:
                    # Find where these SKUs do exist
                    all_skus = get_skus(db)
                    sku_pricebook_map = {}
                    for sku in all_skus:
                        if sku.id in invalid_skus:
                            sku_pricebook_map[sku.id] = sku.pricebook_id
                    
                    # Get pricebook names for better error message
                    pricebooks = {pb.id: pb.name for pb in get_pricebooks(db)}
                    target_pricebook = pricebooks.get(pricebook_id, f"Pricebook {pricebook_id}")
                    
                    error_msg = f"SKU(s) {invalid_skus} do not exist in {target_pricebook}. "
                    if sku_pricebook_map:
                        suggestions = []
                        for sku_id, pb_id in sku_pricebook_map.items():
                            pb_name = pricebooks.get(pb_id, f"Pricebook {pb_id}")
                            suggestions.append(f"SKU {sku_id} exists in {pb_name}")
                        error_msg += f"Available in: {', '.join(suggestions)}"
                    
                    raise ValueError(error_msg)
            
            # Convert lines to QuoteLineCreate objects
            quote_lines = []
            for line in lines:
                # Handle field name mapping (quantity -> qty)
                if 'quantity' in line:
                    line['qty'] = line.pop('quantity')
                quote_lines.append(QuoteLineCreate(**line))
            
            # Create quote data
            quote_data = QuoteCreate(
                account_id=account_id,
                pricebook_id=pricebook_id,
                lines=quote_lines
            )
            
            with log_tool_execution("create_quote", None, 
                                   account_id=account_id,
                                   pricebook_id=pricebook_id,
                                   line_count=len(lines)) as logger:
                quote = create_quote(db, quote_data, idempotency_key)
            
            return CreateQuoteOutput(
                quote_id=quote.id,
                status=quote.status if isinstance(quote.status, str) else quote.status.value,
                total_lines=len(quote.lines)
            )
            
        except Exception as e:
            # For errors, we need to return a valid CreateQuoteOutput
            # Since the schema requires quote_id, status, and total_lines,
            # we'll raise the exception instead of returning an error response
            raise ValueError(f"Failed to create quote: {str(e)}")
    
    def get_quote_tool(quote_id: int) -> GetQuoteOutput:
        """Get quote details by ID."""
        try:
            with log_tool_execution("get_quote", None, quote_id=quote_id) as logger:
                quote = get_quote(db, quote_id)
            
            if not quote:
                # For missing quotes, raise an exception instead of returning invalid schema
                raise ValueError(f"Quote with ID {quote_id} not found")
            
            # Calculate totals
            lines = []
            total_amount = 0.0
            
            for line in quote.lines:
                line_total = float(line.unit_price or 0) * line.qty * (1 - line.discount_pct)
                total_amount += line_total
                
                lines.append({
                    "id": line.id,
                    "sku_id": line.sku_id,
                    "qty": line.qty,
                    "unit_price": float(line.unit_price) if line.unit_price else None,
                    "discount_pct": line.discount_pct,
                    "line_total": line_total
                })
            
            return GetQuoteOutput(
                quote_id=quote.id,
                account_id=quote.account_id,
                pricebook_id=quote.pricebook_id,
                status=quote.status if isinstance(quote.status, str) else quote.status.value,
                created_at=quote.created_at.isoformat(),
                lines=lines,
                total_amount=total_amount
            )
            
        except Exception as e:
            # For any errors, raise the exception instead of returning invalid schema
            raise ValueError(f"Failed to get quote: {str(e)}")
    
    def render_quote_pdf_tool(quote_id: int) -> RenderQuotePdfOutput:
        """Generate PDF for a quote."""
        try:
            # Verify quote exists
            quote = get_quote(db, quote_id)
            if not quote:
                raise ValueError(f"Quote with ID {quote_id} not found")
            
            # Generate PDF
            pdf_path = generate_quote_pdf(quote_id)
            
            # Construct PDF URL
            pdf_url = f"/quotes/{quote_id}/pdf"
            
            return RenderQuotePdfOutput(
                quote_id=quote_id,
                pdf_url=pdf_url,
                status="generated"
            )
            
        except Exception as e:
            raise ValueError(f"Failed to generate PDF: {str(e)}")
    
    # Create StructuredTool instances
    tools = [
        StructuredTool.from_function(
            func=find_account_tool,
            name="find_account",
            description="Search for accounts by name or domain. Returns candidates with confidence scores."
        ),
        StructuredTool.from_function(
            func=list_pricebooks_tool,
            name="list_pricebooks", 
            description="List all available pricebooks with their currencies and default status."
        ),
        StructuredTool.from_function(
            func=list_skus_tool,
            name="list_skus",
            description="Search for SKUs/products with optional filters (name, code, pricebook_id, parent_sku_id)."
        ),
        StructuredTool.from_function(
            func=create_quote_tool,
            name="create_quote",
            description="Create a new quote with account_id, pricebook_id, and line items. Supports idempotency_key."
        ),
        StructuredTool.from_function(
            func=get_quote_tool,
            name="get_quote", 
            description="Get complete quote details including line items and totals by quote_id."
        ),
        StructuredTool.from_function(
            func=render_quote_pdf_tool,
            name="render_quote_pdf",
            description="Generate PDF document for a quote and return the download URL."
        )
    ]
    
    return tools


# =============================================================================
# TOOL REGISTRY (DEPRECATED)
# =============================================================================

def get_all_tools() -> List[StructuredTool]:
    """Get all tools for the agent.
    
    Note: This function is deprecated. Use create_tools_with_db(db) instead
    to get tools with database session injected.
    """
    # This function is kept for backward compatibility but should not be used
    # Tools need database session to function properly
    raise NotImplementedError("Use create_tools_with_db(db) to get tools with database session")


def get_tool_by_name(name: str) -> Optional[StructuredTool]:
    """Get a specific tool by name.
    
    Note: This function is deprecated. Use create_tools_with_db(db) instead.
    """
    raise NotImplementedError("Use create_tools_with_db(db) to get tools with database session")
