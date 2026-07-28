import logging
import uuid

from mcp.server.fastmcp import FastMCP

from app.config import config
from app.constants import DEFAULT_TOP_K
from app.logging_config import configure_logging, reset_request_id, set_request_id
from mcp_server.client import RagApiClient

# Writes to stderr only (see app/logging_config.py) — stdout is the actual JSON-RPC protocol
# channel for this server's stdio transport, so it must never be written to by logging.
configure_logging(config.log_level)
logger = logging.getLogger(__name__)

mcp = FastMCP("rag-knowledge")
_client = RagApiClient()


@mcp.tool()
def list_libraries() -> list[dict]:
    """List all available knowledge libraries and their metadata."""
    token = set_request_id(str(uuid.uuid4())[:8])
    try:
        logger.info("MCP tool call: list_libraries")
        return _client.list_libraries()
    finally:
        reset_request_id(token)


@mcp.tool()
def query_library(library_id: str, query: str, top_k: int = DEFAULT_TOP_K) -> list[dict]:
    """Retrieve the most relevant chunks from a knowledge library for a query."""
    token = set_request_id(str(uuid.uuid4())[:8])
    try:
        logger.info(
            "MCP tool call: query_library", extra={"library_id": library_id, "top_k": top_k}
        )
        return _client.query_library(library_id, query, top_k)
    finally:
        reset_request_id(token)


if __name__ == "__main__":
    mcp.run(transport="stdio")
