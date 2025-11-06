#!/bin/bash

# =============================================================================
# Kong API Gateway Route Configuration Script
# Automatically configures all 11 microservices in Kong
# =============================================================================

set -e  # Exit on error

echo "=========================================="
echo "Kong API Gateway Configuration"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Wait for Kong to be ready
echo "Waiting for Kong to be ready..."
RETRY_COUNT=0
MAX_RETRIES=30

until curl -s http://localhost:8444 > /dev/null 2>&1; do
  RETRY_COUNT=$((RETRY_COUNT + 1))
  if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
    echo -e "${RED}✗ Kong did not start within expected time${NC}"
    echo "Please check: docker logs kong-gateway"
    exit 1
  fi
  echo "Kong not ready yet, waiting... ($RETRY_COUNT/$MAX_RETRIES)"
  sleep 2
done

echo -e "${GREEN}✓ Kong is ready!${NC}"
echo ""

# Function to create service and route
create_service_route() {
  SERVICE_NAME=$1
  SERVICE_HOST=$2
  SERVICE_PORT=$3
  ROUTE_PATH=$4

  echo -n "Creating $SERVICE_NAME... "

  # Check if service already exists
  EXISTING_SERVICE=$(curl -s http://localhost:8444/services/$SERVICE_NAME 2>/dev/null || echo "")

  if echo "$EXISTING_SERVICE" | grep -q "\"name\":\"$SERVICE_NAME\""; then
    echo -e "${YELLOW}(already exists, skipping)${NC}"
    return 0
  fi

  # Create service
  SERVICE_RESPONSE=$(curl -s -X POST http://localhost:8444/services \
    --data name=$SERVICE_NAME \
    --data url=http://$SERVICE_HOST:$SERVICE_PORT 2>&1)

  if ! echo "$SERVICE_RESPONSE" | grep -q "\"name\":\"$SERVICE_NAME\""; then
    echo -e "${RED}✗ Failed to create service${NC}"
    echo "Response: $SERVICE_RESPONSE"
    return 1
  fi

  # Create route
  ROUTE_RESPONSE=$(curl -s -X POST http://localhost:8444/services/$SERVICE_NAME/routes \
    --data "paths[]=$ROUTE_PATH" \
    --data name=${SERVICE_NAME}-route \
    --data "strip_path=false" 2>&1)

  if ! echo "$ROUTE_RESPONSE" | grep -q "\"name\":\"${SERVICE_NAME}-route\""; then
    echo -e "${RED}✗ Failed to create route${NC}"
    echo "Response: $ROUTE_RESPONSE"
    return 1
  fi

  echo -e "${GREEN}✓${NC}"
}

echo "Configuring microservices..."
echo ""

# Create all services and routes
create_service_route "auth-service" "auth-service" "8001" "/api/v1/auth"
create_service_route "ticket-service" "ticket-service" "8002" "/api/v1/tickets"
create_service_route "team-service" "team-service" "8003" "/api/v1/team"
create_service_route "sla-service" "sla-service" "8004" "/api/v1/sla"
create_service_route "workload-service" "workload-service" "8005" "/api/v1/workload"
create_service_route "analytics-service" "analytics-service" "8006" "/api/v1/analytics"
create_service_route "escalation-service" "escalation-service" "8007" "/api/v1/escalation"
create_service_route "collaboration-service" "collaboration-service" "8008" "/api/v1/collaboration"
create_service_route "integration-service" "integration-service" "8009" "/api/v1/integration"
create_service_route "scheduling-service" "scheduling-service" "8010" "/api/v1/scheduling"
create_service_route "work-session-service" "work-session-service" "8011" "/api/v1/work-sessions"

# Additional routes for frontend compatibility
echo ""
echo "Configuring additional frontend-compatible routes..."
create_service_route "ml-endpoints" "analytics-service" "8006" "/api/v1/ml"
create_service_route "work-endpoints" "work-session-service" "8011" "/api/v1/work"

echo ""
echo "=========================================="
echo -e "${GREEN}✅ All Kong routes configured!${NC}"
echo "=========================================="
echo ""
echo "📝 Configuration Summary:"
echo "  • 11 microservices registered"
echo "  • All routes configured with path-based routing"
echo "  • Kong Proxy: http://localhost:8000"
echo "  • Kong Admin: http://localhost:8444"
echo ""
echo "🧪 Test the setup:"
echo "  curl http://localhost:8000/api/v1/auth/health"
echo "  curl http://localhost:8000/api/v1/tickets/health"
echo "  curl http://localhost:8000/api/v1/team/health"
echo ""
echo "📚 View all services:"
echo "  curl http://localhost:8444/services | jq"
echo ""
echo "📚 View all routes:"
echo "  curl http://localhost:8444/routes | jq"
echo ""
