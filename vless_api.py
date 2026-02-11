"""
3x-ui Panel API Client for VLESS key management.

API Reference: https://github.com/MHSanaei/3x-ui/wiki
Base path: /panel/api/inbounds
"""

import json
import uuid
import time
import logging
import httpx

from config import VLESS_PANEL_URL, VLESS_USERNAME, VLESS_PASSWORD, VLESS_INBOUND_IDS

logger = logging.getLogger(__name__)


class VlessClient:
    """Client for interacting with the 3x-ui panel API."""

    def __init__(self):
        self.base_url = VLESS_PANEL_URL
        self.username = VLESS_USERNAME
        self.password = VLESS_PASSWORD
        self.inbound_ids = VLESS_INBOUND_IDS
        self.session_cookie = None
        self.http_client = httpx.AsyncClient(timeout=30.0, verify=False)

    async def login(self) -> bool:
        """Authenticate with the 3x-ui panel and get session cookie."""
        try:
            url = f"{self.base_url}/login"
            data = {"username": self.username, "password": self.password}
            response = await self.http_client.post(url, data=data)
            result = response.json()

            if result.get("success"):
                # Extract session cookie
                self.session_cookie = response.cookies.get("3x-ui")
                if not self.session_cookie:
                    # Try alternative cookie name
                    for name, value in response.cookies.items():
                        self.session_cookie = value
                        break
                logger.info("Successfully logged in to 3x-ui panel")
                return True
            else:
                logger.error(f"3x-ui login failed: {result.get('msg', 'Unknown error')}")
                return False
        except Exception as e:
            logger.error(f"3x-ui login error: {e}")
            return False

    async def _ensure_logged_in(self):
        """Ensure we have a valid session."""
        if not self.session_cookie:
            success = await self.login()
            if not success:
                raise Exception("Failed to authenticate with 3x-ui panel")

    async def _request(self, method: str, path: str, **kwargs):
        """Make an authenticated request to the API."""
        await self._ensure_logged_in()
        url = f"{self.base_url}/panel/api/inbounds{path}"
        cookies = {"3x-ui": self.session_cookie}

        try:
            response = await self.http_client.request(method, url, cookies=cookies, **kwargs)
            result = response.json()

            # If session expired, re-login and retry
            if not result.get("success") and "login" in str(result.get("msg", "")).lower():
                self.session_cookie = None
                await self._ensure_logged_in()
                cookies = {"3x-ui": self.session_cookie}
                response = await self.http_client.request(method, url, cookies=cookies, **kwargs)
                result = response.json()

            return result
        except Exception as e:
            logger.error(f"3x-ui API request error: {e}")
            raise

    async def get_inbounds(self) -> list:
        """List all inbounds."""
        result = await self._request("GET", "/list")
        if result.get("success"):
            return result.get("obj", [])
        return []

    async def create_client(
        self,
        email: str,
        total_gb: int = 0,
        expiry_days: int = 30,
        limit_ip: int = 1,
        inbound_id: int = 1,
    ) -> dict:
        """
        Create a new VLESS client on the specified inbound.

        Args:
            email: Client identifier/name (used as remark)
            total_gb: Data limit in GB (0 = unlimited)
            expiry_days: Expiry in days from now
            limit_ip: Max concurrent connections (devices)
            inbound_id: Inbound ID to add client to

        Returns:
            dict with client info including the UUID
        """

        client_uuid = str(uuid.uuid4())
        expiry_time = int((time.time() + expiry_days * 86400) * 1000)  # milliseconds
        total_bytes = total_gb * 1024 * 1024 * 1024 if total_gb > 0 else 0

        client_settings = {
            "clients": [
                {
                    "id": client_uuid,
                    "flow": "",
                    "email": email,
                    "limitIp": limit_ip,
                    "totalGB": total_bytes,
                    "expiryTime": expiry_time,
                    "enable": True,
                    "tgId": "",
                    "subId": "",
                    "reset": 0,
                }
            ]
        }

        data = {
            "id": inbound_id,
            "settings": json.dumps(client_settings),
        }

        result = await self._request("POST", "/addClient", data=data)

        if result.get("success"):
            logger.info(f"Created VLESS client: {email} (UUID: {client_uuid})")
            return {
                "success": True,
                "uuid": client_uuid,
                "email": email,
                "limit_ip": limit_ip,
                "total_gb": total_gb,
                "expiry_days": expiry_days,
            }
        else:
            error = result.get("msg", "Unknown error")
            logger.error(f"Failed to create VLESS client: {error}")
            return {"success": False, "error": error}

    async def get_client_link(self, client_uuid: str, inbound_id: int = 1) -> str:
        """
        Get the VLESS connection link for a specific client.
        This fetches inbound details and constructs the VLESS URI.
        """
        result = await self._request("GET", f"/get/{inbound_id}")
        if not result.get("success"):
            return None

        inbound = result.get("obj", {})
        # Parse the stream settings
        stream_settings = json.loads(inbound.get("streamSettings", "{}"))
        port = inbound.get("port", 443)
        remark = inbound.get("remark", "vless")
        server_address = VLESS_PANEL_URL.split("://")[1].split(":")[0]

        # Build the VLESS URI
        network = stream_settings.get("network", "tcp")
        security = stream_settings.get("security", "none")

        params = [f"type={network}", f"security={security}"]

        # Add network-specific params
        if network == "ws":
            ws_settings = stream_settings.get("wsSettings", {})
            path = ws_settings.get("path", "/")
            host = ws_settings.get("headers", {}).get("Host", server_address)
            params.extend([f"path={path}", f"host={host}"])
        elif network == "grpc":
            grpc_settings = stream_settings.get("grpcSettings", {})
            service_name = grpc_settings.get("serviceName", "")
            params.append(f"serviceName={service_name}")
        elif network == "tcp":
            tcp_settings = stream_settings.get("tcpSettings", {})
            header_type = tcp_settings.get("header", {}).get("type", "none")
            params.append(f"headerType={header_type}")

        # Add TLS/reality params
        if security == "tls":
            tls_settings = stream_settings.get("tlsSettings", {})
            sni = tls_settings.get("serverName", server_address)
            fp = tls_settings.get("fingerprint", "")
            alpn = ",".join(tls_settings.get("alpn", []))
            params.extend([f"sni={sni}"])
            if fp:
                params.append(f"fp={fp}")
            if alpn:
                params.append(f"alpn={alpn}")
        elif security == "reality":
            reality_settings = stream_settings.get("realitySettings", {})
            pbk = reality_settings.get("publicKey", "")
            fp = reality_settings.get("fingerprint", "chrome")
            sni = reality_settings.get("serverNames", [""])[0] if reality_settings.get("serverNames") else ""
            sid = reality_settings.get("shortIds", [""])[0] if reality_settings.get("shortIds") else ""
            spx = reality_settings.get("spiderX", "")
            params.extend([f"sni={sni}", f"fp={fp}", f"pbk={pbk}"])
            if sid:
                params.append(f"sid={sid}")
            if spx:
                params.append(f"spx={spx}")

        params_str = "&".join(params)
        vless_link = f"vless://{client_uuid}@{server_address}:{port}?{params_str}#{remark}"

        return vless_link

    async def close(self):
        """Close the HTTP client."""
        await self.http_client.aclose()
