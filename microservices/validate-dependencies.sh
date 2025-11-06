#!/bin/bash

# =============================================================================
# Dependency Validator
# Checks that all imported modules are in requirements.txt
# =============================================================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=========================================="
echo "Dependency Validation"
echo "==========================================${NC}"
echo ""

TOTAL_ISSUES=0

# Function to check service dependencies
check_service_deps() {
    local service_dir=$1
    local service_name=$(basename "$service_dir")

    echo "Checking: $service_name"
    echo "-----------------------------------"

    if [ ! -f "$service_dir/main.py" ]; then
        echo -e "${RED}✗ main.py not found${NC}"
        ((TOTAL_ISSUES++))
        echo ""
        return
    fi

    if [ ! -f "$service_dir/requirements.txt" ]; then
        echo -e "${RED}✗ requirements.txt not found${NC}"
        ((TOTAL_ISSUES++))
        echo ""
        return
    fi

    # Extract imports from main.py
    IMPORTS=$(grep -h "^from\|^import" "$service_dir/main.py" | \
              sed 's/from \([^ ]*\).*/\1/' | \
              sed 's/import \([^ ]*\).*/\1/' | \
              grep -v "^app\.\|^\..*\|^typing\|^datetime\|^os\|^enum" | \
              sort -u)

    # Key dependencies to check
    CRITICAL_DEPS=(
        "jose:python-jose"
        "passlib:passlib"
        "bcrypt:bcrypt"
        "requests:requests"
        "redis:redis"
        "sqlalchemy:sqlalchemy"
        "fastapi:fastapi"
        "uvicorn:uvicorn"
        "pydantic:pydantic"
        "loguru:loguru"
        "httpx:httpx"
        "sklearn:scikit-learn"
        "pandas:pandas"
        "numpy:numpy"
    )

    MISSING=0

    for dep in "${CRITICAL_DEPS[@]}"; do
        import_name="${dep%%:*}"
        package_name="${dep##*:}"

        # Check if imported in code
        if echo "$IMPORTS" | grep -q "^${import_name}"; then
            # Check if in requirements.txt
            if grep -qi "^${package_name}" "$service_dir/requirements.txt"; then
                echo -e "${GREEN}✓${NC} $import_name → $package_name"
            else
                echo -e "${RED}✗ MISSING:${NC} $import_name → $package_name"
                ((MISSING++))
                ((TOTAL_ISSUES++))
            fi
        fi
    done

    if [ $MISSING -eq 0 ]; then
        echo -e "${GREEN}✓ All dependencies satisfied${NC}"
    else
        echo -e "${RED}✗ Found $MISSING missing dependencies${NC}"
    fi

    echo ""
}

# Check all services
for service_dir in production-services/*/; do
    check_service_deps "$service_dir"
done

# Summary
echo "=========================================="
echo "VALIDATION SUMMARY"
echo "=========================================="
echo ""

if [ $TOTAL_ISSUES -eq 0 ]; then
    echo -e "${GREEN}✓ All dependencies validated successfully!${NC}"
    echo ""
    echo "All services have their required dependencies in requirements.txt"
    exit 0
else
    echo -e "${RED}✗ Found $TOTAL_ISSUES issue(s)${NC}"
    echo ""
    echo "Please add missing dependencies to the appropriate requirements.txt files"
    echo ""
    echo "Common packages:"
    echo "  python-jose[cryptography]==3.3.0  # JWT authentication"
    echo "  passlib[bcrypt]==1.7.4            # Password hashing"
    echo "  bcrypt==4.0.1                      # Encryption"
    echo "  requests==2.31.0                   # HTTP requests"
    exit 1
fi
