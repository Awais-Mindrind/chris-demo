#!/bin/bash
# Database management script

case "$1" in
    "init")
        echo "Initializing database..."
        uvx alembic upgrade head
        ;;
    "migrate")
        echo "Running database migrations..."
        uvx alembic upgrade head
        ;;
    "create-migration")
        if [ -z "$2" ]; then
            echo "Usage: $0 create-migration <migration_name>"
            exit 1
        fi
        echo "Creating migration: $2"
        uvx alembic revision --autogenerate -m "$2"
        ;;
    "reset")
        echo "Resetting database..."
        rm -f dev.db
        uvx alembic upgrade head
        ;;
    *)
        echo "Usage: $0 {init|migrate|create-migration <name>|reset}"
        echo ""
        echo "Commands:"
        echo "  init              - Initialize database with migrations"
        echo "  migrate           - Run pending migrations"
        echo "  create-migration  - Create new migration"
        echo "  reset             - Reset database (delete and recreate)"
        exit 1
        ;;
esac
