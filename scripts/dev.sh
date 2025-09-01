#!/bin/bash
# Development server startup script

echo "Starting Sales Quoting Engine development server..."
echo "Environment: $(grep APP_ENV .env 2>/dev/null | cut -d'=' -f2 || echo 'development')"
echo "Database: $(grep DB_URL .env 2>/dev/null | cut -d'=' -f2 || echo 'sqlite:///./dev.db')"
echo ""

# Activate virtual environment and start server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
