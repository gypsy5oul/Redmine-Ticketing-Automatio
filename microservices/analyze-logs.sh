#!/bin/bash

# =============================================================================
# Microservices Log Analyzer
# Analyzes logs from all services and reports issues
# =============================================================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=========================================="
echo "Microservices Log Analyzer"
echo "==========================================${NC}"
echo ""

SERVICES=(
    "auth-service"
    "ticket-service"
    "team-service"
    "sla-service"
    "workload-service"
    "analytics-service"
    "escalation-service"
    "collaboration-service"
    "integration-service"
    "scheduling-service"
    "work-session-service"
)

FOUND_ERRORS=0

# Function to analyze logs
analyze_service_logs() {
    local service=$1

    echo "----------------------------------------"
    echo -e "${BLUE}Analyzing: $service${NC}"
    echo "----------------------------------------"

    # Check if container exists
    if ! docker ps -a --format '{{.Names}}' | grep -q "^${service}$"; then
        echo -e "${RED}✗ Container not found${NC}"
        ((FOUND_ERRORS++))
        echo ""
        return
    fi

    # Get container status
    STATUS=$(docker inspect --format='{{.State.Status}}' "$service" 2>/dev/null)
    if [ "$STATUS" != "running" ]; then
        echo -e "${RED}✗ Container status: $STATUS${NC}"
        ((FOUND_ERRORS++))
    else
        echo -e "${GREEN}✓ Container is running${NC}"
    fi

    # Get logs
    LOGS=$(docker logs "$service" 2>&1 | tail -100)

    # Check for critical errors
    if echo "$LOGS" | grep -qi "ModuleNotFoundError"; then
        echo -e "${RED}✗ CRITICAL: Missing Python module${NC}"
        echo "$LOGS" | grep -i "ModuleNotFoundError" | head -3 | sed 's/^/  /'
        ((FOUND_ERRORS++))
    fi

    if echo "$LOGS" | grep -qi "ImportError"; then
        echo -e "${RED}✗ CRITICAL: Import error${NC}"
        echo "$LOGS" | grep -i "ImportError" | head -3 | sed 's/^/  /'
        ((FOUND_ERRORS++))
    fi

    if echo "$LOGS" | grep -qi "OperationalError.*could not connect"; then
        echo -e "${RED}✗ Database connection failed${NC}"
        echo "$LOGS" | grep -i "OperationalError" | head -2 | sed 's/^/  /'
        ((FOUND_ERRORS++))
    fi

    if echo "$LOGS" | grep -qi "ConnectionRefusedError"; then
        echo -e "${RED}✗ Connection refused (database/redis)${NC}"
        echo "$LOGS" | grep -i "ConnectionRefusedError" | head -2 | sed 's/^/  /'
        ((FOUND_ERRORS++))
    fi

    # Check for warnings
    if echo "$LOGS" | grep -qi "warning"; then
        WARN_COUNT=$(echo "$LOGS" | grep -ci "warning")
        echo -e "${YELLOW}⚠ Found $WARN_COUNT warnings${NC}"
        echo "$LOGS" | grep -i "warning" | tail -3 | sed 's/^/  /'
    fi

    # Check for successful startup
    if echo "$LOGS" | grep -qi "started successfully\|Application startup complete\|Uvicorn running"; then
        echo -e "${GREEN}✓ Service started successfully${NC}"
    else
        if [ "$STATUS" = "running" ]; then
            echo -e "${YELLOW}⚠ Service running but no startup confirmation found${NC}"
        fi
    fi

    # Show last few lines
    echo ""
    echo "Last 5 log lines:"
    echo "$LOGS" | tail -5 | sed 's/^/  /'

    echo ""
}

# Analyze all services
for service in "${SERVICES[@]}"; do
    analyze_service_logs "$service"
done

# Analyze infrastructure
echo "----------------------------------------"
echo -e "${BLUE}Infrastructure Services${NC}"
echo "----------------------------------------"

# PostgreSQL
if docker logs devops-tickets-postgres 2>&1 | tail -20 | grep -qi "ready to accept connections"; then
    echo -e "${GREEN}✓ PostgreSQL: Ready${NC}"
else
    echo -e "${RED}✗ PostgreSQL: Not ready${NC}"
    docker logs devops-tickets-postgres 2>&1 | tail -5 | sed 's/^/  /'
    ((FOUND_ERRORS++))
fi

# Redis
if docker logs devops-tickets-redis 2>&1 | tail -20 | grep -qi "Ready to accept connections"; then
    echo -e "${GREEN}✓ Redis: Ready${NC}"
else
    echo -e "${RED}✗ Redis: Not ready${NC}"
    docker logs devops-tickets-redis 2>&1 | tail -5 | sed 's/^/  /'
    ((FOUND_ERRORS++))
fi

# Kong
if docker logs kong-gateway 2>&1 | tail -20 | grep -qi "started"; then
    echo -e "${GREEN}✓ Kong: Started${NC}"
else
    echo -e "${RED}✗ Kong: Not started${NC}"
    docker logs kong-gateway 2>&1 | tail -5 | sed 's/^/  /'
    ((FOUND_ERRORS++))
fi

# RabbitMQ
if docker logs devops-tickets-rabbitmq 2>&1 | tail -20 | grep -qi "started"; then
    echo -e "${GREEN}✓ RabbitMQ: Started${NC}"
else
    echo -e "${RED}✗ RabbitMQ: Not started${NC}"
    docker logs devops-tickets-rabbitmq 2>&1 | tail -5 | sed 's/^/  /'
    ((FOUND_ERRORS++))
fi

echo ""
echo "=========================================="
echo "ANALYSIS SUMMARY"
echo "=========================================="
echo ""

if [ $FOUND_ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ No critical errors found!${NC}"
    echo ""
    echo "All services appear to be running correctly."
else
    echo -e "${RED}✗ Found $FOUND_ERRORS error(s)${NC}"
    echo ""
    echo "Please review the errors above and:"
    echo "  1. Check requirements.txt has all dependencies"
    echo "  2. Verify .env file has correct configuration"
    echo "  3. Ensure database is accessible"
    echo "  4. Check for port conflicts"
fi

echo ""
echo "To view full logs for a specific service:"
echo "  docker logs -f <service-name>"
echo ""
echo "To restart a service:"
echo "  docker compose -f docker-compose.microservices.yml restart <service-name>"
echo ""
