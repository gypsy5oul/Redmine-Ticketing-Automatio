"""
HTTP client for inter-service communication
"""

import httpx
from typing import Dict, Any, Optional
from loguru import logger


class ServiceClient:
    """
    Base class for inter-service HTTP communication
    Handles authentication, retries, and error handling
    """

    def __init__(self, base_url: str, service_token: str):
        """
        Args:
            base_url: Base URL of the target service (e.g., http://team-service:8003)
            service_token: JWT token for service-to-service auth
        """
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "Authorization": f"Bearer {service_token}",
            "Content-Type": "application/json"
        }
        self.client = httpx.AsyncClient(timeout=10.0)

    async def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make GET request to another service"""
        url = f"{self.base_url}{endpoint}"

        try:
            response = await self.client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error calling {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error calling {url}: {e}")
            raise

    async def post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make POST request to another service"""
        url = f"{self.base_url}{endpoint}"

        try:
            response = await self.client.post(url, headers=self.headers, json=data)
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error calling {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error calling {url}: {e}")
            raise

    async def put(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make PUT request to another service"""
        url = f"{self.base_url}{endpoint}"

        try:
            response = await self.client.put(url, headers=self.headers, json=data)
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error calling {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error calling {url}: {e}")
            raise

    async def delete(self, endpoint: str) -> Dict[str, Any]:
        """Make DELETE request to another service"""
        url = f"{self.base_url}{endpoint}"

        try:
            response = await self.client.delete(url, headers=self.headers)
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error calling {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error calling {url}: {e}")
            raise

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()


# Service-specific clients

class TeamServiceClient(ServiceClient):
    """Client for Team Service"""

    async def get_member(self, member_id: int) -> Dict[str, Any]:
        """Get team member by ID"""
        return await self.get(f"/team/members/{member_id}")

    async def get_members(self, active_only: bool = True) -> Dict[str, Any]:
        """Get all team members"""
        params = {"active": active_only}
        return await self.get("/team/members", params=params)


class TicketServiceClient(ServiceClient):
    """Client for Ticket Service"""

    async def get_ticket(self, ticket_id: int) -> Dict[str, Any]:
        """Get ticket by ID"""
        return await self.get(f"/tickets/{ticket_id}")

    async def update_ticket(self, ticket_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update ticket"""
        return await self.put(f"/tickets/{ticket_id}", data)


class SLAServiceClient(ServiceClient):
    """Client for SLA Service"""

    async def get_sla_status(self, ticket_id: int) -> Dict[str, Any]:
        """Get SLA status for ticket"""
        return await self.get(f"/sla/status/{ticket_id}")

    async def start_tracking(self, ticket_id: int, priority: str) -> Dict[str, Any]:
        """Start SLA tracking for ticket"""
        return await self.post("/sla/start", {"ticket_id": ticket_id, "priority": priority})
