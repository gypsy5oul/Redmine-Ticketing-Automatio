# Kong API Gateway Setup Guide

## Overview

Kong API Gateway serves as the single entry point for all microservices. All external traffic goes through Kong (port 8000), which routes requests to the appropriate microservices.

## Architecture

```
External Client → Kong Gateway (8000) → Internal Microservices (8001-8011)
                      ↓
                Kong Admin API (8444)
```

## Port Configuration

- **8000**: Kong Proxy (Main API entry point - USE THIS)
- **8443**: Kong Proxy SSL
- **8444**: Kong Admin API (for configuration)
- **8445**: Kong Admin API SSL
- **8001-8011**: Microservices (accessed through Kong)

## Quick Start

### 1. Start All Services

```bash
cd microservices
docker-compose -f docker-compose.microservices.yml up -d
```

### 2. Verify Kong is Running

```bash
# Check Kong health
curl http://localhost:8000

# Check Kong Admin API
curl http://localhost:8444
```

### 3. Configure Kong Routes (Required First Time)

You need to configure Kong to route traffic to your microservices. Run the setup script:

```bash
# Create and run the Kong configuration script
chmod +x setup-kong-routes.sh
./setup-kong-routes.sh
```

Or manually configure routes (see below).

## Manual Kong Configuration

### Create Services and Routes for All 11 Microservices

#### 1. Auth Service (Port 8001)

```bash
# Create service
curl -i -X POST http://localhost:8444/services \
  --data name=auth-service \
  --data url=http://auth-service:8001

# Create route
curl -i -X POST http://localhost:8444/services/auth-service/routes \
  --data 'paths[]=/api/v1/auth' \
  --data name=auth-route
```

#### 2. Ticket Service (Port 8002)

```bash
# Create service
curl -i -X POST http://localhost:8444/services \
  --data name=ticket-service \
  --data url=http://ticket-service:8002

# Create route
curl -i -X POST http://localhost:8444/services/ticket-service/routes \
  --data 'paths[]=/api/v1/tickets' \
  --data name=ticket-route
```

#### 3. Team Service (Port 8003)

```bash
# Create service
curl -i -X POST http://localhost:8444/services \
  --data name=team-service \
  --data url=http://team-service:8003

# Create route
curl -i -X POST http://localhost:8444/services/team-service/routes \
  --data 'paths[]=/api/v1/team' \
  --data name=team-route
```

#### 4. SLA Service (Port 8004)

```bash
# Create service
curl -i -X POST http://localhost:8444/services \
  --data name=sla-service \
  --data url=http://sla-service:8004

# Create route
curl -i -X POST http://localhost:8444/services/sla-service/routes \
  --data 'paths[]=/api/v1/sla' \
  --data name=sla-route
```

#### 5. Workload Service (Port 8005)

```bash
# Create service
curl -i -X POST http://localhost:8444/services \
  --data name=workload-service \
  --data url=http://workload-service:8005

# Create route
curl -i -X POST http://localhost:8444/services/workload-service/routes \
  --data 'paths[]=/api/v1/workload' \
  --data name=workload-route
```

#### 6. Analytics Service (Port 8006)

```bash
# Create service
curl -i -X POST http://localhost:8444/services \
  --data name=analytics-service \
  --data url=http://analytics-service:8006

# Create route
curl -i -X POST http://localhost:8444/services/analytics-service/routes \
  --data 'paths[]=/api/v1/analytics' \
  --data name=analytics-route
```

#### 7. Escalation Service (Port 8007)

```bash
# Create service
curl -i -X POST http://localhost:8444/services \
  --data name=escalation-service \
  --data url=http://escalation-service:8007

# Create route
curl -i -X POST http://localhost:8444/services/escalation-service/routes \
  --data 'paths[]=/api/v1/escalation' \
  --data name=escalation-route
```

#### 8. Collaboration Service (Port 8008)

```bash
# Create service
curl -i -X POST http://localhost:8444/services \
  --data name=collaboration-service \
  --data url=http://collaboration-service:8008

# Create route
curl -i -X POST http://localhost:8444/services/collaboration-service/routes \
  --data 'paths[]=/api/v1/collaboration' \
  --data name=collaboration-route
```

#### 9. Integration Service (Port 8009)

```bash
# Create service
curl -i -X POST http://localhost:8444/services \
  --data name=integration-service \
  --data url=http://integration-service:8009

# Create route
curl -i -X POST http://localhost:8444/services/integration-service/routes \
  --data 'paths[]=/api/v1/integration' \
  --data name=integration-route
```

#### 10. Scheduling Service (Port 8010)

```bash
# Create service
curl -i -X POST http://localhost:8444/services \
  --data name=scheduling-service \
  --data url=http://scheduling-service:8010

# Create route
curl -i -X POST http://localhost:8444/services/scheduling-service/routes \
  --data 'paths[]=/api/v1/scheduling' \
  --data name=scheduling-route
```

#### 11. Work Session Service (Port 8011)

```bash
# Create service
curl -i -X POST http://localhost:8444/services \
  --data name=work-session-service \
  --data url=http://work-session-service:8011

# Create route
curl -i -X POST http://localhost:8444/services/work-session-service/routes \
  --data 'paths[]=/api/v1/work-sessions' \
  --data name=work-session-route
```

## Automated Setup Script

Save this as `setup-kong-routes.sh`:

```bash
#!/bin/bash

echo "Configuring Kong API Gateway routes..."

# Wait for Kong to be ready
echo "Waiting for Kong to be ready..."
until curl -s http://localhost:8444 > /dev/null 2>&1; do
  echo "Kong not ready yet, waiting..."
  sleep 2
done
echo "Kong is ready!"

# Function to create service and route
create_service_route() {
  SERVICE_NAME=$1
  SERVICE_HOST=$2
  SERVICE_PORT=$3
  ROUTE_PATH=$4

  echo "Creating $SERVICE_NAME..."

  # Create service
  curl -i -X POST http://localhost:8444/services \
    --data name=$SERVICE_NAME \
    --data url=http://$SERVICE_HOST:$SERVICE_PORT

  # Create route
  curl -i -X POST http://localhost:8444/services/$SERVICE_NAME/routes \
    --data "paths[]=$ROUTE_PATH" \
    --data name=${SERVICE_NAME}-route

  echo "✓ $SERVICE_NAME configured"
}

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

echo ""
echo "✅ All Kong routes configured successfully!"
echo ""
echo "You can now access all services through Kong at http://localhost:8000"
echo "Example: curl http://localhost:8000/api/v1/auth/health"
```

## Testing the Setup

### 1. Test Health Endpoints Through Kong

```bash
# Auth service
curl http://localhost:8000/api/v1/auth/health

# Ticket service
curl http://localhost:8000/api/v1/tickets/health

# Team service
curl http://localhost:8000/api/v1/team/health

# ... and so on for all services
```

### 2. Test API Endpoints

```bash
# Login through Kong
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# Get tickets through Kong
TOKEN="your-jwt-token"
curl http://localhost:8000/api/v1/tickets \
  -H "Authorization: Bearer $TOKEN"
```

### 3. Verify Kong Configuration

```bash
# List all services
curl http://localhost:8444/services

# List all routes
curl http://localhost:8444/routes

# Check specific service
curl http://localhost:8444/services/auth-service
```

## Kong Admin API Management

### View All Services

```bash
curl http://localhost:8444/services | jq
```

### View All Routes

```bash
curl http://localhost:8444/routes | jq
```

### Delete a Service

```bash
curl -i -X DELETE http://localhost:8444/services/service-name
```

### Delete a Route

```bash
curl -i -X DELETE http://localhost:8444/routes/route-id
```

### Update a Route

```bash
curl -i -X PATCH http://localhost:8444/routes/route-id \
  --data 'paths[]=/new/path'
```

## Advanced Kong Features

### 1. Rate Limiting

Limit requests to prevent abuse:

```bash
curl -i -X POST http://localhost:8444/services/auth-service/plugins \
  --data "name=rate-limiting" \
  --data "config.second=5" \
  --data "config.hour=10000"
```

### 2. CORS Configuration

Enable CORS for frontend access:

```bash
curl -i -X POST http://localhost:8444/services/auth-service/plugins \
  --data "name=cors" \
  --data "config.origins=http://localhost:3000,http://10.0.2.121:3000" \
  --data "config.methods=GET,POST,PUT,DELETE,PATCH,OPTIONS" \
  --data "config.headers=Accept,Authorization,Content-Type" \
  --data "config.credentials=true"
```

### 3. Request/Response Logging

Log all requests and responses:

```bash
curl -i -X POST http://localhost:8444/plugins \
  --data "name=file-log" \
  --data "config.path=/tmp/kong.log"
```

### 4. JWT Authentication

Add JWT validation at gateway level:

```bash
curl -i -X POST http://localhost:8444/services/ticket-service/plugins \
  --data "name=jwt"
```

### 5. Request Transformation

Add headers to requests:

```bash
curl -i -X POST http://localhost:8444/services/auth-service/plugins \
  --data "name=request-transformer" \
  --data "config.add.headers=X-Gateway:Kong"
```

## Troubleshooting

### Kong Not Starting

```bash
# Check Kong logs
docker logs kong-gateway

# Check Kong database connection
docker exec -it kong-gateway kong health
```

### Routes Not Working

```bash
# Verify service exists
curl http://localhost:8444/services/auth-service

# Verify route exists
curl http://localhost:8444/routes | jq '.data[] | select(.name=="auth-route")'

# Test direct service connection (bypass Kong)
curl http://localhost:8001/health
```

### Database Migration Issues

```bash
# Check migration logs
docker logs kong-migrations

# Manually run migrations
docker exec -it kong-gateway kong migrations up
```

## Production Considerations

1. **SSL/TLS**: Configure Kong with proper SSL certificates for port 8443
2. **Authentication**: Add JWT plugin or OAuth2 at gateway level
3. **Rate Limiting**: Protect services from abuse
4. **Monitoring**: Enable Prometheus plugin for metrics
5. **Caching**: Add proxy-cache plugin for frequently accessed endpoints
6. **Load Balancing**: Configure multiple upstream targets for high availability

## Environment Variables in .env

```bash
# Kong API Gateway Configuration
KONG_PG_PASSWORD=kong_password_change_this
KONG_ADMIN_URL=http://localhost:8444
KONG_PROXY_URL=http://localhost:8000
```

## Next Steps

1. ✅ Start all services with docker-compose
2. ✅ Run `setup-kong-routes.sh` to configure routes
3. ✅ Test all services through Kong (port 8000)
4. 🔧 Configure Kong plugins (rate limiting, CORS, etc.)
5. 🔧 Update frontend to use Kong proxy URL (http://localhost:8000)
6. 🔧 Set up monitoring and logging

## Useful Commands

```bash
# Start all services
docker-compose -f docker-compose.microservices.yml up -d

# View Kong logs
docker logs -f kong-gateway

# Restart Kong
docker restart kong-gateway

# Stop all services
docker-compose -f docker-compose.microservices.yml down

# Stop and remove volumes (CAUTION: data loss)
docker-compose -f docker-compose.microservices.yml down -v
```

## Support

- Kong Documentation: https://docs.konghq.com/
- Kong Admin API: http://localhost:8444
- RabbitMQ Management: http://localhost:15672
- Microservices: http://localhost:8001-8011 (direct access)
- Kong Proxy: http://localhost:8000 (gateway access)

---

**Kong Setup Complete!** 🚀

All services are now accessible through Kong API Gateway at port 8000.
