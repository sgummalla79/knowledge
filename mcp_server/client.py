import requests

from app.config import config


class RagApiError(Exception):
    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.code = code


class RagApiClient:
    """Calls the Flask API over loopback HTTP from inside the same container.

    Reuses app.config so the same API_KEY the Flask app enforces is the one presented here —
    no separate credential to keep in sync.
    """

    def __init__(self):
        self._base_url = f"http://localhost:{config.port}"
        self._headers = {"X-API-Key": config.api_key}

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

    def list_libraries(self) -> list[dict]:
        response = requests.get(f"{self._base_url}/libraries", headers=self._headers)
        self._raise_for_status(response)
        return response.json()

    def query_library(self, library_id: str, query: str, top_k: int) -> list[dict]:
        response = requests.post(
            f"{self._base_url}/libraries/{library_id}/query",
            headers=self._headers,
            json={"query": query, "top_k": top_k},
        )
        self._raise_for_status(response)
        return response.json()["chunks"]
