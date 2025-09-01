.PHONY: help seed test capture report clean

help:  ## Show this help message
	@echo "Sales Quoting Engine - Development Commands"
	@echo "==========================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

seed:  ## Seed demo data (idempotent)
	@echo "🌱 Seeding demo data..."
	uv run python scripts/seed_demo.py

test:  ## Run API tests and capture samples
	@echo "🚀 Running API tests..."
	uv run python scripts/capture_samples.py

capture: test  ## Alias for test

report:  ## Generate acceptance report
	@echo "📊 Generating acceptance report..."
	uv run python scripts/acceptance_report.py

server:  ## Start the backend server
	@echo "🚀 Starting backend server..."
	uv run uvicorn app.main:app --reload

migrate:  ## Run database migrations
	@echo "🗄️  Running migrations..."
	uv run alembic upgrade head

setup: migrate seed  ## Full setup (migrate + seed)
	@echo "✅ Setup complete!"

clean:  ## Clean generated files
	@echo "🧹 Cleaning generated files..."
	rm -rf docs/samples/*
	rm -f dev.db*
	rm -f public/quote_*.pdf

all: setup test report  ## Run full pipeline
	@echo "🎉 Full pipeline complete!"