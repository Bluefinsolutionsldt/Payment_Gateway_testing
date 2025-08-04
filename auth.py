import hmac
import hashlib
import base64
from datetime import datetime, timezone
import httpx
from typing import Dict, Any

class SelcomClient:
    def __init__(self, api_key: str, api_secret: str, base_url: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url

    def _generate_selcom_headers(self, data: Dict[str, Any], method: str = 'POST') -> Dict[str, str]:
        timestamp = datetime.now(timezone.utc).isoformat()
        signed_fields_list = sorted(data.keys())
        signed_fields_str = ",".join(signed_fields_list)
        message_parts = [f"timestamp={timestamp}"]
        for key in signed_fields_list:
            message_parts.append(f"{key}={data[key]}")
        message = "&".join(message_parts).encode('utf-8')
        digest = hmac.new(
            self.api_secret.encode('utf-8'),
            msg=message,
            digestmod=hashlib.sha256
        ).digest()
        return {
            "Authorization": f"SELCOM {base64.b64encode(self.api_key.encode('utf-8')).decode('utf-8')}",
            "Timestamp": timestamp,
            "Digest-Method": "HS256",
            "Digest": base64.b64encode(digest).decode('utf-8'),
            "Signed-Fields": signed_fields_str,
            "Content-Type": "application/json"
        }

    async def post(self, path: str, data: Dict[str, Any]) -> httpx.Response:
        headers = self._generate_selcom_headers(data, method='POST')
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            response = await client.post(path, json=data, headers=headers)
            return response

    async def get(self, path: str, params: Dict[str, Any]) -> httpx.Response:
        headers = self._generate_selcom_headers(params, method='GET')
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            response = await client.get(path, params=params, headers=headers)
            return response
