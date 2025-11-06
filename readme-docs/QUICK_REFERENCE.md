# Quick Reference Card

## 🚀 Deployment (One-Time Setup)

```bash
cd /opt/redmine-automation-v2/v3

# 1. Configure
nano .env  # Add REDMINE_API_KEY, GOOGLE_CHAT_WEBHOOK, POSTGRES_PASSWORD

# 2. Start
docker-compose up -d

# 3. Test
./test-deployment.sh

# 4. Access
# Frontend: http://10.0.2.121:3000
# Backend:  http://10.0.2.121:8000
# API Docs: http://10.0.2.121:8000/api/docs
```

---

## 📊 Daily Operations

### Check System Health
```bash
curl http://10.0.2.121:8000/health
docker-compose ps
docker stats
```

### View Logs
```bash
docker-compose logs -f backend        # Live backend logs
docker-compose logs -f --tail=100     # Last 100 lines all services
docker-compose logs backend | grep ERROR  # Errors only
```

### Monitor Performance
```bash
# Cache metrics
curl http://10.0.2.121:8000/api/v1/metrics/cache

# ML models status
curl http://10.0.2.121:8000/api/v1/ml/models/status

# System resources
docker stats --no-stream
```

### Manual Operations
```bash
# Process tickets manually
curl -X POST http://10.0.2.121:8000/api/v1/tickets/process

# Train ML models
curl -X POST http://10.0.2.121:8000/api/v1/ml/train

# Clear cache
curl -X DELETE "http://10.0.2.121:8000/api/v1/cache/clear?cache_type=all"
```

---

## 🔧 Troubleshooting

### Service Down
```bash
docker-compose restart backend
docker-compose restart frontend
docker-compose restart postgres
docker-compose restart redis
```

### LLM Connection Issues
```bash
# Test LLM from backend
docker-compose exec backend curl http://10.0.6.31:8000/v1/models

# If fails:
# 1. Check LLM server is running on 10.0.6.31
# 2. Test network: ping 10.0.6.31
# 3. Check firewall rules
```

### Database Issues
```bash
# Check database
docker-compose exec postgres pg_isready

# Connect manually
docker-compose exec postgres psql -U devops_user -d devops_tickets

# View tables
docker-compose exec postgres psql -U devops_user -d devops_tickets -c "\dt"
```

### High Memory Usage
```bash
# Clear Redis cache
docker-compose exec redis redis-cli FLUSHALL

# Clear query cache
curl -X DELETE "http://10.0.2.121:8000/api/v1/cache/clear?cache_type=query"

# Restart services
docker-compose restart
```

---

## 📁 Important Files

| File | Purpose |
|------|---------|
| `.env` | Configuration (API keys, passwords) |
| `docker-compose.yml` | Service definitions |
| `backend/logs/` | Application logs |
| `backend/models/` | ML model files |
| `FINAL_SUMMARY.md` | Complete system overview |
| `OPTIMIZATION_GUIDE.md` | Performance details |
| `DEPLOYMENT_ON_10.0.2.121.md` | Deployment guide |

---

## 🎯 Key Endpoints

### Health & Monitoring
```
GET  /health                      - System health
GET  /api/v1/metrics/cache        - Cache performance
GET  /api/v1/ml/models/status     - ML models status
```

### Ticket Operations
```
POST /api/v1/tickets/process      - Process new tickets
GET  /api/v1/tickets/{id}         - Get ticket details
```

### ML & Analytics
```
POST /api/v1/ml/train             - Train ML models
GET  /api/v1/analytics/forecast   - Volume forecast
```

### Cache Management
```
GET    /api/v1/metrics/cache      - Cache stats
DELETE /api/v1/cache/clear        - Clear cache
```

### Full Documentation
```
http://10.0.2.121:8000/api/docs   - Swagger UI
http://10.0.2.121:8000/redoc      - ReDoc
```

---

## 🔄 Update/Restart Procedures

### Update Code
```bash
cd /opt/redmine-automation-v2/v3
git pull  # or copy new files
docker-compose down
docker-compose build
docker-compose up -d
```

### Restart Single Service
```bash
docker-compose restart backend
```

### Full Restart
```bash
docker-compose down
docker-compose up -d
```

### Apply Database Migrations
```bash
cd backend
docker-compose exec backend alembic upgrade head
```

---

## 📊 Performance Expectations

| Metric | Value |
|--------|-------|
| Ticket Processing | 1-2s (cached), 10-15s (fresh) |
| API Response Time | 20-100ms |
| System Capacity | 80-100 tickets/min |
| Cache Hit Rate | 70-85% |
| Memory Usage | 400-600MB |

---

## 🆘 Emergency Contacts

### System Information
- **Server**: 10.0.2.121
- **LLM Server**: 10.0.6.31:8000
- **Frontend**: http://10.0.2.121:3000
- **Backend**: http://10.0.2.121:8000

### Logs Export
```bash
# Export all logs for debugging
docker-compose logs > system-logs-$(date +%Y%m%d).txt

# Export specific service
docker-compose logs backend > backend-logs.txt
```

### Database Backup
```bash
docker-compose exec postgres pg_dump -U devops_user devops_tickets > \
  backup_$(date +%Y%m%d_%H%M%S).sql
```

---

## 🎓 Quick Tips

1. **Always check health first**: `curl http://10.0.2.121:8000/health`
2. **Monitor cache hit rate**: Should be 70%+ after warmup
3. **Train ML models weekly**: Automatic via scheduler
4. **Check logs for errors**: `docker-compose logs backend | grep ERROR`
5. **Backup database regularly**: Use pg_dump command above

---

## 📞 Common Commands Reference

```bash
# Start everything
docker-compose up -d

# Stop everything
docker-compose down

# View status
docker-compose ps

# Follow logs
docker-compose logs -f backend

# Check health
curl http://10.0.2.121:8000/health

# Run tests
./test-deployment.sh

# Clear cache
curl -X DELETE "http://10.0.2.121:8000/api/v1/cache/clear?cache_type=all"

# Restart service
docker-compose restart backend
```

---

**System Version**: 3.0.0-optimized
**Status**: Production Ready ✅
**Performance**: 3-5x faster
**Deployed on**: 10.0.2.121

For detailed documentation, see `FINAL_SUMMARY.md`
