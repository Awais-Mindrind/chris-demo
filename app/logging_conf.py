"""Structured logging configuration."""
import logging
import sys
import json
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from contextlib import contextmanager
from functools import wraps
import traceback

from app.config import settings


class StructuredFormatter(logging.Formatter):
    """Structured JSON formatter for production logging."""
    
    def format(self, record):
        """Format log record as structured JSON."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add trace_id if available
        if hasattr(record, 'trace_id'):
            log_entry['trace_id'] = record.trace_id
        
        # Add tool information if available
        if hasattr(record, 'tool_name'):
            log_entry['tool_name'] = record.tool_name
        
        # Add latency if available
        if hasattr(record, 'latency_ms'):
            log_entry['latency_ms'] = record.latency_ms
        
        # Add status if available
        if hasattr(record, 'status'):
            log_entry['status'] = record.status
        
        # Add extra fields
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        return json.dumps(log_entry)


class HumanReadableFormatter(logging.Formatter):
    """Human readable formatter for development logging."""
    
    def format(self, record):
        """Format log record for human readability."""
        # Base format
        formatted = f"[{record.levelname}] {record.getMessage()}"
        
        # Add trace_id if available
        if hasattr(record, 'trace_id'):
            formatted += f" [trace_id={record.trace_id}]"
        
        # Add tool information if available
        if hasattr(record, 'tool_name'):
            formatted += f" [tool={record.tool_name}]"
        
        # Add latency if available
        if hasattr(record, 'latency_ms'):
            formatted += f" [latency={record.latency_ms}ms]"
        
        # Add status if available
        if hasattr(record, 'status'):
            formatted += f" [status={record.status}]"
        
        # Add extra fields
        if hasattr(record, 'extra_fields'):
            for key, value in record.extra_fields.items():
                formatted += f" [{key}={value}]"
        
        return formatted


class TraceLogger:
    """Logger with trace ID support and structured logging."""
    
    def __init__(self, name: str, trace_id: Optional[str] = None):
        self.logger = logging.getLogger(name)
        self.trace_id = trace_id or str(uuid.uuid4())
    
    def _log_with_context(self, level: int, message: str, **kwargs):
        """Log with trace context and additional fields."""
        extra = {
            'trace_id': self.trace_id,
            **kwargs
        }
        self.logger.log(level, message, extra=extra)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with context."""
        self._log_with_context(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message with context."""
        self._log_with_context(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with context."""
        self._log_with_context(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message with context."""
        self._log_with_context(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message with context."""
        self._log_with_context(logging.CRITICAL, message, **kwargs)
    
    def exception(self, message: str, **kwargs):
        """Log exception with traceback."""
        extra = {
            'trace_id': self.trace_id,
            'exc_info': True,
            **kwargs
        }
        self.logger.exception(message, extra=extra)


def setup_logging():
    """Configure application logging."""
    # Determine formatter based on environment
    if settings.app_env == "production":
        formatter = StructuredFormatter()
    else:
        formatter = HumanReadableFormatter()
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))
    root_logger.addHandler(console_handler)
    
    # Set specific logger levels
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.INFO)
    
    # Create application logger
    app_logger = logging.getLogger("sales_quoting_engine")
    app_logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    logging.info("Logging configured", extra={
        'app_env': settings.app_env,
        'log_level': settings.log_level
    })


def get_trace_logger(name: str, trace_id: Optional[str] = None) -> TraceLogger:
    """Get a logger with trace ID support."""
    return TraceLogger(name, trace_id)


@contextmanager
def log_tool_execution(tool_name: str, trace_id: Optional[str] = None, **context):
    """Context manager for logging tool execution with timing."""
    logger = get_trace_logger(f"tool.{tool_name}", trace_id)
    start_time = time.time()
    
    try:
        logger.info(f"Starting {tool_name}", tool_name=tool_name, status="started", **context)
        yield logger
        latency_ms = (time.time() - start_time) * 1000
        logger.info(f"Completed {tool_name}", 
                   tool_name=tool_name, 
                   status="success", 
                   latency_ms=round(latency_ms, 2),
                   **context)
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        logger.error(f"Failed {tool_name}: {str(e)}", 
                    tool_name=tool_name, 
                    status="failed", 
                    latency_ms=round(latency_ms, 2),
                    error_type=type(e).__name__,
                    **context)
        raise


def log_endpoint_request(endpoint: str, method: str, trace_id: str, **context):
    """Log endpoint request."""
    logger = get_trace_logger("endpoint", trace_id)
    logger.info(f"{method} {endpoint}", 
               endpoint=endpoint, 
               method=method, 
               status="request_received",
               **context)


def log_endpoint_response(endpoint: str, method: str, trace_id: str, status_code: int, latency_ms: float, **context):
    """Log endpoint response."""
    logger = get_trace_logger("endpoint", trace_id)
    status = "success" if 200 <= status_code < 400 else "error"
    logger.info(f"{method} {endpoint} - {status_code}", 
               endpoint=endpoint, 
               method=method, 
               status_code=status_code,
               status=status,
               latency_ms=round(latency_ms, 2),
               **context)


def log_idempotency_check(idempotency_key: str, trace_id: str, **context):
    """Log idempotency key check."""
    logger = get_trace_logger("idempotency", trace_id)
    logger.info(f"Checking idempotency key: {idempotency_key[:8]}...", 
               idempotency_key_prefix=idempotency_key[:8],
               status="checking",
               **context)


def log_idempotency_duplicate(idempotency_key: str, trace_id: str, **context):
    """Log duplicate idempotency key detection."""
    logger = get_trace_logger("idempotency", trace_id)
    logger.warning(f"Duplicate idempotency key detected: {idempotency_key[:8]}...", 
                  idempotency_key_prefix=idempotency_key[:8],
                  status="duplicate_detected",
                  **context)


def log_idempotency_success(idempotency_key: str, trace_id: str, **context):
    """Log successful idempotency key processing."""
    logger = get_trace_logger("idempotency", trace_id)
    logger.info(f"Idempotency key processed successfully: {idempotency_key[:8]}...", 
               idempotency_key_prefix=idempotency_key[:8],
               status="success",
               **context)


def log_session_created(session_id: str, trace_id: str, **context):
    """Log session creation."""
    logger = get_trace_logger("session", trace_id)
    logger.info(f"Session created: {session_id}", 
               session_id=session_id,
               status="created",
               **context)


def log_session_retrieved(session_id: str, trace_id: str, **context):
    """Log session retrieval."""
    logger = get_trace_logger("session", trace_id)
    logger.info(f"Session retrieved: {session_id}", 
               session_id=session_id,
               status="retrieved",
               **context)


def log_quote_created(quote_id: int, account_id: int, trace_id: str, **context):
    """Log quote creation."""
    logger = get_trace_logger("quote", trace_id)
    logger.info(f"Quote created: {quote_id} for account {account_id}", 
               quote_id=quote_id,
               account_id=account_id,
               status="created",
               **context)


def log_pdf_generated(quote_id: int, pdf_path: str, trace_id: str, **context):
    """Log PDF generation."""
    logger = get_trace_logger("pdf", trace_id)
    logger.info(f"PDF generated for quote {quote_id}: {pdf_path}", 
               quote_id=quote_id,
               pdf_path=pdf_path,
               status="generated",
               **context)


def log_streaming_started(session_id: str, trace_id: str, **context):
    """Log streaming session start."""
    logger = get_trace_logger("streaming", trace_id)
    logger.info(f"Streaming started for session {session_id}", 
               session_id=session_id,
               status="started",
               **context)


def log_streaming_completed(session_id: str, trace_id: str, **context):
    """Log streaming session completion."""
    logger = get_trace_logger("streaming", trace_id)
    logger.info(f"Streaming completed for session {session_id}", 
               session_id=session_id,
               status="completed",
               **context)


def log_error(error: Exception, context: str, trace_id: str, **extra_context):
    """Log error with context."""
    logger = get_trace_logger("error", trace_id)
    logger.error(f"Error in {context}: {str(error)}", 
                error_type=type(error).__name__,
                error_message=str(error),
                context=context,
                status="error",
                **extra_context)


# Convenience function for decorators
def log_function_call(func_name: str, trace_id: Optional[str] = None):
    """Decorator to log function calls with timing."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_trace_logger(f"function.{func_name}", trace_id)
            start_time = time.time()
            
            try:
                logger.info(f"Calling {func_name}", 
                           function=func_name, 
                           status="started")
                result = func(*args, **kwargs)
                latency_ms = (time.time() - start_time) * 1000
                logger.info(f"Completed {func_name}", 
                           function=func_name, 
                           status="success",
                           latency_ms=round(latency_ms, 2))
                return result
            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                logger.error(f"Failed {func_name}: {str(e)}", 
                            function=func_name, 
                            status="failed",
                            latency_ms=round(latency_ms, 2),
                            error_type=type(e).__name__)
                raise
        return wrapper
    return decorator
