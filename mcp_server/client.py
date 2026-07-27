import os
import time

import requests

from app.config import config

# Requested once, at first token exchange — matches exactly what mcp_server's tools use today
# (list_libraries, query_library) plus offline_access so a refresh token is also issued.
_OAUTH_SCOPE = "libraries:read query:execute offline_access"
# Refresh a bit before the JWT's real expiry so a request never starts with an about-to-expire token.
_EXPIRY_SAFETY_MARGIN_SECONDS = 30


class RagApiError(Exception):
    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.code = code


class RagApiClient:
    """Calls the Flask API over loopback HTTP from inside the same container.

    Authenticates as a registered Application (via /dashboard) using OAuth2 client_credentials +
    refresh_token — a scoped credential (libraries:read + query:execute only), never the app's own
    admin session.
    """

    def __init__(self):
        self._base_url = f"http://localhost:{config.port}"
        self._client_id = os.environ.get("MCP_CLIENT_ID")
        self._client_secret = os.environ.get("MCP_CLIENT_SECRET")
        if not self._client_id or not self._client_secret:
            raise RagApiError(
                "MCP_CLIENT_ID/MCP_CLIENT_SECRET are not set. Register an application in the "
                "/dashboard and set both env vars to its client_id/client_secret."
            )
        self._access_token: str | None = None
        self._access_token_expires_at: float = 0.0
        self._refresh_token: str | None = None

    def _headers(self) -> dict:
        self._ensure_access_token()
        return {"Authorization": f"Bearer {self._access_token}"}

    def _ensure_access_token(self) -> None:
        if self._access_token is not None and time.time() < self._access_token_expires_at:
            return
        if self._refresh_token is not None and self._refresh_via_refresh_token():
            return
        self._refresh_via_client_credentials()

    def _refresh_via_refresh_token(self) -> bool:
        response = requests.post(
            f"{self._base_url}/oauth/token",
            data={"grant_type": "refresh_token", "refresh_token": self._refresh_token},
        )
        if not response.ok:
            return False
        self._cache_token_response(response.json())
        return True

    def _refresh_via_client_credentials(self) -> None:
        response = requests.post(
            f"{self._base_url}/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "scope": _OAUTH_SCOPE,
            },
        )
        self._raise_for_status(response)
        self._cache_token_response(response.json())

    def _cache_token_response(self, body: dict) -> None:
        self._access_token = body["access_token"]
        self._access_token_expires_at = time.time() + body["expires_in"] - _EXPIRY_SAFETY_MARGIN_SECONDS
        if "refresh_token" in body:
            self._refresh_token = body["refresh_token"]

    def _raise_for_status(self, response: requests.Response):
        try:
            response.raise_for_status()
        except requests.HTTPError as error:
            try:
                body = response.json()
                message = body["error"]["message"]
                code = body["error"]["code"]
            except (ValueError, KeyError, TypeError):
                message = str(error)
                code = None
            raise RagApiError(message, code) from error

    def _get(self, path: str, retried: bool = False) -> requests.Response:
        response = requests.get(f"{self._base_url}{path}", headers=self._headers())
        if response.status_code == 401 and not retried:
            self._access_token = None
            return self._get(path, retried=True)
        self._raise_for_status(response)
        return response

    def _post(self, path: str, json: dict, retried: bool = False) -> requests.Response:
        response = requests.post(f"{self._base_url}{path}", headers=self._headers(), json=json)
        if response.status_code == 401 and not retried:
            self._access_token = None
            return self._post(path, json, retried=True)
        self._raise_for_status(response)
        return response

    def list_libraries(self) -> list[dict]:
        return self._get("/libraries").json()

    def query_library(self, library_id: str, query: str, top_k: int) -> list[dict]:
        response = self._post(f"/libraries/{library_id}/query", json={"query": query, "top_k": top_k})
        return response.json()["chunks"]
