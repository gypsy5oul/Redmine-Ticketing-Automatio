#!/usr/bin/env python3
"""
Redmine Service - Centralized Redmine API interactions
"""

from typing import Dict, List, Optional
import requests
from loguru import logger

from app.core.config import settings


class RedmineService:
    """Service for interacting with Redmine API"""

    def __init__(self):
        self.base_url = settings.REDMINE_BASE_URL
        self.api_key = settings.REDMINE_API_KEY
        self.headers = {
            'X-Redmine-API-Key': self.api_key,
            'Content-Type': 'application/json'
        }

    def get_group_members(self, group_id: int = None) -> List[Dict]:
        """
        Fetch all users from a Redmine group (default: DevOps Team)

        Args:
            group_id: Redmine group ID (defaults to DEVOPS_TEAM_GROUP_ID)

        Returns:
            List of user dicts with id, name, email, login
        """
        try:
            if group_id is None:
                group_id = settings.DEVOPS_TEAM_GROUP_ID

            url = f"{self.base_url}/groups/{group_id}.json?include=users"

            response = requests.get(
                url,
                headers=self.headers,
                timeout=10
            )

            response.raise_for_status()
            data = response.json()

            users = data.get('group', {}).get('users', [])

            # Enrich with detailed user info
            detailed_users = []
            for user in users:
                user_detail = self.get_user_details(user['id'])
                if user_detail:
                    detailed_users.append(user_detail)
                else:
                    # Fallback to basic info
                    detailed_users.append({
                        'id': user['id'],
                        'name': user['name'],
                        'email': None,
                        'login': None
                    })

            logger.info(f"✅ Fetched {len(detailed_users)} users from Redmine group {group_id}")
            return detailed_users

        except requests.RequestException as e:
            logger.error(f"❌ Failed to fetch group members: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Unexpected error fetching group members: {e}")
            return []

    def get_user_details(self, user_id: int) -> Optional[Dict]:
        """
        Get detailed information about a Redmine user

        Args:
            user_id: Redmine user ID

        Returns:
            Dict with id, name, email, login, firstname, lastname
        """
        try:
            url = f"{self.base_url}/users/{user_id}.json"

            response = requests.get(
                url,
                headers=self.headers,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                user = data.get('user', {})

                return {
                    'id': user.get('id'),
                    'name': f"{user.get('firstname', '')} {user.get('lastname', '')}".strip(),
                    'firstname': user.get('firstname'),
                    'lastname': user.get('lastname'),
                    'email': user.get('mail'),
                    'login': user.get('login'),
                    'status': user.get('status', 1)
                }
            else:
                logger.warning(f"⚠️ Failed to fetch user {user_id}: HTTP {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"❌ Error fetching user {user_id}: {e}")
            return None

    def update_issue(
        self,
        issue_id: int,
        assigned_to_id: int = None,
        status_id: int = None,
        notes: str = None,
        priority_id: int = None
    ) -> bool:
        """
        Update a Redmine issue

        Args:
            issue_id: Redmine issue ID
            assigned_to_id: User ID to assign to
            status_id: Status ID (1=New, 2=In Progress, 3=Resolved, 5=Closed)
            notes: Comment/note to add
            priority_id: Priority ID

        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"{self.base_url}/issues/{issue_id}.json"

            payload = {"issue": {}}

            if assigned_to_id is not None:
                payload["issue"]["assigned_to_id"] = assigned_to_id

            if status_id is not None:
                payload["issue"]["status_id"] = status_id

            if notes is not None:
                payload["issue"]["notes"] = notes

            if priority_id is not None:
                payload["issue"]["priority_id"] = priority_id

            response = requests.put(
                url,
                json=payload,
                headers=self.headers,
                timeout=10
            )

            if response.status_code == 204:
                logger.info(f"✅ Updated Redmine issue #{issue_id}")
                return True
            else:
                logger.warning(f"⚠️ Redmine update failed: HTTP {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"❌ Failed to update Redmine issue {issue_id}: {e}")
            return False

    def get_issue(self, issue_id: int) -> Optional[Dict]:
        """
        Get issue details from Redmine

        Args:
            issue_id: Redmine issue ID

        Returns:
            Issue dict or None
        """
        try:
            url = f"{self.base_url}/issues/{issue_id}.json?include=attachments,custom_fields"

            response = requests.get(
                url,
                headers=self.headers,
                timeout=10
            )

            response.raise_for_status()
            data = response.json()

            return data.get('issue')

        except Exception as e:
            logger.error(f"❌ Failed to fetch issue {issue_id}: {e}")
            return None

    def get_new_issues(self, project_id: int = None, limit: int = 50) -> List[Dict]:
        """
        Fetch new issues assigned to DevOps Team

        Args:
            project_id: Redmine project ID (defaults to DEVOPS_PROJECT_ID)
            limit: Maximum number of issues to fetch

        Returns:
            List of issue dicts
        """
        try:
            if project_id is None:
                project_id = settings.DEVOPS_PROJECT_ID

            url = f"{self.base_url}/issues.json"
            params = {
                "project_id": project_id,
                "status_id": 1,  # New status
                "assigned_to_id": settings.DEVOPS_TEAM_GROUP_ID,
                "include": "attachments,custom_fields",
                "limit": limit
            }

            response = requests.get(
                url,
                params=params,
                headers=self.headers,
                timeout=10
            )

            response.raise_for_status()
            data = response.json()

            issues = data.get('issues', [])
            logger.info(f"📥 Fetched {len(issues)} new issues from Redmine")

            return issues

        except Exception as e:
            logger.error(f"❌ Failed to fetch new issues: {e}")
            return []

    def get_issues_by_ids(self, issue_ids: List[int]) -> Dict[int, Dict]:
        """Fetch multiple Redmine issues by their IDs.

        Args:
            issue_ids: List of Redmine issue IDs.

        Returns:
            Mapping of issue_id -> issue payload.
        """
        if not issue_ids:
            return {}

        issues: Dict[int, Dict] = {}
        chunk_size = 50  # Redmine handles up to 100 per request; keep conservative

        for index in range(0, len(issue_ids), chunk_size):
            chunk = issue_ids[index:index + chunk_size]
            params = {
                "issue_id": ",".join(str(i) for i in chunk),
                "status_id": "*",  # Include closed issues
                "include": "attachments,custom_fields",
            }

            try:
                response = requests.get(
                    f"{self.base_url}/issues.json",
                    params=params,
                    headers=self.headers,
                    timeout=15
                )
                response.raise_for_status()

                data = response.json()
                for issue in data.get('issues', []):
                    issues[issue['id']] = issue

            except requests.RequestException as e:
                logger.error(f"❌ Failed to fetch issue batch {chunk}: {e}")
            except Exception as e:
                logger.error(f"❌ Unexpected error fetching issue batch {chunk}: {e}")

        return issues

    def add_issue_note(self, issue_id: int, note: str) -> bool:
        """
        Add a note/comment to an issue without changing other fields

        Args:
            issue_id: Redmine issue ID
            note: Note text to add

        Returns:
            True if successful
        """
        return self.update_issue(issue_id, notes=note)

    def get_issue_statuses(self) -> List[Dict]:
        """
        Get all available issue statuses

        Returns:
            List of status dicts with id, name, is_closed
        """
        try:
            url = f"{self.base_url}/issue_statuses.json"

            response = requests.get(
                url,
                headers=self.headers,
                timeout=10
            )

            response.raise_for_status()
            data = response.json()

            return data.get('issue_statuses', [])

        except Exception as e:
            logger.error(f"❌ Failed to fetch issue statuses: {e}")
            return []
