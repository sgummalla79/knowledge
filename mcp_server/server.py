from mcp.server.fastmcp import FastMCP

from app.constants import DEFAULT_TOP_K
from mcp_server.client import RagApiClient

mcp = FastMCP("rag-knowledge")
_client = RagApiClient()


@mcp.tool()
def list_libraries() -> list[dict]:
    """List all available knowledge libraries and their metadata."""
    return _client.list_libraries()


@mcp.tool()
def query_library(library_id: str, query: str, top_k: int = DEFAULT_TOP_K) -> list[dict]:
    """Retrieve the most relevant chunks from a knowledge library for a query."""
    return _client.query_library(library_id, query, top_k)


if __name__ == "__main__":
    mcp.run(transport="stdio")
