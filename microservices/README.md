# Microservices Architecture

This directory contains the microservices implementation of the DevOps Ticket Management System.

## 📁 Directory Structure

```
microservices/
├── README.md                              # This file
├── MICROSERVICES_MIGRATION_PLAN.md        # Overall migration plan
├── STEP_BY_STEP_MIGRATION.md              # Detailed migration steps
├── ARCHITECTURE_COMPARISON.md             # Before/After comparison
├── docker-compose.microservices.yml       # Docker Compose for all services
│
├── shared/                                # Shared code across services
│   ├── auth.py                            # JWT authentication utilities
│   ├── database.py                        # Database connection
│   ├── models.py                          # Shared database models
│   └── service_client.py                  # Inter-service HTTP clients
│
├── api-gateway/                           # API Gateway configuration
│   └── kong-config.yml                    # Kong routing rules
│
└── services/                              # Individual microservices
    ├── auth-service/                      # Port 8101
    ├── ticket-service/                    # Port 8102
    ├── team-service/                      # Port 8103 (COMPLETE EXAMPLE)
    ├── sla-service/                       # Port 8104
    ├── workload-service/                  # Port 8105
    ├── analytics-service/                 # Port 8106
    ├── escalation-service/                # Port 8107
    └── integration-service/               # Port 8108
```

## 🚀 Quick Start

### 1. Start Infrastructure
```bash
cd microservices

# Start PostgreSQL, Redis, RabbitMQ
docker compose -f docker-compose.microservices.yml up -d postgres redis rabbitmq
```

### 2. Start API Gateway
```bash
# Start Kong
docker compose -f docker-compose.microservices.yml up -d kong-database kong
```

### 3. Start Services (One by One)
```bash
# Start Team Service (example)
docker compose -f docker-compose.microservices.yml up -d team-service

# Test it
curl http://localhost:8103/health

# Access through API Gateway
curl http://localhost:8000/api/v1/team/members
```

### 4. Start All Services
```bash
# Start everything
docker compose -f docker-compose.microservices.yml up -d

# Check status
docker compose -f docker-compose.microservices.yml ps
```

## 📚 Documentation

- **[MICROSERVICES_MIGRATION_PLAN.md](MICROSERVICES_MIGRATION_PLAN.md)** - Overall strategy and timeline
- **[STEP_BY_STEP_MIGRATION.md](STEP_BY_STEP_MIGRATION.md)** - Detailed migration guide
- **[ARCHITECTURE_COMPARISON.md](ARCHITECTURE_COMPARISON.md)** - Before/After analysis

## 🎯 Service Ports

| Service | Port | Endpoints |
|---------|------|-----------|
| API Gateway (Kong) | 8000 | All external traffic |
| Auth Service | 8101 | `/api/v1/auth/*` |
| Ticket Service | 8102 | `/api/v1/tickets/*`, `/api/v1/comments/*` |
| Team Service | 8103 | `/api/v1/team/*` |
| SLA Service | 8104 | `/api/v1/sla/*` |
| Workload Service | 8105 | `/api/v1/workload/*` |
| Analytics Service | 8106 | `/api/v1/analytics/*`, `/api/v1/ml/*`, `/api/v1/dashboard/*` |
| Escalation Service | 8107 | `/api/v1/escalation/*` |
| Integration Service | 8108 | `/api/v1/redmine/*`, `/api/v1/integration/*` |

## 🔧 Development

### Create a New Service
```bash
cd services

# Copy team-service as template
cp -r team-service my-new-service

# Update:
# 1. main.py - Change service name and port
# 2. Dockerfile - Update port
# 3. requirements.txt - Add dependencies
# 4. docker-compose.microservices.yml - Add service entry
```

### Test a Service Locally
```bash
cd services/team-service

# Install dependencies
pip install -r requirements.txt

# Run locally
python main.py

# Test
curl http://localhost:8103/health
```

### Add Inter-Service Communication
```python
# In your service
from shared.service_client import TeamServiceClient

team_client = TeamServiceClient(
    base_url="http://team-service:8103",
    service_token=os.getenv("SERVICE_TOKEN")
)

# Call another service
member = await team_client.get_member(member_id)
```

## 🧪 Testing

### Unit Tests
```bash
# Test individual service
cd services/team-service
pytest tests/

# Test all services
cd microservices
pytest services/*/tests/
```

### Integration Tests
```bash
# Start all services
docker compose -f docker-compose.microservices.yml up -d

# Run integration tests
pytest tests/integration/
```

### Load Testing
```bash
# Install locust
pip install locust

# Run load test
locust -f tests/load_test.py --host=http://localhost:8000
```

## 📊 Monitoring

### Check Service Health
```bash
# All services
for port in 8101 8102 8103 8104 8105 8106 8107 8108; do
  echo "Service on port $port:"
  curl -s http://localhost:$port/health | jq
done
```

### View Logs
```bash
# All services
docker compose -f docker-compose.microservices.yml logs -f

# Specific service
docker logs -f team-service

# Filter errors
docker compose logs | grep ERROR
```

### Kong Metrics
```bash
# Check Kong status
curl http://localhost:8001/status

# View routes
curl http://localhost:8001/routes | jq

# View services
curl http://localhost:8001/services | jq
```

### RabbitMQ Management
```bash
# Access RabbitMQ UI
# http://localhost:15672
# Default credentials: devops / devops_password

# Check queues via API
curl -u devops:devops_password http://localhost:15672/api/queues | jq
```

## 🔄 Migration Status

### ✅ Completed
- [x] Infrastructure setup
- [x] Shared library creation
- [x] Team Service (complete example)
- [x] API Gateway configuration
- [x] Docker Compose setup
- [x] Documentation

### 🚧 In Progress
- [ ] Extract Ticket Service
- [ ] Extract SLA Service
- [ ] Extract Analytics Service
- [ ] Extract remaining services

### 📝 TODO
- [ ] Integration tests
- [ ] Load testing
- [ ] Gradual rollout strategy
- [ ] Remove endpoints from monolith main.py
- [ ] Production deployment

## 🚨 Troubleshooting

### Service won't start
```bash
# Check logs
docker logs team-service

# Check if port is already in use
lsof -i :8103

# Check database connectivity
docker exec -it team-service /bin/sh
psql -h postgres -U devops_user -d devops_tickets
```

### Can't reach service through API Gateway
```bash
# Check Kong routes
curl http://localhost:8001/routes

# Check if service is registered
curl http://localhost:8001/services

# Test direct service access
curl http://localhost:8103/health

# Test through gateway
curl http://localhost:8000/api/v1/team/members
```

### Database connection pool exhausted
```bash
# Increase pool size in shared/database.py
pool_size=20  # Increase this
max_overflow=10  # And this

# Or reduce number of service instances
docker compose scale team-service=1
```

## 📖 Best Practices

1. **Keep services small** - Each service should be < 500 lines
2. **One database per service** - (Future: migrate from shared DB)
3. **Use async communication** - RabbitMQ for events
4. **Add comprehensive logging** - JSON format for parsing
5. **Implement circuit breakers** - Handle service failures gracefully
6. **Version your APIs** - `/api/v1`, `/api/v2`, etc.
7. **Monitor everything** - Logs, metrics, traces
8. **Test thoroughly** - Unit, integration, load tests

## 🎯 Performance Targets

- **Response time**: < 200ms (p95)
- **Throughput**: > 100 req/sec per service
- **Availability**: 99.9% uptime
- **Error rate**: < 0.5%
- **Memory**: < 512MB per service
- **CPU**: < 50% avg per service

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Kong Documentation](https://docs.konghq.com/)
- [RabbitMQ Tutorials](https://www.rabbitmq.com/getstarted.html)
- [Microservices Patterns](https://microservices.io/patterns/)
- [12-Factor App](https://12factor.net/)

## 🤝 Contributing

1. Create a feature branch
2. Make your changes
3. Add tests
4. Update documentation
5. Submit a pull request

## 📄 License

Same as the main project.

---

**Questions?** Check the documentation or reach out to the DevOps team.
