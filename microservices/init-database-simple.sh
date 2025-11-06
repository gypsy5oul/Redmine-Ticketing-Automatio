#!/bin/bash

# =============================================================================
# Simple Database Initialization
# Uses the old backend to run migrations
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=========================================="
echo "Database Initialization (Simple Method)"
echo "==========================================${NC}"
echo ""

# Check if database is ready
echo "Checking database connection..."
if ! docker exec devops-tickets-postgres pg_isready -U devops_user > /dev/null 2>&1; then
    echo -e "${RED}✗ PostgreSQL is not ready${NC}"
    exit 1
fi

echo -e "${GREEN}✓ PostgreSQL is ready${NC}"
echo ""

# Build a temporary container with backend and run migrations
echo "Running migrations using backend..."
cd /opt/redmine-automation-microservice

# Use docker run with backend image to run migrations
docker run --rm \
  --network microservices_microservices-network \
  -e DATABASE_URL="postgresql://devops_user:devops_password_change_this@devops-tickets-postgres:5432/devops_tickets" \
  -v $(pwd)/backend:/app \
  -w /app \
  python:3.11-slim \
  bash -c "
    pip install -q alembic sqlalchemy psycopg2-binary && \
    alembic upgrade head
  "

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Database initialized successfully${NC}"
else
    echo -e "${RED}✗ Database initialization failed${NC}"
    exit 1
fi

echo ""
echo "Verifying tables..."
TABLE_COUNT=$(docker exec devops-tickets-postgres psql -U devops_user -d devops_tickets -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';" 2>/dev/null | tr -d ' ')

echo -e "${GREEN}✓ Database has $TABLE_COUNT tables${NC}"
echo ""

# Show tables
echo "Tables created:"
docker exec devops-tickets-postgres psql -U devops_user -d devops_tickets -c "\dt" 2>/dev/null | grep "public" | awk '{print "  ✓ " $3}'

echo ""
echo -e "${GREEN}=========================================="
echo "✅ Database Ready!"
echo "==========================================${NC}"
echo ""
echo "You can now login to the application."
echo ""
