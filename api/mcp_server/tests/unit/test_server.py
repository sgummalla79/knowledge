from api.mcp_server.server import build_mcp_servers

# Regression coverage for a real production incident: stateful streamable-http sessions are
# tracked in an in-memory dict scoped to one process, which silently breaks the moment there's more
# than one worker/replica behind a proxy that doesn't preserve per-client backend affinity (this
# repo's Traefik ingress doesn't) — a session minted on one process 404s "Session not found" on any
# follow-up request that lands elsewhere. See api/mcp_server/server.py's own comment.


def test_every_tier_server_is_stateless():
    servers = build_mcp_servers()

    assert len(servers) == 3
    for server in servers:
        assert server.settings.stateless_http is True
