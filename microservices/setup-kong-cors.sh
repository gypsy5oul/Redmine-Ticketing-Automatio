#!/bin/bash

# =============================================================================
# Kong CORS Configuration Script
# Enables Cross-Origin Resource Sharing for frontend access
# =============================================================================

set -e  # Exit on error

echo "=========================================="
echo "Kong CORS Configuration"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Wait for Kong to be ready
echo "Checking if Kong is ready..."
if ! curl -s http://localhost:8444 > /dev/null 2>&1; then
  echo -e "${RED}✗ Kong is not running!${NC}"
  echo "Please start Kong first with: docker-compose -f docker-compose.microservices.yml up -d"
  exit 1
fi

echo -e "${GREEN}✓ Kong is ready!${NC}"
echo ""

# Configure CORS plugin globally
echo "Configuring CORS plugin..."

CORS_RESPONSE=$(curl -s -X POST http://localhost:8444/plugins \
  --data "name=cors" \
  --data "config.origins=http://localhost:3000,http://localhost:5173,http://10.0.2.121:3000,http://10.0.2.121:5173" \
  --data "config.methods=GET,POST,PUT,DELETE,PATCH,OPTIONS" \
  --data "config.headers=Accept,Authorization,Content-Type,X-Requested-With" \
  --data "config.exposed_headers=Authorization,X-Total-Count" \
  --data "config.credentials=true" \
  --data "config.max_age=3600" 2>&1)

if echo "$CORS_RESPONSE" | grep -q "\"name\":\"cors\""; then
  echo -e "${GREEN}✓ CORS plugin configured successfully!${NC}"
  echo ""
  echo "Allowed origins:"
  echo "  - http://localhost:3000 (production frontend)"
  echo "  - http://localhost:5173 (dev frontend - Vite)"
  echo "  - http://10.0.2.121:3000 (remote access)"
  echo "  - http://10.0.2.121:5173 (remote dev access)"
elif echo "$CORS_RESPONSE" | grep -q "already exists"; then
  echo -e "${YELLOW}⚠ CORS plugin already exists (skipping)${NC}"
else
  echo -e "${RED}✗ Failed to configure CORS plugin${NC}"
  echo "Response: $CORS_RESPONSE"
  exit 1
fi

echo ""
echo "=========================================="
echo -e "${GREEN}✅ CORS Configuration Complete!${NC}"
echo "=========================================="
echo ""
echo "Frontend can now make API requests to Kong at:"
echo "  http://localhost:8000"
echo "  http://10.0.2.121:8000"
echo ""
echo "Next steps:"
echo "  1. Ensure frontend .env has: VITE_API_BASE_URL=http://localhost:8000"
echo "  2. Start frontend: cd frontend && npm run dev"
echo "  3. Access frontend: http://localhost:5173"
echo ""
