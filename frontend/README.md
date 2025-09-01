# Frontend UI Server

A simple FastAPI + Jinja2 UI server for the Quote Agent demo.

## Features

- **Chat Interface**: Real-time streaming chat with the AI agent
- **Quote Creation**: Direct quote creation with demo data
- **PDF Viewing**: Direct links to generated quote PDFs
- **Server-Side Proxy**: No CORS issues - all requests proxied through the UI server

## Quick Start

### Prerequisites

1. Backend server running on port 8000
2. Demo data seeded in the database

### Running the Servers

**Backend (port 8000):**
```bash
uv run uvicorn app.main:app --reload --port 8000
```

**Frontend UI (port 8001):**
```bash
uv run uvicorn frontend.main:app --reload --port 8001
```

### Configuration

Environment variables:
- `BACKEND_BASE`: Backend server URL (default: `http://localhost:8000`)
- `PORT`: UI server port (default: `8001`)

## Usage

1. Open http://localhost:8001 in your browser
2. **Chat**: Type messages like "Create a quote for Acme for 10 Widgets"
3. **Direct Quote**: Click "Create Quote (direct)" for immediate quote creation
4. **PDF**: Click "View Quote PDF" links to download generated PDFs

## Manual Testing

### HTML Page
```bash
curl -sS http://localhost:8001/
```

### Direct Quote Creation
```bash
curl -sS -H "Content-Type: application/json" \
  -X POST http://localhost:8001/actions/create_quote \
  -d '{"account_id":1,"pricebook_id":1,"idempotency_key":"Q-DEMO-UI-001","lines":[{"sku_id":7,"qty":10}]}'
```

## Architecture

- **FastAPI**: UI server with Jinja2 templates
- **httpx**: Async HTTP client for backend proxying
- **SSE Streaming**: Real-time token streaming from backend
- **Static Files**: CSS and JavaScript served from `/static`

## Files

- `main.py`: FastAPI application with proxy endpoints
- `templates/index.html`: Main chat interface template
- `static/styles.css`: Minimal CSS styling
- `static/app.js`: JavaScript for chat and quote functionality
