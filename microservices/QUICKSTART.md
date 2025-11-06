# 🚀 Microservices Quick Start Guide

## Prerequisites

- Python 3.9+
- PostgreSQL 13+
- Redis 6+
- Docker & Docker Compose (optional but recommended)

---

## Option 1: Docker Compose (Recommended)

### 1. Create Docker Compose Configuration

Create `docker-compose.yml` in the project root:

```yaml
version: '3.8'

services:
  # Infrastructure
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: ticketing_db
      POSTGRES_USER: ticketing_user
      POSTGRES_PASSWORD: securepassword
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  # Microservices
  auth-service:
    build:
      context: ./microservices/production-services/auth-service
      dockerfile: Dockerfile
    ports:
      - "8001:8001"
    environment:
      DATABASE_URL: postgresql://ticketing_user:securepassword@postgres:5432/ticketing_db
      REDIS_HOST: redis
      REDIS_PORT: 6379
      JWT_SECRET_KEY: your-super-secret-key-change-in-production
    depends_on:
      - postgres
      - redis

  ticket-service:
    build:
      context: ./microservices/production-services/ticket-service
      dockerfile: Dockerfile
    ports:
      - "8002:8002"
    environment:
      DATABASE_URL: postgresql://ticketing_user:securepassword@postgres:5432/ticketing_db
      REDIS_HOST: redis
      JWT_SECRET_KEY: your-super-secret-key-change-in-production
    depends_on:
      - postgres
      - redis

  team-service:
    build:
      context: ./microservices/production-services/team-service
      dockerfile: Dockerfile
    ports:
      - "8003:8003"
    environment:
      DATABASE_URL: postgresql://ticketing_user:securepassword@postgres:5432/ticketing_db
      REDIS_HOST: redis
      JWT_SECRET_KEY: your-super-secret-key-change-in-production
    depends_on:
      - postgres
      - redis

  sla-service:
    build:
      context: ./microservices/production-services/sla-service
      dockerfile: Dockerfile
    ports:
      - "8004:8004"
    environment:
      DATABASE_URL: postgresql://ticketing_user:securepassword@postgres:5432/ticketing_db
      REDIS_HOST: redis
      JWT_SECRET_KEY: your-super-secret-key-change-in-production
    depends_on:
      - postgres
      - redis

  workload-service:
    build:
      context: ./microservices/production-services/workload-service
      dockerfile: Dockerfile
    ports:
      - "8005:8005"
    environment:
      DATABASE_URL: postgresql://ticketing_user:securepassword@postgres:5432/ticketing_db
      REDIS_HOST: redis
    depends_on:
      - postgres
      - redis

  analytics-service:
    build:
      context: ./microservices/production-services/analytics-service
      dockerfile: Dockerfile
    ports:
      - "8006:8006"
    environment:
      DATABASE_URL: postgresql://ticketing_user:securepassword@postgres:5432/ticketing_db
    depends_on:
      - postgres

  escalation-service:
    build:
      context: ./microservices/production-services/escalation-service
      dockerfile: Dockerfile
    ports:
      - "8007:8007"
    environment:
      DATABASE_URL: postgresql://ticketing_user:securepassword@postgres:5432/ticketing_db
    depends_on:
      - postgres

  collaboration-service:
    build:
      context: ./microservices/production-services/collaboration-service
      dockerfile: Dockerfile
    ports:
      - "8008:8008"
    environment:
      DATABASE_URL: postgresql://ticketing_user:securepassword@postgres:5432/ticketing_db
    depends_on:
      - postgres

  integration-service:
    build:
      context: ./microservices/production-services/integration-service
      dockerfile: Dockerfile
    ports:
      - "8009:8009"
    environment:
      REDMINE_BASE_URL: ${REDMINE_BASE_URL}
      REDMINE_API_KEY: ${REDMINE_API_KEY}

  scheduling-service:
    build:
      context: ./microservices/production-services/scheduling-service
      dockerfile: Dockerfile
    ports:
      - "8010:8010"
    environment:
      DATABASE_URL: postgresql://ticketing_user:securepassword@postgres:5432/ticketing_db
    depends_on:
      - postgres

  work-session-service:
    build:
      context: ./microservices/production-services/work-session-service
      dockerfile: Dockerfile
    ports:
      - "8011:8011"
    environment:
      DATABASE_URL: postgresql://ticketing_user:securepassword@postgres:5432/ticketing_db
    depends_on:
      - postgres

volumes:
  postgres_data:
```

### 2. Create Dockerfile for Each Service

Create this `Dockerfile` in each service directory:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY main.py .

# Expose port
EXPOSE 8000

# Run the service
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 3. Create requirements.txt for Each Service

```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
redis==5.0.1
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
pydantic-settings==2.1.0
loguru==0.7.2
requests==2.31.0
```

### 4. Start All Services

```bash
# Build and start all services
docker-compose up --build

# Or run in background
docker-compose up -d

# Check logs
docker-compose logs -f

# Check service health
curl http://localhost:8001/health  # Auth
curl http://localhost:8002/health  # Ticket
# ... etc
```

---

## Option 2: Manual Setup (Development)

### 1. Set Up Database

```bash
# Install PostgreSQL
sudo apt-get install postgresql-15

# Create database and user
sudo -u postgres psql
CREATE DATABASE ticketing_db;
CREATE USER ticketing_user WITH PASSWORD 'securepassword';
GRANT ALL PRIVILEGES ON DATABASE ticketing_db TO ticketing_user;
\q

# Run migrations (from your existing backend)
cd backend
alembic upgrade head
```

### 2. Install Redis

```bash
sudo apt-get install redis-server
sudo systemctl start redis
```

### 3. Install Python Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install fastapi uvicorn sqlalchemy psycopg2-binary redis \
    python-jose[cryptography] passlib[bcrypt] pydantic-settings \
    loguru requests
```

### 4. Set Environment Variables

Create `.env` file:

```bash
DATABASE_URL=postgresql://ticketing_user:securepassword@localhost:5432/ticketing_db
REDIS_HOST=localhost
REDIS_PORT=6379
JWT_SECRET_KEY=your-super-secret-key-change-in-production
REDMINE_BASE_URL=https://your-redmine-instance.com
REDMINE_API_KEY=your-redmine-api-key
```

### 5. Start Services (Multiple Terminals)

**Terminal 1 - Auth Service:**
```bash
cd microservices/production-services/auth-service
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

**Terminal 2 - Ticket Service:**
```bash
cd microservices/production-services/ticket-service
uvicorn main:app --host 0.0.0.0 --port 8002 --reload
```

**Terminal 3 - Team Service:**
```bash
cd microservices/production-services/team-service
uvicorn main:app --host 0.0.0.0 --port 8003 --reload
```

**Terminal 4 - SLA Service:**
```bash
cd microservices/production-services/sla-service
uvicorn main:app --host 0.0.0.0 --port 8004 --reload
```

**Terminal 5 - Workload Service:**
```bash
cd microservices/production-services/workload-service
uvicorn main:app --host 0.0.0.0 --port 8005 --reload
```

**Terminal 6 - Analytics Service:**
```bash
cd microservices/production-services/analytics-service
uvicorn main:app --host 0.0.0.0 --port 8006 --reload
```

**Terminal 7 - Escalation Service:**
```bash
cd microservices/production-services/escalation-service
uvicorn main:app --host 0.0.0.0 --port 8007 --reload
```

**Terminal 8 - Collaboration Service:**
```bash
cd microservices/production-services/collaboration-service
uvicorn main:app --host 0.0.0.0 --port 8008 --reload
```

**Terminal 9 - Integration Service:**
```bash
cd microservices/production-services/integration-service
uvicorn main:app --host 0.0.0.0 --port 8009 --reload
```

**Terminal 10 - Scheduling Service:**
```bash
cd microservices/production-services/scheduling-service
uvicorn main:app --host 0.0.0.0 --port 8010 --reload
```

**Terminal 11 - Work Session Service:**
```bash
cd microservices/production-services/work-session-service
uvicorn main:app --host 0.0.0.0 --port 8011 --reload
```

---

## Verify All Services

### Check Health Endpoints

```bash
#!/bin/bash
# save as check-health.sh

services=(
  "8001:Auth"
  "8002:Ticket"
  "8003:Team"
  "8004:SLA"
  "8005:Workload"
  "8006:Analytics"
  "8007:Escalation"
  "8008:Collaboration"
  "8009:Integration"
  "8010:Scheduling"
  "8011:WorkSession"
)

echo "Checking all microservices..."
for service in "${services[@]}"; do
  port="${service%%:*}"
  name="${service##*:}"

  response=$(curl -s http://localhost:$port/health)
  status=$(echo $response | grep -o '"status":"[^"]*"' | cut -d'"' -f4)

  if [ "$status" == "healthy" ]; then
    echo "✅ $name Service (port $port): HEALTHY"
  else
    echo "❌ $name Service (port $port): UNHEALTHY"
  fi
done
```

```bash
chmod +x check-health.sh
./check-health.sh
```

### Access API Documentation

Each service has auto-generated Swagger docs:

- Auth: http://localhost:8001/docs
- Ticket: http://localhost:8002/docs
- Team: http://localhost:8003/docs
- SLA: http://localhost:8004/docs
- Workload: http://localhost:8005/docs
- Analytics: http://localhost:8006/docs
- Escalation: http://localhost:8007/docs
- Collaboration: http://localhost:8008/docs
- Integration: http://localhost:8009/docs
- Scheduling: http://localhost:8010/docs
- WorkSession: http://localhost:8011/docs

---

## Test the Services

### 1. Login (Auth Service)

```bash
curl -X POST http://localhost:8001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123"
  }'
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {...}
}
```

### 2. Get Team Members (Team Service)

```bash
TOKEN="your-jwt-token-from-login"

curl -X GET http://localhost:8003/api/v1/team/members \
  -H "Authorization: Bearer $TOKEN"
```

### 3. Get Tickets (Ticket Service)

```bash
curl -X GET http://localhost:8002/api/v1/tickets \
  -H "Authorization: Bearer $TOKEN"
```

### 4. Get Dashboard (Analytics Service)

```bash
curl -X GET http://localhost:8006/api/v1/analytics/dashboard \
  -H "Authorization: Bearer $TOKEN"
```

---

## API Gateway Setup (Optional)

### Using Nginx

Create `nginx.conf`:

```nginx
events {
    worker_connections 1024;
}

http {
    upstream auth_service {
        server localhost:8001;
    }

    upstream ticket_service {
        server localhost:8002;
    }

    upstream team_service {
        server localhost:8003;
    }

    # ... add all services

    server {
        listen 8080;

        location /api/v1/auth {
            proxy_pass http://auth_service;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        location /api/v1/tickets {
            proxy_pass http://ticket_service;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        location /api/v1/team {
            proxy_pass http://team_service;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        # ... add all routes
    }
}
```

Start Nginx:
```bash
nginx -c /path/to/nginx.conf
```

Now all services accessible via: `http://localhost:8080/api/v1/...`

---

## Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose logs service-name

# Check port availability
sudo netstat -tuln | grep 8001

# Check environment variables
docker-compose exec service-name env
```

### Database Connection Issues

```bash
# Test PostgreSQL connection
psql -h localhost -U ticketing_user -d ticketing_db

# Check PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-15-main.log
```

### Redis Connection Issues

```bash
# Test Redis connection
redis-cli ping

# Check Redis logs
sudo tail -f /var/log/redis/redis-server.log
```

---

## Production Checklist

- [ ] Change `JWT_SECRET_KEY` to strong random value
- [ ] Change database password
- [ ] Enable HTTPS/TLS
- [ ] Set up API rate limiting
- [ ] Configure proper CORS origins
- [ ] Set up monitoring (Prometheus + Grafana)
- [ ] Set up log aggregation (ELK Stack)
- [ ] Configure backups for PostgreSQL
- [ ] Set up CI/CD pipeline
- [ ] Load testing
- [ ] Security audit
- [ ] Documentation review

---

## Next Steps

1. **Test Locally:** Follow Option 1 or 2 above
2. **Frontend Integration:** Update frontend API URLs
3. **Deploy to Staging:** Test in staging environment
4. **Load Testing:** Ensure services can handle production traffic
5. **Production Deployment:** Deploy to production with monitoring

---

## Support

- **Documentation:** See `MIGRATION_COMPLETE.md` for full details
- **API Docs:** Visit each service's `/docs` endpoint
- **Issues:** Check service logs and health endpoints

---

**Quick Start Complete!** 🚀

All 11 services ready for deployment. Start with Docker Compose for easiest setup.
