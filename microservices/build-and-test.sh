#!/bin/bash

# =============================================================================
# Microservices Build and Test Script
# Complete build, start, and validation of all 11 microservices
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
TOTAL_SERVICES=11
PASSED=0
FAILED=0
WARNINGS=0

echo -e "${BLUE}=========================================="
echo "Microservices Build & Test"
echo "==========================================${NC}"
echo ""

# Function to print colored status
print_status() {
    local status=$1
    local message=$2

    case $status in
        "pass")
            echo -e "${GREEN}✓${NC} $message"
            ((PASSED++))
            ;;
        "fail")
            echo -e "${RED}✗${NC} $message"
            ((FAILED++))
            ;;
        "warn")
            echo -e "${YELLOW}⚠${NC} $message"
            ((WARNINGS++))
            ;;
        "info")
            echo -e "${BLUE}ℹ${NC} $message"
            ;;
    esac
}

# Check prerequisites
echo "Step 1: Checking Prerequisites..."
echo "-----------------------------------"

if ! command -v docker &> /dev/null; then
    print_status "fail" "Docker is not installed"
    exit 1
else
    print_status "pass" "Docker is installed"
fi

if docker compose version &> /dev/null; then
    print_status "pass" "Docker Compose v2 is available"
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    print_status "pass" "Docker Compose v1 is available"
    COMPOSE_CMD="docker-compose"
else
    print_status "fail" "Docker Compose is not installed"
    exit 1
fi

if [ ! -f ".env" ]; then
    print_status "warn" ".env file not found in microservices directory"
    echo "    Creating .env from example..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_status "pass" "Created .env from .env.example"
    else
        print_status "fail" "No .env.example found either"
        exit 1
    fi
else
    print_status "pass" ".env file exists"
fi

echo ""

# Stop existing containers
echo "Step 2: Stopping Existing Containers..."
echo "-----------------------------------"
$COMPOSE_CMD -f docker-compose.microservices.yml down > /dev/null 2>&1 || true
print_status "pass" "Stopped all existing containers"
echo ""

# Build services
echo "Step 3: Building All Services (this may take 10-20 minutes)..."
echo "-----------------------------------"
print_status "info" "Building infrastructure and 11 microservices..."
echo ""

BUILD_START=$(date +%s)

if $COMPOSE_CMD -f docker-compose.microservices.yml build --no-cache 2>&1 | tee build.log; then
    print_status "pass" "All services built successfully"

    BUILD_END=$(date +%s)
    BUILD_TIME=$((BUILD_END - BUILD_START))
    echo "    Build time: ${BUILD_TIME}s (~$((BUILD_TIME / 60))m $((BUILD_TIME % 60))s)"
else
    print_status "fail" "Build failed - check build.log for details"
    echo ""
    echo "Last 30 lines of build.log:"
    tail -30 build.log
    exit 1
fi

echo ""

# Start services
echo "Step 4: Starting All Services..."
echo "-----------------------------------"
print_status "info" "Starting infrastructure and microservices..."
echo ""

if $COMPOSE_CMD -f docker-compose.microservices.yml up -d 2>&1 | tee start.log; then
    print_status "pass" "All services started"
else
    print_status "fail" "Failed to start services - check start.log"
    exit 1
fi

echo ""
print_status "info" "Waiting 30 seconds for services to initialize..."
sleep 30
echo ""

# Check container status
echo "Step 5: Checking Container Status..."
echo "-----------------------------------"

SERVICES=(
    "devops-tickets-postgres"
    "devops-tickets-redis"
    "kong-database"
    "kong-gateway"
    "devops-tickets-rabbitmq"
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

for service in "${SERVICES[@]}"; do
    if docker ps --format '{{.Names}}' | grep -q "^${service}$"; then
        STATUS=$(docker inspect --format='{{.State.Status}}' "$service" 2>/dev/null || echo "unknown")
        if [ "$STATUS" = "running" ]; then
            print_status "pass" "$service is running"
        else
            print_status "fail" "$service exists but status is: $STATUS"
        fi
    else
        print_status "fail" "$service container not found"
    fi
done

echo ""

# Check for errors in logs
echo "Step 6: Checking Service Logs for Errors..."
echo "-----------------------------------"

MICROSERVICES=(
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

for service in "${MICROSERVICES[@]}"; do
    LOGS=$(docker logs "$service" 2>&1 | tail -20)

    if echo "$LOGS" | grep -qi "error\|exception\|failed\|traceback"; then
        print_status "fail" "$service has errors in logs"
        echo "    Last error:"
        echo "$LOGS" | grep -i "error\|exception\|failed\|traceback" | tail -3 | sed 's/^/    /'
    elif echo "$LOGS" | grep -qi "started successfully\|Application startup complete"; then
        print_status "pass" "$service started successfully"
    else
        print_status "warn" "$service - cannot determine status from logs"
    fi
done

echo ""

# Test health endpoints
echo "Step 7: Testing Health Endpoints..."
echo "-----------------------------------"
print_status "info" "Waiting 10 more seconds before testing..."
sleep 10
echo ""

# Test infrastructure
if curl -s http://localhost:8444 > /dev/null 2>&1; then
    print_status "pass" "Kong Admin API is accessible"
else
    print_status "fail" "Kong Admin API is not accessible"
fi

if docker exec devops-tickets-postgres pg_isready -U devops_user > /dev/null 2>&1; then
    print_status "pass" "PostgreSQL is ready"
else
    print_status "fail" "PostgreSQL is not ready"
fi

if docker exec devops-tickets-redis redis-cli ping > /dev/null 2>&1; then
    print_status "pass" "Redis is ready"
else
    print_status "fail" "Redis is not ready"
fi

if docker exec devops-tickets-rabbitmq rabbitmq-diagnostics ping > /dev/null 2>&1; then
    print_status "pass" "RabbitMQ is ready"
else
    print_status "fail" "RabbitMQ is not ready"
fi

echo ""

# Test microservice health endpoints (direct)
HEALTH_PORTS=(
    "auth-service:8001"
    "ticket-service:8002"
    "team-service:8003"
    "sla-service:8004"
    "workload-service:8005"
    "analytics-service:8006"
    "escalation-service:8007"
    "collaboration-service:8008"
    "integration-service:8009"
    "scheduling-service:8010"
    "work-session-service:8011"
)

for service_port in "${HEALTH_PORTS[@]}"; do
    service="${service_port%%:*}"
    port="${service_port##*:}"

    RESPONSE=$(curl -s http://localhost:$port/health 2>&1 || echo "connection_failed")

    if echo "$RESPONSE" | grep -qi "healthy\|ok"; then
        print_status "pass" "$service health endpoint OK"
    else
        print_status "fail" "$service health endpoint failed (port $port)"
    fi
done

echo ""

# Generate summary report
echo "=========================================="
echo "BUILD & TEST SUMMARY"
echo "=========================================="
echo ""
echo "Total Checks: $((PASSED + FAILED + WARNINGS))"
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo -e "${YELLOW}Warnings: $WARNINGS${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ ALL TESTS PASSED!${NC}"
    echo ""
    echo "Your microservices stack is ready!"
    echo ""
    echo "Next steps:"
    echo "  1. Configure Kong routes: ./setup-kong-routes.sh"
    echo "  2. Configure CORS: ./setup-kong-cors.sh"
    echo "  3. Access services:"
    echo "     - Kong Proxy: http://localhost:8000"
    echo "     - Kong Admin: http://localhost:8444"
    echo "     - RabbitMQ UI: http://localhost:15672"
    echo ""
    exit 0
else
    echo -e "${RED}✗ TESTS FAILED${NC}"
    echo ""
    echo "Please review the errors above and check:"
    echo "  1. Service logs: docker logs <service-name>"
    echo "  2. Build logs: cat build.log"
    echo "  3. Start logs: cat start.log"
    echo ""
    echo "Common issues:"
    echo "  - Missing dependencies in requirements.txt"
    echo "  - Database connection errors (check .env)"
    echo "  - Port conflicts"
    echo "  - Missing environment variables"
    echo ""
    exit 1
fi
