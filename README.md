# Sales Quoting Engine

AI-powered sales quote creation system with streaming chat interface.

## Quick Start

### Backend Setup
1. Install dependencies: `uv pip install -r requirements.txt`
2. Set up environment: `cp .env.example .env` and add your `GOOGLE_API_KEY`
3. Initialize database: `uvx alembic upgrade head`
4. Start the server: `uv run uvicorn app.main:app --reload`

### Frontend Setup
1. Open a new terminal and run:
```bash
cd frontend
npm install
npm run dev
```
2. Visit http://localhost:5173

Notes:
- Frontend calls the backend via relative `/api/...` paths. A Vite proxy forwards to `http://localhost:8000`.
- Set `VITE_API_BASE=/api` in `frontend/.env` if needed.

## API Testing

### Health Check
```bash
http :8000/healthz
```

### Chat Streaming
```bash
http -S -N POST :8000/chat message="hello"
```

### Create Quote
```bash
http POST :8000/actions/create_quote \
  account_id=1 \
  pricebook_id=1 \
  idempotency_key=Q-DEMO \
  lines:='[{"sku_id":1,"qty":10}]'
```

## Features

- **Chat Interface**: Stream tokens in real-time with POST-based SSE polyfill
- **Quote Creation**: Direct quote creation with idempotency support
- **PDF Generation**: Automatic PDF generation for quotes
- **Session Management**: Conversation history and session tracking

## Architecture

- **Backend**: FastAPI + SQLAlchemy + LangChain + Google GenAI
- **Frontend**: React + TypeScript + Vite
- **Database**: SQLite with Alembic migrations
- **Streaming**: Server-Sent Events (SSE) for real-time chat
- **PDF**: ReportLab for professional quote generation
