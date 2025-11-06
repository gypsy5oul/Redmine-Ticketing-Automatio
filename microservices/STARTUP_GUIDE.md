# Microservices Startup Guide

## Overview

The microservices connect to PostgreSQL and Redis from the old monolithic app. This ensures all your existing data (users, tickets, teams, etc.) is available to the microservices.

## Architecture

```
Old App (docker-compose.yml)
  ├── postgres (devops-tickets-db) <- Contains all your data
  └── redis (devops-tickets-redis)  <- Contains all your cache

Microservices (docker-compose.microservices.yml)
  ├── 11 Microservices -> Connect to postgres/redis via devops-network
  ├── Kong API Gateway
  ├── RabbitMQ
  └── Frontend
```

## Step-by-Step Startup

### 1. Start PostgreSQL and Redis from Old App

```bash
cd /home/user/Redmine-Ticketing-Automatio

# Start only postgres and redis (not backend or frontend)
docker-compose up -d postgres redis

# Verify they're running
docker-compose ps postgres redis

# Check logs
docker-compose logs postgres | tail -20
docker-compose logs redis | tail -20
```

Expected output:
```
NAME                      STATUS
devops-tickets-db         Up (healthy)
devops-tickets-redis      Up (healthy)
```

### 2. Start All Microservices

```bash
cd /home/user/Redmine-Ticketing-Automatio/microservices

# Start all microservices, Kong, RabbitMQ, and frontend
docker-compose -f docker-compose.microservices.yml up -d

# Wait 30 seconds for all services to start
sleep 30

# Check status of all services
docker-compose -f docker-compose.microservices.yml ps
```

### 3. Configure Kong Routes and CORS

```bash
cd /home/user/Redmine-Ticketing-Automatio/microservices

# Setup Kong routes (13 routes for all services)
./setup-kong-routes.sh

# Setup CORS for frontend access
./setup-kong-cors.sh
```

### 4. Verify Everything is Working

```bash
# Check all containers are healthy
docker ps

# You should see 17 containers running:
#  1. devops-tickets-db (postgres from old app)
#  2. devops-tickets-redis (redis from old app)
#  3-5. kong-database, kong-migrations, kong-gateway
#  6. devops-tickets-rabbitmq
#  7-17. 11 microservices
#  18. devops-tickets-frontend

# Test database connection
docker-compose -f docker-compose.microservices.yml logs auth-service | tail -20

# Test Kong routing
curl http://localhost:8000/api/auth/health

# Test frontend
curl http://localhost:3000
```

### 5. Access the Application

- **Frontend:** http://localhost:3000
- **Kong API Gateway:** http://localhost:8000
- **Kong Admin:** http://localhost:8444
- **RabbitMQ Management:** http://localhost:15672 (devops_user / devops_password_change_this)

## Stopping Services

### Stop Microservices Only (Keep Database Running)

```bash
cd /home/user/Redmine-Ticketing-Automatio/microservices
docker-compose -f docker-compose.microservices.yml down
```

### Stop Everything (Including Database)

```bash
# Stop microservices
cd /home/user/Redmine-Ticketing-Automatio/microservices
docker-compose -f docker-compose.microservices.yml down

# Stop postgres and redis
cd /home/user/Redmine-Ticketing-Automatio
docker-compose down postgres redis
```

## Troubleshooting

### Issue: Services can't connect to postgres/redis

**Check network:**
```bash
# Verify devops-network exists
docker network ls | grep devops

# If not, create it
docker network create devops-network

# Restart postgres/redis on the network
cd /home/user/Redmine-Ticketing-Automatio
docker-compose up -d postgres redis
```

### Issue: "role 'devops_user' does not exist"

This should NOT happen since the old app's database already has the user. But if it does:

```bash
cd /home/user/Redmine-Ticketing-Automatio/microservices
./create-db-user.sh
```

### Issue: Frontend can't connect to backend

```bash
# Check Kong is running and healthy
docker ps | grep kong

# Re-setup Kong routes
cd /home/user/Redmine-Ticketing-Automatio/microservices
./setup-kong-routes.sh
./setup-kong-cors.sh
```

### Issue: Service logs show connection errors

```bash
# Check which service is failing
docker-compose -f docker-compose.microservices.yml ps

# View logs
docker-compose -f docker-compose.microservices.yml logs <service-name>

# Example: Check auth-service
docker-compose -f docker-compose.microservices.yml logs auth-service | tail -50
```

## Quick Start Script

For convenience, here's a single command to start everything:

```bash
# Start postgres and redis
cd /home/user/Redmine-Ticketing-Automatio && docker-compose up -d postgres redis

# Wait for them to be healthy
sleep 10

# Start microservices
cd /home/user/Redmine-Ticketing-Automatio/microservices && docker-compose -f docker-compose.microservices.yml up -d

# Wait for services to start
sleep 30

# Configure Kong
./setup-kong-routes.sh && ./setup-kong-cors.sh

echo "All services started! Access frontend at http://localhost:3000"
```

## Network Diagram

```
┌─────────────────────────────────────────────────────────┐
│ devops-network (External - from old app)               │
│                                                         │
│  ┌──────────────┐         ┌──────────────────────┐    │
│  │   postgres   │◄────────┤  All 11 Microservices│    │
│  │              │         │   - auth-service     │    │
│  └──────────────┘         │   - ticket-service   │    │
│                           │   - team-service     │    │
│  ┌──────────────┐         │   - sla-service      │    │
│  │    redis     │◄────────┤   - workload-service │    │
│  │              │         │   - analytics-service│    │
│  └──────────────┘         │   - escalation-...   │    │
│                           │   - collaboration-...│    │
│                           │   - integration-...  │    │
│                           │   - scheduling-...   │    │
│                           │   - work-session-... │    │
│                           └──────────────────────┘    │
│                                     │                  │
└─────────────────────────────────────┼──────────────────┘
                                      │
                  ┌───────────────────┴──────────────────┐
                  │ microservices-network (Internal)     │
                  │                                       │
                  │  ┌──────────────┐   ┌─────────────┐ │
                  │  │     Kong     │◄──┤  Frontend   │ │
                  │  │  API Gateway │   │  (Nginx)    │ │
                  │  └──────────────┘   └─────────────┘ │
                  │         │                            │
                  │  ┌──────────────┐                    │
                  │  │  RabbitMQ    │                    │
                  │  │ (Message Q)  │                    │
                  │  └──────────────┘                    │
                  └────────────────────────────────────────┘
```

## Data Persistence

- **PostgreSQL Data:** Managed by old app volume `postgres_data`
- **Redis Data:** Managed by old app volume `redis_data`
- **Kong Data:** Managed by microservices volume `kong_data`
- **RabbitMQ Data:** Managed by microservices volume `rabbitmq_data`

All your application data (users, tickets, teams, etc.) remains in the PostgreSQL volume managed by the old docker-compose.yml.
