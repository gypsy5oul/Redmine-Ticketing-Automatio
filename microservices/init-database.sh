#!/bin/bash

# =============================================================================
# Database Initialization Script
# Runs Alembic migrations to create all tables
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=========================================="
echo "Database Initialization"
echo "==========================================${NC}"
echo ""

# Check if database is ready
echo "Checking database connection..."
if ! docker exec devops-tickets-postgres pg_isready -U devops_user > /dev/null 2>&1; then
    echo -e "${RED}✗ PostgreSQL is not ready${NC}"
    echo "Please start the microservices first:"
    echo "  docker compose -f docker-compose.microservices.yml up -d"
    exit 1
fi

echo -e "${GREEN}✓ PostgreSQL is ready${NC}"
echo ""

# Check if tables already exist
echo "Checking if tables exist..."
TABLE_COUNT=$(docker exec devops-tickets-postgres psql -U devops_user -d devops_tickets -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';" 2>/dev/null | tr -d ' ')

if [ "$TABLE_COUNT" -gt 0 ]; then
    echo -e "${YELLOW}⚠ Database already has $TABLE_COUNT tables${NC}"
    echo ""
    echo "Do you want to:"
    echo "  1) Keep existing data and skip initialization"
    echo "  2) Drop all tables and recreate (DATA LOSS!)"
    echo ""
    read -p "Choose (1 or 2): " choice

    if [ "$choice" = "2" ]; then
        echo ""
        echo -e "${RED}WARNING: This will delete ALL data!${NC}"
        read -p "Type 'yes' to confirm: " confirm

        if [ "$confirm" != "yes" ]; then
            echo "Cancelled."
            exit 0
        fi

        echo "Dropping all tables..."
        docker exec devops-tickets-postgres psql -U devops_user -d devops_tickets -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" > /dev/null 2>&1
        echo -e "${GREEN}✓ Database cleared${NC}"
    else
        echo "Keeping existing data."
        exit 0
    fi
fi

echo ""
echo "Running database migrations..."
echo ""

# Run migrations using the backend container
cd /opt/redmine-automation-microservice/backend

# Ensure alembic is installed
if ! command -v alembic &> /dev/null; then
    echo "Installing alembic..."
    pip install alembic psycopg2-binary sqlalchemy > /dev/null 2>&1
fi

# Set database URL for migrations
export DATABASE_URL="postgresql://devops_user:devops_password_change_this@localhost:5432/devops_tickets"

# Run migrations
echo "Running Alembic migrations..."
if alembic upgrade head; then
    echo -e "${GREEN}✓ Migrations completed successfully${NC}"
else
    echo -e "${RED}✗ Migration failed${NC}"
    exit 1
fi

echo ""
echo "Verifying tables were created..."
TABLE_COUNT=$(docker exec devops-tickets-postgres psql -U devops_user -d devops_tickets -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';" | tr -d ' ')

echo -e "${GREEN}✓ Created $TABLE_COUNT tables${NC}"
echo ""

# List all tables
echo "Tables created:"
docker exec devops-tickets-postgres psql -U devops_user -d devops_tickets -c "\dt" | grep "public" | awk '{print "  - " $3}'

echo ""
echo -e "${GREEN}=========================================="
echo "Database Initialization Complete!"
echo "==========================================${NC}"
echo ""
echo "Next steps:"
echo "  1. Create admin user (if needed)"
echo "  2. Test login at http://localhost:3000"
echo ""
