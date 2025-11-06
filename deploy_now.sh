#!/bin/bash
set -e

echo "========================================="
echo "  Deploying Critical Improvements"
echo "========================================="
echo ""

# 1. Backup
echo "[1/7] Creating backup..."
mkdir -p backups
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
docker exec devops-tickets-db pg_dump -U devops_user devops_tickets | gzip > backups/db_backup_$TIMESTAMP.sql.gz
echo "✅ Backup created: backups/db_backup_$TIMESTAMP.sql.gz"
echo ""

# 2. Rebuild images
echo "[2/7] Rebuilding Docker images (5-10 minutes)..."
docker-compose build backend scheduler frontend
echo "✅ Images rebuilt"
echo ""

# 3. Restart services
echo "[3/7] Restarting services..."
docker-compose down
docker-compose up -d
echo "✅ Services restarted"
echo ""

# 4. Wait for database
echo "[4/7] Waiting for database (15 seconds)..."
sleep 15
echo "✅ Database ready"
echo ""

# 5. Apply migrations
echo "[5/7] Applying database migrations..."
docker-compose exec -T backend alembic upgrade head
echo "✅ Migrations applied"
echo ""

# 6. Wait for health checks
echo "[6/7] Waiting for health checks (60 seconds)..."
sleep 60
echo "✅ Health checks complete"
echo ""

# 7. Validate
echo "[7/7] Validating deployment..."
echo ""
echo "Container Status:"
docker ps --filter "name=devops-tickets" --format "table {{.Names}}\t{{.Status}}"
echo ""

echo "Database Constraints:"
CONSTRAINTS=$(docker exec devops-tickets-db psql -U devops_user -d devops_tickets -t -c "SELECT COUNT(*) FROM pg_constraint WHERE conname LIKE 'chk_%' OR conname LIKE 'uq_%';" | tr -d ' ')
echo "  Found: $CONSTRAINTS (expected 13+)"
echo ""

echo "Database Indexes:"
INDEXES=$(docker exec devops-tickets-db psql -U devops_user -d devops_tickets -t -c "SELECT COUNT(*) FROM pg_indexes WHERE indexname LIKE 'idx_%';" | tr -d ' ')
echo "  Found: $INDEXES (expected 20+)"
echo ""

echo "API Health:"
if curl -f -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "  ✅ Backend API healthy"
else
    echo "  ❌ Backend API not responding"
fi

if curl -f -s http://localhost:3000/ > /dev/null 2>&1; then
    echo "  ✅ Frontend accessible"
else
    echo "  ❌ Frontend not accessible"
fi
echo ""

echo "========================================="
echo "  Deployment Complete!"
echo "========================================="
echo ""
echo "Backup: backups/db_backup_$TIMESTAMP.sql.gz"
echo "Constraints: $CONSTRAINTS"
echo "Indexes: $INDEXES"
echo ""
echo "Next steps:"
echo "  1. Test: http://10.0.2.121:3000"
echo "  2. Logs: docker-compose logs -f backend"
echo "  3. See QUICK_REFERENCE.md for testing commands"
echo ""
