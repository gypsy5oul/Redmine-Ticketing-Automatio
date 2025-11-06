#!/bin/bash

# Comprehensive endpoint audit script
# Compares old monolithic backend with new microservices

echo "============================================"
echo "ENDPOINT AUDIT - Old App vs Microservices"
echo "============================================"
echo ""

# Extract all routes from old backend
echo "1. Extracting routes from OLD MONOLITHIC BACKEND..."
echo "---------------------------------------------------"
grep "@app\." /home/user/Redmine-Ticketing-Automatio/backend/app/main.py | \
    grep -E "get|post|put|delete|patch" | \
    sed 's/@app\.//' | \
    sed 's/(.*tags=\[/  [/' | \
    sed 's/\].*$/]/' > /tmp/old_routes.txt

echo "Found $(wc -l < /tmp/old_routes.txt) routes in old backend"
echo ""

# Extract routes from microservices
echo "2. Extracting routes from MICROSERVICES..."
echo "---------------------------------------------------"

for service in auth-service ticket-service team-service sla-service workload-service \
               analytics-service escalation-service collaboration-service \
               integration-service scheduling-service work-session-service; do
    echo "  - Checking $service..."
    if [ -f "/home/user/Redmine-Ticketing-Automatio/microservices/production-services/$service/main.py" ]; then
        grep "@app\." "/home/user/Redmine-Ticketing-Automatio/microservices/production-services/$service/main.py" | \
            grep -E "get|post|put|delete|patch" | \
            sed "s/@app\./$service: /" | \
            sed 's/(.*tags=\[/  [/' | \
            sed 's/\].*$/]/' >> /tmp/microservices_routes.txt
    fi
done

echo "Found $(wc -l < /tmp/microservices_routes.txt) routes in microservices"
echo ""

# Display old backend routes categorized
echo "3. OLD BACKEND ROUTES BY CATEGORY"
echo "---------------------------------------------------"
echo ""

echo "📊 DASHBOARD:"
grep -i "dashboard" /tmp/old_routes.txt | nl
echo ""

echo "🎫 TICKETS:"
grep -E "tickets" /tmp/old_routes.txt | grep -v "process-tickets" | nl
echo ""

echo "💬 COMMENTS:"
grep -i "comments" /tmp/old_routes.txt | nl
echo ""

echo "⏰ SLA:"
grep -i "sla" /tmp/old_routes.txt | nl
echo ""

echo "📈 WORKLOAD:"
grep -i "workload" /tmp/old_routes.txt | nl
echo ""

echo "🚨 ESCALATION:"
grep -i "escalation" /tmp/old_routes.txt | nl
echo ""

echo "🤝 COLLABORATION:"
grep -i "collaboration" /tmp/old_routes.txt | nl
echo ""

echo "📉 ANALYTICS & ML:"
grep -E "analytics|ml" /tmp/old_routes.txt | nl
echo ""

echo "👥 TEAM:"
grep -i "team" /tmp/old_routes.txt | nl
echo ""

echo "🔗 REDMINE:"
grep -i "redmine" /tmp/old_routes.txt | nl
echo ""

echo "📅 SCHEDULER:"
grep -i "scheduler" /tmp/old_routes.txt | nl
echo ""

echo "📝 ACTIVITIES:"
grep -i "activities" /tmp/old_routes.txt | nl
echo ""

echo "🔐 AUTH (from auth router):"
echo "  Note: Auth routes are in /app/api/v1/auth.py"
grep "@router\." /home/user/Redmine-Ticketing-Automatio/backend/app/api/v1/auth.py | grep -E "get|post|put|delete|patch" | nl
echo ""

echo "⏱️  WORK SESSIONS (from work_sessions router):"
echo "  Note: Work session routes are in /app/api/v1/work_sessions.py"
grep "@router\." /home/user/Redmine-Ticketing-Automatio/backend/app/api/v1/work_sessions.py | grep -E "get|post|put|delete|patch" | nl
echo ""

echo "📅 SCHEDULING (from scheduling router):"
echo "  Note: Scheduling routes are in /app/api/v1/scheduling.py"
grep "@router\." /home/user/Redmine-Ticketing-Automatio/backend/app/api/v1/scheduling.py | grep -E "get|post|put|delete|patch" | nl
echo ""

# Display microservices routes
echo "4. MICROSERVICES ROUTES BY SERVICE"
echo "---------------------------------------------------"
cat /tmp/microservices_routes.txt | sort
echo ""

# Critical missing endpoints analysis
echo "5. ⚠️  CRITICAL MISSING ENDPOINTS IN MICROSERVICES"
echo "---------------------------------------------------"
echo ""

echo "Missing Dashboard Endpoints:"
if ! grep -qi "dashboard" /tmp/microservices_routes.txt; then
    echo "  ❌ ALL dashboard endpoints are missing!"
    echo "     - GET /api/v1/dashboard/metrics"
    echo "     - GET /api/v1/dashboard/activity"
else
    echo "  ✅ Dashboard endpoints found"
fi
echo ""

echo "Missing Ticket Endpoints:"
grep "tickets" /tmp/old_routes.txt | while read route; do
    endpoint=$(echo "$route" | grep -o '"/[^"]*"' | tr -d '"')
    if ! grep -q "$endpoint" /tmp/microservices_routes.txt 2>/dev/null; then
        echo "  ❌ $route"
    fi
done
echo ""

echo "Missing Comment Endpoints:"
grep "comments" /tmp/old_routes.txt | while read route; do
    endpoint=$(echo "$route" | grep -o '"/[^"]*"' | tr -d '"')
    if ! grep -q "comment" /tmp/microservices_routes.txt 2>/dev/null; then
        echo "  ❌ $route"
    fi
done
echo ""

echo "Missing Analytics/ML Endpoints:"
grep -E "analytics|ml" /tmp/old_routes.txt | while read route; do
    if ! grep -qi "analytics\|ml" /tmp/microservices_routes.txt; then
        echo "  ❌ $route"
    fi
done
echo ""

echo "6. SUMMARY"
echo "---------------------------------------------------"
echo "Old Backend Routes:     $(wc -l < /tmp/old_routes.txt)"
echo "Microservices Routes:   $(wc -l < /tmp/microservices_routes.txt 2>/dev/null || echo 0)"
echo ""
echo "RECOMMENDATION:"
echo "The microservices are missing many critical endpoints from the old backend."
echo "Most endpoints are defined inline in the old main.py and need to be"
echo "distributed across the appropriate microservices."
echo ""
echo "Priority Missing Features:"
echo "  1. Dashboard endpoints (metrics, activity)"
echo "  2. Ticket CRUD operations"
echo "  3. Comment management"
echo "  4. Analytics and ML predictions"
echo "  5. Activities/audit log"
echo ""

# Cleanup
rm -f /tmp/old_routes.txt /tmp/microservices_routes.txt
