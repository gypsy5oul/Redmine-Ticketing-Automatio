#!/bin/bash

# Validation script to check if microservices setup is ready
# Run this AFTER starting postgres and redis from old app

set -e

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "============================================"
echo "Microservices Setup Validation"
echo "============================================"
echo ""

ERRORS=0
WARNINGS=0

# 1. Check docker-compose file syntax
echo -e "${YELLOW}[1/10] Validating docker-compose file syntax...${NC}"
if docker-compose -f docker-compose.microservices.yml config --quiet 2>/dev/null; then
    echo -e "${GREEN}✓ Docker Compose file syntax is valid${NC}"
else
    echo -e "${RED}✗ Docker Compose file has syntax errors${NC}"
    ((ERRORS++))
fi
echo ""

# 2. Check devops-network exists
echo -e "${YELLOW}[2/10] Checking if devops-network exists...${NC}"
if docker network ls | grep -q "devops-network"; then
    echo -e "${GREEN}✓ devops-network exists${NC}"
else
    echo -e "${RED}✗ devops-network does not exist${NC}"
    echo "  Create it with: docker network create devops-network"
    ((ERRORS++))
fi
echo ""

# 3. Check postgres is running
echo -e "${YELLOW}[3/10] Checking if postgres is running...${NC}"
if docker ps | grep -q "devops-tickets-db"; then
    echo -e "${GREEN}✓ PostgreSQL container is running${NC}"

    # Check if healthy
    if docker ps | grep "devops-tickets-db" | grep -q "(healthy)"; then
        echo -e "${GREEN}✓ PostgreSQL is healthy${NC}"
    else
        echo -e "${YELLOW}⚠ PostgreSQL is running but not healthy yet (may need more time)${NC}"
        ((WARNINGS++))
    fi
else
    echo -e "${RED}✗ PostgreSQL container is not running${NC}"
    echo "  Start it with: cd /home/user/Redmine-Ticketing-Automatio && docker-compose up -d postgres"
    ((ERRORS++))
fi
echo ""

# 4. Check redis is running
echo -e "${YELLOW}[4/10] Checking if redis is running...${NC}"
if docker ps | grep -q "devops-tickets-redis"; then
    echo -e "${GREEN}✓ Redis container is running${NC}"

    # Check if healthy
    if docker ps | grep "devops-tickets-redis" | grep -q "(healthy)"; then
        echo -e "${GREEN}✓ Redis is healthy${NC}"
    else
        echo -e "${YELLOW}⚠ Redis is running but not healthy yet (may need more time)${NC}"
        ((WARNINGS++))
    fi
else
    echo -e "${RED}✗ Redis container is not running${NC}"
    echo "  Start it with: cd /home/user/Redmine-Ticketing-Automatio && docker-compose up -d redis"
    ((ERRORS++))
fi
echo ""

# 5. Check .env file exists
echo -e "${YELLOW}[5/10] Checking if .env file exists...${NC}"
if [ -f ".env" ]; then
    echo -e "${GREEN}✓ .env file exists${NC}"

    # Check critical environment variables
    if grep -q "DATABASE_URL" .env && grep -q "JWT_SECRET_KEY" .env && grep -q "SECRET_KEY" .env; then
        echo -e "${GREEN}✓ Critical environment variables are set${NC}"
    else
        echo -e "${YELLOW}⚠ Some critical environment variables may be missing${NC}"
        ((WARNINGS++))
    fi
else
    echo -e "${RED}✗ .env file does not exist${NC}"
    ((ERRORS++))
fi
echo ""

# 6. Check if all Dockerfiles exist
echo -e "${YELLOW}[6/10] Checking if all service Dockerfiles exist...${NC}"
MISSING_DOCKERFILES=0
SERVICES=("auth-service" "ticket-service" "team-service" "sla-service" "workload-service"
          "analytics-service" "escalation-service" "collaboration-service" "integration-service"
          "scheduling-service" "work-session-service")

for service in "${SERVICES[@]}"; do
    if [ ! -f "production-services/$service/Dockerfile" ]; then
        echo -e "${RED}  ✗ Missing: production-services/$service/Dockerfile${NC}"
        ((MISSING_DOCKERFILES++))
    fi
done

if [ $MISSING_DOCKERFILES -eq 0 ]; then
    echo -e "${GREEN}✓ All 11 service Dockerfiles exist${NC}"
else
    echo -e "${RED}✗ $MISSING_DOCKERFILES Dockerfile(s) missing${NC}"
    ((ERRORS++))
fi
echo ""

# 7. Check if all requirements.txt exist
echo -e "${YELLOW}[7/10] Checking if all service requirements.txt exist...${NC}"
MISSING_REQUIREMENTS=0

for service in "${SERVICES[@]}"; do
    if [ ! -f "production-services/$service/requirements.txt" ]; then
        echo -e "${RED}  ✗ Missing: production-services/$service/requirements.txt${NC}"
        ((MISSING_REQUIREMENTS++))
    fi
done

if [ $MISSING_REQUIREMENTS -eq 0 ]; then
    echo -e "${GREEN}✓ All 11 service requirements.txt exist${NC}"
else
    echo -e "${RED}✗ $MISSING_REQUIREMENTS requirements.txt file(s) missing${NC}"
    ((ERRORS++))
fi
echo ""

# 8. Check if Kong setup scripts exist and are executable
echo -e "${YELLOW}[8/10] Checking Kong setup scripts...${NC}"
if [ -f "setup-kong-routes.sh" ] && [ -x "setup-kong-routes.sh" ]; then
    echo -e "${GREEN}✓ setup-kong-routes.sh exists and is executable${NC}"
else
    echo -e "${RED}✗ setup-kong-routes.sh missing or not executable${NC}"
    ((ERRORS++))
fi

if [ -f "setup-kong-cors.sh" ] && [ -x "setup-kong-cors.sh" ]; then
    echo -e "${GREEN}✓ setup-kong-cors.sh exists and is executable${NC}"
else
    echo -e "${RED}✗ setup-kong-cors.sh missing or not executable${NC}"
    ((ERRORS++))
fi
echo ""

# 9. Check if frontend Dockerfile exists
echo -e "${YELLOW}[9/10] Checking frontend Dockerfile...${NC}"
if [ -f "../frontend/Dockerfile.microservices" ]; then
    echo -e "${GREEN}✓ Frontend Dockerfile exists${NC}"
else
    echo -e "${RED}✗ Frontend Dockerfile missing: ../frontend/Dockerfile.microservices${NC}"
    ((ERRORS++))
fi

if [ -f "../frontend/nginx.microservices.conf" ]; then
    echo -e "${GREEN}✓ Frontend Nginx config exists${NC}"
else
    echo -e "${RED}✗ Frontend Nginx config missing: ../frontend/nginx.microservices.conf${NC}"
    ((ERRORS++))
fi
echo ""

# 10. Check if postgres and redis are on devops-network
echo -e "${YELLOW}[10/10] Checking if postgres and redis are on devops-network...${NC}"
POSTGRES_ON_NETWORK=false
REDIS_ON_NETWORK=false

if docker network inspect devops-network 2>/dev/null | grep -q "devops-tickets-db"; then
    echo -e "${GREEN}✓ PostgreSQL is on devops-network${NC}"
    POSTGRES_ON_NETWORK=true
else
    echo -e "${RED}✗ PostgreSQL is NOT on devops-network${NC}"
    echo "  This may happen if postgres started before the network was created."
    echo "  Fix: cd /home/user/Redmine-Ticketing-Automatio && docker-compose restart postgres"
    ((ERRORS++))
fi

if docker network inspect devops-network 2>/dev/null | grep -q "devops-tickets-redis"; then
    echo -e "${GREEN}✓ Redis is on devops-network${NC}"
    REDIS_ON_NETWORK=true
else
    echo -e "${RED}✗ Redis is NOT on devops-network${NC}"
    echo "  Fix: cd /home/user/Redmine-Ticketing-Automatio && docker-compose restart redis"
    ((ERRORS++))
fi
echo ""

# Summary
echo "============================================"
echo "Validation Summary"
echo "============================================"
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed! Ready to start microservices.${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Start microservices: docker-compose -f docker-compose.microservices.yml up -d"
    echo "  2. Wait 30 seconds: sleep 30"
    echo "  3. Setup Kong: ./setup-kong-routes.sh && ./setup-kong-cors.sh"
    echo "  4. Access frontend: http://localhost:3000"
    echo ""
    echo "Or use the automated script:"
    echo "  ./start-all.sh"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠ Validation completed with $WARNINGS warning(s)${NC}"
    echo "  You can proceed, but monitor the services during startup."
    exit 0
else
    echo -e "${RED}✗ Validation failed with $ERRORS error(s) and $WARNINGS warning(s)${NC}"
    echo "  Please fix the errors above before starting microservices."
    exit 1
fi
