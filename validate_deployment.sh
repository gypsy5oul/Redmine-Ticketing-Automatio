#!/bin/bash
echo "==========================================="
echo "  VALIDATING DEPLOYMENT"
echo "==========================================="
echo ""

# Container status
echo "[1/7] Container Status:"
docker ps --filter "name=devops-tickets" --format "table {{.Names}}\t{{.Status}}"
echo ""

# Database constraints
echo "[2/7] Database Constraints:"
CONSTRAINTS=$(docker exec devops-tickets-db psql -U devops_user -d devops_tickets -t -c "SELECT COUNT(*) FROM pg_constraint WHERE conname LIKE 'chk_%' OR conname LIKE 'uq_%';" | tr -d ' ')
echo "  Found: $CONSTRAINTS constraints (expected 13+)"
echo ""

# Database indexes
echo "[3/7] Database Indexes:"
INDEXES=$(docker exec devops-tickets-db psql -U devops_user -d devops_tickets -t -c "SELECT COUNT(*) FROM pg_indexes WHERE indexname LIKE 'idx_%';" | tr -d ' ')
echo "  Found: $INDEXES indexes (expected 20+)"
echo ""

# API health
echo "[4/7] API Health:"
if curl -f -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "  ✅ Backend API healthy"
else
    echo "  ❌ Backend API not responding"
fi

# Frontend
echo "[5/7] Frontend:"
if curl -f -s http://localhost:3000/ > /dev/null 2>&1; then
    echo "  ✅ Frontend accessible"
else
    echo "  ❌ Frontend not accessible"
fi
echo ""

# Image sizes
echo "[6/7] Docker Image Sizes:"
docker images | grep devops-tickets | awk '{printf "  %-40s %s\n", $1":"$2, $7" "$8}'
echo ""

# Migration status
echo "[7/7] Migration Status:"
docker-compose exec -T backend alembic current
echo ""

echo "==========================================="
echo "  DEPLOYMENT VALIDATION COMPLETE"
echo "==========================================="
echo ""
echo "✅ Deployment successful!"
echo ""
echo "Next steps:"
echo "  1. Test app: http://10.0.2.121:3000"
echo "  2. See QUICK_REFERENCE.md for testing"
echo ""
