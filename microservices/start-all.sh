#!/bin/bash

# Quick start script for microservices architecture
# This starts postgres/redis from old app, then all microservices

set -e

echo "============================================"
echo "Starting Microservices Architecture"
echo "============================================"
echo ""

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Step 1: Starting PostgreSQL and Redis from old app...${NC}"
cd /home/user/Redmine-Ticketing-Automatio
docker-compose up -d postgres redis

echo ""
echo -e "${YELLOW}Step 2: Waiting for database to be ready...${NC}"
sleep 10

# Check if postgres is healthy
if docker-compose ps postgres | grep -q "Up (healthy)"; then
    echo -e "${GREEN}✓ PostgreSQL is healthy${NC}"
else
    echo "⚠ PostgreSQL is not healthy yet, waiting 10 more seconds..."
    sleep 10
fi

# Check if redis is healthy
if docker-compose ps redis | grep -q "Up (healthy)"; then
    echo -e "${GREEN}✓ Redis is healthy${NC}"
else
    echo "⚠ Redis is not healthy yet, waiting 10 more seconds..."
    sleep 10
fi

echo ""
echo -e "${YELLOW}Step 3: Starting all microservices...${NC}"
cd /home/user/Redmine-Ticketing-Automatio/microservices
docker-compose -f docker-compose.microservices.yml up -d

echo ""
echo -e "${YELLOW}Step 4: Waiting for services to start...${NC}"
sleep 30

echo ""
echo -e "${YELLOW}Step 5: Configuring Kong API Gateway...${NC}"

# Check if Kong is healthy before configuring
max_retries=6
retry_count=0
while [ $retry_count -lt $max_retries ]; do
    if docker-compose -f docker-compose.microservices.yml ps kong | grep -q "Up (healthy)"; then
        echo -e "${GREEN}✓ Kong is healthy${NC}"
        break
    else
        echo "⚠ Kong is not healthy yet, waiting... ($((retry_count+1))/$max_retries)"
        sleep 10
        ((retry_count++))
    fi
done

if [ $retry_count -eq $max_retries ]; then
    echo "⚠ Kong did not become healthy in time. You may need to setup routes manually."
    echo "Run: ./setup-kong-routes.sh && ./setup-kong-cors.sh"
else
    echo ""
    echo -e "${YELLOW}Setting up Kong routes...${NC}"
    ./setup-kong-routes.sh

    echo ""
    echo -e "${YELLOW}Setting up Kong CORS...${NC}"
    ./setup-kong-cors.sh
fi

echo ""
echo "============================================"
echo -e "${GREEN}All services started successfully!${NC}"
echo "============================================"
echo ""
echo "Service Status:"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "devops-tickets|kong|auth-service|ticket-service|team-service"
echo ""
echo "Access Points:"
echo "  Frontend:          http://localhost:3000"
echo "  Kong API Gateway:  http://localhost:8000"
echo "  Kong Admin:        http://localhost:8444"
echo "  RabbitMQ:          http://localhost:15672"
echo ""
echo "Quick Health Checks:"
echo "  curl http://localhost:8000/api/auth/health"
echo "  curl http://localhost:8000/api/tickets/health"
echo "  curl http://localhost:3000"
echo ""
echo "View Logs:"
echo "  docker-compose -f docker-compose.microservices.yml logs -f <service-name>"
echo ""
echo "Stop All Services:"
echo "  cd /home/user/Redmine-Ticketing-Automatio/microservices && docker-compose -f docker-compose.microservices.yml down"
echo "  cd /home/user/Redmine-Ticketing-Automatio && docker-compose down postgres redis"
echo ""
