#!/usr/bin/env python3
"""
Automated service extraction tool
Extracts endpoints from main.py and creates microservices
"""

import re
import os
from typing import List, Dict, Tuple

def extract_endpoint(main_py_content: str, start_line: int) -> Tuple[str, int]:
    """
    Extract a complete endpoint function from main.py
    Returns: (endpoint_code, end_line)
    """
    lines = main_py_content.split('\n')

    # Find the decorator line
    decorator_line = start_line - 1  # Convert to 0-indexed

    # Extract from decorator to end of function
    code_lines = []
    indent_level = 0
    in_function = False

    for i in range(decorator_line, len(lines)):
        line = lines[i]

        # Start collecting from decorator
        if line.strip().startswith('@app.'):
            code_lines.append(line)
            continue

        # Found function definition
        if 'async def' in line or 'def ' in line:
            in_function = True
            indent_level = len(line) - len(line.lstrip())
            code_lines.append(line)
            continue

        if in_function:
            code_lines.append(line)

            # Check if we've reached the end of the function
            if line.strip() and not line.strip().startswith('#'):
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= indent_level and line.strip():
                    # We've outdented - function is complete
                    code_lines.pop()  # Remove the last line (belongs to next function)
                    break

    return '\n'.join(code_lines), i

def read_main_py():
    """Read main.py content"""
    with open('backend/app/main.py', 'r') as f:
        return f.read()

def extract_imports(main_py_content: str) -> List[str]:
    """Extract all imports from main.py"""
    lines = main_py_content.split('\n')
    imports = []

    for line in lines[:100]:  # Check first 100 lines for imports
        if line.strip().startswith('import ') or line.strip().startswith('from '):
            imports.append(line)
        elif line.strip().startswith('logger = '):
            imports.append(line)

    return imports

# Endpoint mapping
ENDPOINTS = {
    'Ticket': [
        252, 730, 769, 882, 922, 1012, 1079, 1159, 1208
    ],
    'Team': [
        2264, 2290, 2398, 2457, 2496, 2649, 2718, 2748
    ],
    'SLA': [
        1251, 1281, 1341, 1389, 1397, 1448, 1456
    ],
    'Analytics': [
        1665, 1695, 1716, 1783, 1819, 1846, 1875, 1903, 1954, 2231
    ],
    'Workload': [
        1468, 1496, 1504
    ],
    'Escalation': [
        1516, 1568, 1576
    ],
    'Collaboration': [
        1600, 1637, 1653
    ],
    'Redmine': [
        2338, 2360, 2378
    ],
    'Activities': [
        2928, 2961
    ]
}

def generate_service(service_name: str, endpoint_lines: List[int], main_py_content: str):
    """Generate a complete microservice file"""

    imports = extract_imports(main_py_content)

    # Extract all endpoints for this service
    endpoints_code = []
    for line_num in endpoint_lines:
        code, _ = extract_endpoint(main_py_content, line_num)
        endpoints_code.append(code)

    # Map service name to port
    port_map = {
        'Ticket': 8002,
        'Team': 8003,
        'SLA': 8004,
        'Workload': 8005,
        'Analytics': 8006,
        'Escalation': 8007,
        'Collaboration': 8008,
        'Redmine': 8009,
        'Activities': 8010
    }

    port = port_map.get(service_name, 8000)

    # Generate service file
    service_code = f'''"""
{service_name} Service - Microservice
Extracted from monolithic main.py
Port: {port}
"""

from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from loguru import logger
import os
import sys

# Add parent directory to path for shared imports
sys.path.append('../../../backend')
sys.path.append('../../shared')

# Import from original app
from app.core.database import get_db, engine
from app.core.config import settings
from app.api.deps import get_current_user, get_current_user_optional, require_admin
from app.models.ticket import TicketHistory, TicketStatus, TicketPriority, TicketCategory, ComplexityLevel
from app.models.team import TeamMember, TeamLevel
from app.models.user import User, UserRole
from app.models.sla import SLATracker, SLAStatus, SLAPolicy
from app.services import (
    TicketProcessor,
    SLAManager,
    WorkloadManager,
    EscalationService,
    NotificationService,
    CollaborationService,
    MLPredictionService,
    RedmineService,
    WorkSessionService
)

# Initialize FastAPI app
app = FastAPI(
    title="{service_name} Service",
    version="1.0.0",
    description="{service_name} management microservice"
)

# CORS
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {{
        "service": "{service_name.lower()}-service",
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }}


# ============================================================================
# Endpoints
# ============================================================================

{'

'.join(endpoints_code)}


# ============================================================================
# Startup
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    logger.info("🚀 Starting {service_name} Service v1.0.0")
    logger.info("✅ {service_name} Service started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("👋 Shutting down {service_name} Service...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port={port})
'''

    return service_code

if __name__ == "__main__":
    print("🔧 Extracting microservices from main.py...")

    main_py = read_main_py()

    for service_name, line_numbers in ENDPOINTS.items():
        print(f"\n📦 Generating {service_name} Service...")
        service_code = generate_service(service_name, line_numbers, main_py)

        # Write to file
        service_dir = f"microservices/services/{service_name.lower()}-service"
        os.makedirs(service_dir, exist_ok=True)

        with open(f"{service_dir}/main.py", 'w') as f:
            f.write(service_code)

        print(f"   ✅ Created {service_dir}/main.py ({len(line_numbers)} endpoints)")

    print("\n✅ All services generated successfully!")
