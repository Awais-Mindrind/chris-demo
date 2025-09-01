"""FastAPI application entry point."""
from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
import json
import uuid
import asyncio
import time
from datetime import datetime, timezone

from app.config import settings
from app.db import get_db
from app.agent import get_agent_for_session, process_message, process_message_stream, get_conversation_history, clear_conversation, get_session_stats
from app.crud import create_quote, get_quote, check_idempotency_key
from app.pdf import generate_quote_pdf
from app.schemas import (
    QuoteCreate, QuoteRead, QuoteLineCreate,
    ChatRequest, ChatResponse, CreateQuoteRequest, CreateQuoteResponse,
    QuoteDetailResponse, SessionHistoryResponse, SessionResponse, StatsResponse,
    ErrorResponse, SuccessResponse
)
from app.logging_conf import (
    setup_logging, get_trace_logger, log_endpoint_request, log_endpoint_response,
    log_idempotency_check, log_idempotency_duplicate, log_idempotency_success,
    log_session_created, log_session_retrieved, log_quote_created, log_pdf_generated,
    log_streaming_started, log_streaming_completed, log_error, log_tool_execution
)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def generate_session_id() -> str:
    """Generate a unique session ID."""
    return str(uuid.uuid4())


def validate_idempotency_key(key: Optional[str]) -> str:
    """Validate and return idempotency key."""
    if key is None:
        return str(uuid.uuid4())
    if not isinstance(key, str) or len(key.strip()) == 0:
        raise ValueError("Idempotency key must be a non-empty string")
    return key.strip()


# =============================================================================
# APPLICATION SETUP
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    setup_logging()
    print(f"Starting Sales Quoting Engine in {settings.app_env} mode")
    yield
    # Shutdown
    print("Shutting down Sales Quoting Engine")


app = FastAPI(
    title="Sales Quoting Engine",
    description="AI-powered sales quote creation system",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/public", StaticFiles(directory="public"), name="public")


# =============================================================================
# MIDDLEWARE
# =============================================================================

@app.middleware("http")
async def add_trace_id(request: Request, call_next):
    """Add trace ID to request for logging."""
    # Generate trace ID
    trace_id = str(uuid.uuid4())
    request.state.trace_id = trace_id
    
    # Add trace ID to response headers
    response = await call_next(request)
    response.headers["X-Trace-ID"] = trace_id
    
    return response


# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/healthz")
async def health_check():
    """Health check endpoint."""
    return {
        "ok": True,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.post("/chat")
async def chat_endpoint(
    request: ChatRequest,
    db: Session = Depends(get_db),
    http_request: Request = None
):
    """Chat endpoint for AI agent interaction."""
    start_time = time.time()
    trace_id = getattr(http_request.state, 'trace_id', 'unknown') if http_request else 'unknown'
    
    log_endpoint_request("/chat", "POST", trace_id, message_length=len(request.message))
    
    try:
        # Generate session ID if not provided
        session_id = request.session_id or generate_session_id()
        
        if not request.session_id:
            log_session_created(session_id, trace_id)
        else:
            log_session_retrieved(session_id, trace_id)
        
        # Process message with agent
        response = process_message(session_id, request.message, db)
        
        response_data = ChatResponse(
            response=response,
            session_id=session_id
        )
        
        latency_ms = (time.time() - start_time) * 1000
        log_endpoint_response("/chat", "POST", trace_id, 200, latency_ms, session_id=session_id)
        
        return response_data
        
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        log_error(e, "chat_endpoint", trace_id, message_length=len(request.message))
        log_endpoint_response("/chat", "POST", trace_id, 500, latency_ms)
        
        raise HTTPException(
            status_code=500,
            detail=f"Error processing chat message: {str(e)}"
        )


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest, db: Session = Depends(get_db), http_request: Request = None):
    """Chat endpoint with Server-Sent Events streaming."""
    start_time = time.time()
    trace_id = getattr(http_request.state, 'trace_id', 'unknown')
    
    log_endpoint_request("/chat/stream", "POST", trace_id, message_length=len(request.message))
    
    # Generate session ID if not provided
    session_id = request.session_id or generate_session_id()
    
    if not request.session_id:
        log_session_created(session_id, trace_id)
    else:
        log_session_retrieved(session_id, trace_id)
    
    log_streaming_started(session_id, trace_id)
    
    async def generate_stream():
        """Generate SSE stream with real LLM streaming."""
        try:
            # Send session ID
            yield f"event: session\ndata: {json.dumps({'session_id': session_id})}\n\n"
            
            # Process message with streaming agent
            async for chunk in process_message_stream(session_id, request.message, db):
                if chunk["type"] == "token":
                    # Stream individual tokens
                    yield f"event: token\ndata: {json.dumps({'chunk': chunk['content'], 'partial': chunk['partial']})}\n\n"
                
                elif chunk["type"] == "pdf_ready":
                    # Send PDF ready notification
                    yield f"event: pdf_ready\ndata: {json.dumps({'pdf_url': chunk['pdf_url'], 'quote_id': chunk['quote_id']})}\n\n"
                
                elif chunk["type"] == "done":
                    # Send completion event
                    done_data = {
                        "response": chunk["response"],
                        "session_id": chunk["session_id"]
                    }
                    if chunk.get("pdf_url"):
                        done_data["pdf_url"] = chunk["pdf_url"]
                    
                    yield f"event: done\ndata: {json.dumps(done_data)}\n\n"
            
        except Exception as e:
            error_data = {
                "error": "Processing failed",
                "message": str(e),
                "session_id": session_id
            }
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
            log_error(e, "chat_stream", trace_id, session_id=session_id)
        finally:
            latency_ms = (time.time() - start_time) * 1000
            log_streaming_completed(session_id, trace_id, latency_ms=latency_ms)
            log_endpoint_response("/chat/stream", "POST", trace_id, 200, latency_ms, session_id=session_id)
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )


@app.post("/actions/create_quote")
async def create_quote_endpoint(
    request: CreateQuoteRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    http_request: Request = None
):
    """Create quote endpoint with idempotency support."""
    start_time = time.time()
    trace_id = getattr(http_request.state, 'trace_id', 'unknown') if http_request else 'unknown'
    
    log_endpoint_request("/actions/create_quote", "POST", trace_id, 
                        account_id=request.account_id, 
                        pricebook_id=request.pricebook_id,
                        line_count=len(request.lines))
    
    try:
        # Validate idempotency key
        idempotency_key = validate_idempotency_key(request.idempotency_key)
        
        # Log idempotency check
        log_idempotency_check(idempotency_key, trace_id)
        
        # Check for existing quote with this idempotency key
        existing_quote_id = check_idempotency_key(db, idempotency_key)
        if existing_quote_id:
            log_idempotency_duplicate(idempotency_key, trace_id, quote_id=existing_quote_id)
            existing_quote = get_quote(db, existing_quote_id)
            if existing_quote:
                latency_ms = (time.time() - start_time) * 1000
                log_endpoint_response("/actions/create_quote", "POST", trace_id, 200, latency_ms,
                                    quote_id=existing_quote_id, idempotent=True)
                return CreateQuoteResponse(
                    quote_id=existing_quote.id,
                    status=existing_quote.status,
                    message=f"Quote already exists with ID {existing_quote.id} (idempotent)"
                )
        
        # Convert request to QuoteCreate schema
        quote_data = QuoteCreate(
            account_id=request.account_id,
            pricebook_id=request.pricebook_id,
            lines=[QuoteLineCreate(**line) for line in request.lines]
        )
        
        # Create quote using CRUD function with idempotency
        with log_tool_execution("create_quote", trace_id,
                                account_id=request.account_id,
                                pricebook_id=request.pricebook_id,
                                line_count=len(request.lines)) as logger:
            quote = create_quote(db, quote_data, idempotency_key)
        
        # Log successful quote creation
        log_quote_created(quote.id, request.account_id, trace_id,
                         pricebook_id=request.pricebook_id,
                         line_count=len(request.lines))
        
        # Log idempotency success
        log_idempotency_success(idempotency_key, trace_id, quote_id=quote.id)
        
        # Background task: Generate PDF
        background_tasks.add_task(generate_quote_pdf, quote.id)
        
        response_data = CreateQuoteResponse(
            quote_id=quote.id,
            status=quote.status,
            message=f"Quote created successfully with ID {quote.id}"
        )
        
        latency_ms = (time.time() - start_time) * 1000
        log_endpoint_response("/actions/create_quote", "POST", trace_id, 200, latency_ms,
                            quote_id=quote.id, idempotent=False)
        return response_data
        
    except ValueError as e:
        latency_ms = (time.time() - start_time) * 1000
        log_error(e, "create_quote_validation", trace_id,
                 account_id=request.account_id,
                 pricebook_id=request.pricebook_id)
        log_endpoint_response("/actions/create_quote", "POST", trace_id, 400, latency_ms)
        raise HTTPException(
            status_code=400,
            detail=f"Validation error: {str(e)}"
        )
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        log_error(e, "create_quote", trace_id,
                 account_id=request.account_id,
                 pricebook_id=request.pricebook_id)
        log_endpoint_response("/actions/create_quote", "POST", trace_id, 500, latency_ms)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/quotes/{quote_id}")
async def get_quote_endpoint(
    quote_id: int,
    db: Session = Depends(get_db)
):
    """Get quote by ID with all details."""
    
    try:
        # Get quote using CRUD function
        quote = get_quote(db, quote_id)
        
        if not quote:
            raise HTTPException(
                status_code=404,
                detail=f"Quote with ID {quote_id} not found"
            )
        
        # Convert to response format
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
        
        return QuoteDetailResponse(
            quote_id=quote.id,
            account_id=quote.account_id,
            pricebook_id=quote.pricebook_id,
            status=quote.status,
            created_at=quote.created_at.isoformat(),
            lines=lines,
            total_amount=total_amount
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving quote: {str(e)}"
        )


@app.get("/quotes/{quote_id}/pdf")
async def get_quote_pdf_endpoint(
    quote_id: int,
    db: Session = Depends(get_db)
):
    """Get quote PDF."""
    
    try:
        # Verify quote exists
        quote = get_quote(db, quote_id)
        if not quote:
            raise HTTPException(
                status_code=404,
                detail=f"Quote with ID {quote_id} not found"
            )
        
        # Generate PDF
        pdf_path = generate_quote_pdf(quote_id)
        
        # Return PDF file
        return FileResponse(
            path=pdf_path,
            media_type="application/pdf",
            filename=f"quote_{quote_id}.pdf"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating PDF: {str(e)}"
        )


# =============================================================================
# ADDITIONAL UTILITY ENDPOINTS
# =============================================================================

@app.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str):
    """Get conversation history for a session."""
    try:
        history = get_conversation_history(session_id)
        return SessionHistoryResponse(
            session_id=session_id,
            history=history
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving session history: {str(e)}"
        )


@app.delete("/sessions/{session_id}")
async def clear_session(session_id: str):
    """Clear conversation history for a session."""
    try:
        cleared = clear_conversation(session_id)
        return SessionResponse(
            session_id=session_id,
            cleared=cleared
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error clearing session: {str(e)}"
        )


@app.get("/stats")
async def get_stats():
    """Get application statistics."""
    try:
        stats = get_session_stats()
        return StatsResponse(
            sessions=stats,
            timestamp=datetime.now(timezone.utc)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving statistics: {str(e)}"
        )
