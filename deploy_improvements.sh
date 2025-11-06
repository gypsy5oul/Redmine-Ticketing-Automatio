#!/bin/bash

# =============================================================================
# Deployment Script for Critical Improvements
# =============================================================================
# Version: 1.1
# Date: 2025-11-04
# Description: Deploys database constraints, LLM improvements, and Docker optimizations
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running in project directory
if [ ! -f "docker-compose.yml" ]; then
    log_error "Must run from project root directory (/opt/redmine-automation-v3)"
    exit 1
fi

# Step 1: Create backup directory
log_info "Creating backup directory..."
mkdir -p "$BACKUP_DIR"

# Step 2: Check if containers are running
if ! docker ps | grep -q "devops-tickets-db"; then
    log_warn "Database container not running. Starting services first..."
    docker-compose up -d postgres redis
    sleep 10
fi

# Step 3: Backup database
log_info "Backing up database..."
docker exec devops-tickets-db pg_dump -U devops_user devops_tickets \
    | gzip > "$BACKUP_DIR/db_backup_$TIMESTAMP.sql.gz"
log_info "✅ Database backed up to: $BACKUP_DIR/db_backup_$TIMESTAMP.sql.gz"

# Step 4: Backup Redis (optional)
log_info "Backing up Redis..."
docker exec devops-tickets-redis redis-cli SAVE > /dev/null 2>&1 || log_warn "Redis backup skipped"
docker cp devops-tickets-redis:/data/dump.rdb "$BACKUP_DIR/redis_backup_$TIMESTAMP.rdb" 2>/dev/null || log_warn "Redis backup not available"

# Step 5: Rebuild Docker images with new multi-stage builds
log_info "Rebuilding Docker images (this may take 5-10 minutes)..."
docker-compose build --no-cache backend scheduler frontend

# Step 6: Stop services
log_info "Stopping services..."
docker-compose down

# Step 7: Start services
log_info "Starting services with new images..."
docker-compose up -d

# Step 8: Wait for services to be ready
log_info "Waiting for database to be ready..."
sleep 15

# Step 9: Apply database migrations (inside backend container)
log_info "Applying database migrations..."
log_info "Current database migration status:"
docker-compose exec -T backend alembic current || log_warn "Could not get current migration"

log_info "Upgrading to latest migration (008_add_database_constraints)..."
docker-compose exec -T backend alembic upgrade head

log_info "✅ Migration applied. New status:"
docker-compose exec -T backend alembic current

# Step 10: Wait for all services to become healthy
log_info "Waiting for all services to become healthy (60 seconds)..."
sleep 60

# Step 11: Validation
log_info "Running validation checks..."
echo ""
echo "========================================="
echo "       VALIDATION RESULTS"
echo "========================================="

# Check container health
log_info "Container status:"
docker ps --filter "name=devops-tickets" --format "table {{.Names}}\t{{.Status}}" | grep devops-tickets

# Check database constraints
log_info ""
log_info "Checking database constraints..."
CONSTRAINT_COUNT=$(docker exec devops-tickets-db psql -U devops_user -d devops_tickets -t -c "SELECT COUNT(*) FROM pg_constraint WHERE conname LIKE 'chk_%' OR conname LIKE 'uq_%';" 2>/dev/null | tr -d ' ' || echo "0")
if [ "$CONSTRAINT_COUNT" -ge 10 ]; then
    log_info "✅ Found $CONSTRAINT_COUNT constraints (expected 13+)"
else
    log_error "❌ Only found $CONSTRAINT_COUNT constraints (expected 13+)"
fi

# Check indexes
log_info "Checking database indexes..."
INDEX_COUNT=$(docker exec devops-tickets-db psql -U devops_user -d devops_tickets -t -c "SELECT COUNT(*) FROM pg_indexes WHERE indexname LIKE 'idx_%';" 2>/dev/null | tr -d ' ' || echo "0")
if [ "$INDEX_COUNT" -ge 15 ]; then
    log_info "✅ Found $INDEX_COUNT indexes (expected 20+)"
else
    log_warn "⚠️ Only found $INDEX_COUNT indexes (expected 20+)"
fi

# Test API health
log_info "Testing backend API..."
if curl -f -s http://localhost:8000/health > /dev/null 2>&1; then
    log_info "✅ Backend API is healthy"
else
    log_error "❌ Backend API health check failed"
    log_info "Checking logs..."
    docker-compose logs --tail=20 backend
fi

# Test frontend
log_info "Testing frontend..."
if curl -f -s http://localhost:3000/ > /dev/null 2>&1; then
    log_info "✅ Frontend is accessible"
else
    log_error "❌ Frontend accessibility check failed"
fi

# Check LLM service improvements
log_info "Checking LLM service improvements..."
if docker-compose exec -T backend grep -q "tenacity" /opt/venv/lib/python*/site-packages 2>/dev/null; then
    log_info "✅ Tenacity library installed (retry logic)"
else
    log_warn "⚠️ Tenacity library may not be installed"
fi

# Check image sizes
log_info ""
log_info "Docker image sizes:"
docker images | grep devops-tickets | awk '{printf "%-40s %10s\n", $1":"$2, $7" "$8}'

# Final summary
echo ""
echo "========================================="
echo "       DEPLOYMENT SUMMARY"
echo "========================================="
echo "Backup location: $BACKUP_DIR/db_backup_$TIMESTAMP.sql.gz"
echo "Database constraints: $CONSTRAINT_COUNT (expected 13+)"
echo "Database indexes: $INDEX_COUNT (expected 20+)"
echo ""

# Calculate image size savings
BACKEND_SIZE=$(docker images devops-tickets-backend --format "{{.Size}}" | head -1)
FRONTEND_SIZE=$(docker images devops-tickets-frontend --format "{{.Size}}" | head -1)
echo "Backend image size: $BACKEND_SIZE"
echo "Frontend image size: $FRONTEND_SIZE"
echo ""

log_info "✅ Deployment completed!"
echo ""
log_info "Next steps:"
echo "  1. Verify application in browser: http://10.0.2.121:3000"
echo "  2. Check logs: docker-compose logs -f backend scheduler"
echo "  3. Monitor for 24 hours"
echo ""
log_info "Test database constraints:"
echo "  docker exec devops-tickets-db psql -U devops_user -d devops_tickets"
echo "  # Try: INSERT INTO team_members (work_start_hour, work_end_hour) VALUES (25, 10);"
echo "  # Should fail with: ERROR:  new row violates check constraint"
echo ""
log_info "If issues occur, run rollback:"
echo "  docker-compose down"
echo "  cd backend"
echo "  docker-compose up -d postgres"
echo "  docker-compose exec backend alembic downgrade -1"
echo "  gunzip < $BACKUP_DIR/db_backup_$TIMESTAMP.sql.gz | docker exec -i devops-tickets-db psql -U devops_user devops_tickets"
echo "  cd .."
echo "  docker-compose up -d"
echo ""
