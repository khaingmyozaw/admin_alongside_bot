"""
Marzban Panel API Client for Outline (Shadowsocks) key management.

API Reference: https://gozargah.github.io/marzban/
Base path: /api
"""

import time
import logging
import httpx

from config import MARZBAN_PANEL_URL, MARZBAN_USERNAME, MARZBAN_PASSWORD

logger = logging.getLogger(__name__)


class MarzbanClient:
    """Client for interacting with the Marzban panel API."""

    def __init__(self):
        self.base_url = MARZBAN_PANEL_URL
        self.username = MARZBAN_USERNAME
        self.password = MARZBAN_PASSWORD
        self.access_token = None
        self.http_client = httpx.AsyncClient(timeout=30.0, verify=False)

    async def login(self) -> bool:
        """Authenticate with Marzban and get access token."""
        try:
            url = f"{self.base_url}/api/admin/token"
            data = {
                "username": self.username,
                "password": self.password,
                "grant_type": "password",
            }
            response = await self.http_client.post(
                url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if response.status_code == 200:
                result = response.json()
                self.access_token = result.get("access_token")
                logger.info("Successfully logged in to Marzban panel")
                return True
            else:
                logger.error(
                    f"Marzban login failed: {response.status_code} - {response.text}"
                )
                return False
        except Exception as e:
            logger.error(f"Marzban login error: {e}")
            return False

    async def _ensure_logged_in(self):
        """Ensure we have a valid token."""
        if not self.access_token:
            success = await self.login()
            if not success:
                raise Exception("Failed to authenticate with Marzban panel")

    async def _request(self, method: str, path: str, **kwargs):
        """Make an authenticated request to the Marzban API."""
        await self._ensure_logged_in()
        url = f"{self.base_url}/api{path}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        try:
            response = await self.http_client.request(
                method, url, headers=headers, **kwargs
            )

            # If token expired, re-login and retry
            if response.status_code == 401:
                self.access_token = None
                await self._ensure_logged_in()
                headers["Authorization"] = f"Bearer {self.access_token}"
                response = await self.http_client.request(
                    method, url, headers=headers, **kwargs
                )

            if response.status_code in (200, 201):
                return {"success": True, "data": response.json()}
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                }
        except Exception as e:
            logger.error(f"Marzban API request error: {e}")
            raise

    async def get_inbounds(self) -> dict:
        """Get available inbounds/protocols."""
        result = await self._request("GET", "/inbounds")
        if result.get("success"):
            return result.get("data", {})
        return {}

    async def create_user(
        self,
        username: str,
        data_limit_gb: int = 0,
        expiry_days: int = 30,
    ) -> dict:
        """
        Create a new user on the Marzban panel.

        Args:
            username: Unique username (3-32 chars, a-z, 0-9, _)
            data_limit_gb: Data limit in GB (0 = unlimited)
            expiry_days: Expiry in days from now

        Returns:
            dict with user info including subscription links
        """
        expiry_timestamp = int(time.time() + expiry_days * 86400)
        data_limit_bytes = data_limit_gb * 1024 * 1024 * 1024 if data_limit_gb > 0 else 0

        # First, get available inbounds to see what protocols are configured
        inbounds = await self.get_inbounds()

        # Build proxies and inbounds config
        # For Outline, we want Shadowsocks protocol
        proxies = {}
        inbound_config = {}

        if isinstance(inbounds, dict):
            for protocol, tags in inbounds.items():
                protocol_lower = protocol.lower()
                if protocol_lower == "shadowsocks":
                    proxies["shadowsocks"] = {}
                    inbound_config["shadowsocks"] = [
                        tag.get("tag", tag) if isinstance(tag, dict) else tag
                        for tag in tags
                    ]
                elif protocol_lower == "vless":
                    proxies["vless"] = {"flow": ""}
                    inbound_config["vless"] = [
                        tag.get("tag", tag) if isinstance(tag, dict) else tag
                        for tag in tags
                    ]
                elif protocol_lower == "vmess":
                    proxies["vmess"] = {}
                    inbound_config["vmess"] = [
                        tag.get("tag", tag) if isinstance(tag, dict) else tag
                        for tag in tags
                    ]
                elif protocol_lower == "trojan":
                    proxies["trojan"] = {"password": ""}
                    inbound_config["trojan"] = [
                        tag.get("tag", tag) if isinstance(tag, dict) else tag
                        for tag in tags
                    ]

        # If no protocols found, default to shadowsocks for Outline
        if not proxies:
            proxies = {"shadowsocks": {}}
            inbound_config = {}

        user_data = {
            "username": username,
            "proxies": proxies,
            "inbounds": inbound_config,
            "expire": expiry_timestamp,
            "data_limit": data_limit_bytes,
            "data_limit_reset_strategy": "no_reset",
            "status": "active",
        }

        result = await self._request("POST", "/user", json=user_data)

        if result.get("success"):
            user_info = result.get("data", {})
            logger.info(f"Created Marzban user: {username}")

            # Extract subscription URL and links
            subscription_url = user_info.get("subscription_url", "")
            links = user_info.get("links", [])

            # Build full subscription URL
            if subscription_url and not subscription_url.startswith("http"):
                subscription_url = f"{self.base_url}{subscription_url}"

            return {
                "success": True,
                "username": username,
                "subscription_url": subscription_url,
                "links": links,
                "data_limit_gb": data_limit_gb,
                "expiry_days": expiry_days,
                "expire": expiry_timestamp,
            }
        else:
            error = result.get("error", "Unknown error")
            logger.error(f"Failed to create Marzban user: {error}")
            return {"success": False, "error": error}

    async def get_user(self, username: str) -> dict:
        """Get user details."""
        result = await self._request("GET", f"/user/{username}")
        return result

    async def delete_user(self, username: str) -> dict:
        """Delete a user."""
        result = await self._request("DELETE", f"/user/{username}")
        return result

    async def close(self):
        """Close the HTTP client."""
        await self.http_client.aclose()
