#!/usr/bin/env python3
"""
Integration Service - Redmine sync, notifications, external integrations

Port: 8009
Endpoints:
- GET /api/v1/redmine/projects - Get Redmine projects
- GET /api/v1/redmine/activities - Get activities
- POST /api/v1/redmine/sync-statuses - Sync ticket statuses
- GET /api/v1/redmine/user/{id} - Get Redmine user
"""

import os
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings
from loguru import logger

class Settings(BaseSettings):
    REDMINE_BASE_URL: str = os.getenv("REDMINE_BASE_URL", "https://redmine.example.com")
    REDMINE_API_KEY: str = os.getenv("REDMINE_API_KEY", "")
    SERVICE_NAME: str = "integration-service"
    SERVICE_PORT: int = 8009

settings = Settings()

class RedmineService:
    def __init__(self):
        self.base_url = settings.REDMINE_BASE_URL
        self.api_key = settings.REDMINE_API_KEY
        self.headers = {'X-Redmine-API-Key': self.api_key, 'Content-Type': 'application/json'}

    def get_projects(self):
        """Get Redmine projects"""
        try:
            response = requests.get(f"{self.base_url}/projects.json", headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json().get('projects', [])
        except Exception as e:
            logger.error(f"Failed to fetch projects: {e}")
            return []

    def get_user(self, user_id: int):
        """Get Redmine user"""
        try:
            response = requests.get(f"{self.base_url}/users/{user_id}.json", headers=self.headers, timeout=10)
            if response.status_code == 200:
                user = response.json().get('user', {})
                return {
                    'id': user.get('id'),
                    'name': f"{user.get('firstname', '')} {user.get('lastname', '')}".strip(),
                    'email': user.get('mail'),
                    'login': user.get('login')
                }
            return None
        except Exception as e:
            logger.error(f"Failed to fetch user: {e}")
            return None

app = FastAPI(title="Integration Service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
async def health_check():
    return {"service": settings.SERVICE_NAME, "status": "healthy"}

@app.get("/api/v1/redmine/projects", tags=["Redmine"])
async def get_projects():
    """Get Redmine projects"""
    try:
        redmine = RedmineService()
        projects = redmine.get_projects()
        return {"success": True, "count": len(projects), "projects": projects}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/redmine/user/{user_id}", tags=["Redmine"])
async def get_user(user_id: int):
    """Get Redmine user"""
    try:
        redmine = RedmineService()
        user = redmine.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return {"success": True, "user": user}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/redmine/sync-statuses", tags=["Redmine"])
async def sync_redmine_statuses():
    """
    Synchronize ticket statuses with Redmine

    Source: /backend/app/main.py:2378-2391

    This endpoint syncs local ticket statuses with Redmine.
    In the monolithic app, this calls TicketProcessor.sync_ticket_statuses_with_redmine()

    Note: Full implementation requires TicketProcessor service integration
    """
    try:
        logger.info("🔄 Redmine status sync requested")

        # In full implementation, this would:
        # 1. Query all tickets with pending sync
        # 2. Update Redmine via API for each ticket
        # 3. Mark tickets as synced

        return {
            "success": True,
            "message": "Redmine status sync completed (stub)",
            "synced_count": 0,
            "note": "Full implementation requires database access and TicketProcessor service"
        }

    except Exception as e:
        logger.error(f"❌ Failed to sync Redmine statuses: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.SERVICE_PORT, reload=True)
