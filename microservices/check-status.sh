#!/bin/bash

# =============================================================================
# Quick Status Check for All Services
# =============================================================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=========================================="
echo "Microservices Status Check"
echo "==========================================${NC}"
echo ""

# Check if docker compose is running
if docker compose -f docker-compose.microservices.yml ps > /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif docker-compose -f docker-compose.microservices.yml ps > /dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    echo -e "${RED}Error: Docker Compose not found or not running${NC}"
    exit 1
fi

# Show all services
echo "Container Status:"
echo "-----------------------------------"
$COMPOSE_CMD -f docker-compose.microservices.yml ps

echo ""
echo "Quick Health Check:"
echo "-----------------------------------"

# Infrastructure
printf "PostgreSQL:     "
if docker exec devops-tickets-postgres pg_isready -U devops_user > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Ready${NC}"
else
    echo -e "${RED}✗ Not Ready${NC}"
fi

printf "Redis:          "
if docker exec devops-tickets-redis redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Ready${NC}"
else
    echo -e "${RED}✗ Not Ready${NC}"
fi

printf "Kong:           "
if curl -s http://localhost:8444 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Ready${NC}"
else
    echo -e "${RED}✗ Not Ready${NC}"
fi

printf "RabbitMQ:       "
if curl -s http://localhost:15672 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Ready${NC}"
else
    echo -e "${RED}✗ Not Ready${NC}"
fi

echo ""

# Microservices
PORTS=(8001 8002 8003 8004 8005 8006 8007 8008 8009 8010 8011)
NAMES=("Auth" "Ticket" "Team" "SLA" "Workload" "Analytics" "Escalation" "Collaboration" "Integration" "Scheduling" "WorkSession")

for i in "${!PORTS[@]}"; do
    port="${PORTS[$i]}"
    name="${NAMES[$i]}"

    printf "%-15s " "$name:"

    RESPONSE=$(curl -s -m 2 http://localhost:$port/health 2>&1 || echo "failed")

    if echo "$RESPONSE" | grep -qi "healthy\|ok"; then
        echo -e "${GREEN}✓ http://localhost:$port${NC}"
    else
        echo -e "${RED}✗ Port $port not responding${NC}"
    fi
done

echo ""
echo "Detailed Commands:"
echo "-----------------------------------"
echo "View all logs:        docker compose -f docker-compose.microservices.yml logs"
echo "View service logs:    docker logs <service-name>"
echo "Restart service:      docker compose -f docker-compose.microservices.yml restart <service-name>"
echo "Rebuild service:      docker compose -f docker-compose.microservices.yml up -d --build <service-name>"
echo "Stop all:             docker compose -f docker-compose.microservices.yml down"
echo "Full analysis:        ./analyze-logs.sh"
echo ""
