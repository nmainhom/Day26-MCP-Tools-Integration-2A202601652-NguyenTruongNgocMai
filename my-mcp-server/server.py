"""Authenticated MCP server for searching a real application log file."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer


SERVER_VERSION = "2.0.0"
HOST = os.getenv("MCP_HOST", "127.0.0.1")
PORT = int(os.getenv("MCP_PORT", "8080"))
PUBLIC_URL = os.getenv("MCP_PUBLIC_URL", f"http://localhost:{PORT}")
AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN", "dev-log-token")
LOG_PATH = Path(
    os.getenv("APP_LOG_PATH", Path(__file__).parent / "data" / "app.log")
).resolve()

LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\S+) "
    r"(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL) "
    r"(?P<service>[A-Za-z0-9_.-]+) - "
    r"(?P<message>.+)$"
)


class StaticTokenVerifier(TokenVerifier):
    """Validate the bearer token supplied through MCP_AUTH_TOKEN."""

    async def verify_token(self, token: str) -> AccessToken | None:
        if token != AUTH_TOKEN:
            return None
        return AccessToken(
            token=token,
            client_id="log-analysis-client",
            scopes=["logs:read"],
        )


mcp = MCPServer(
    "log-analysis",
    instructions=(
        "Search application logs and inspect recent errors. Prefer "
        "search_logs_v2 for structured results."
    ),
    auth=AuthSettings(
        issuer_url=PUBLIC_URL,
        resource_server_url=PUBLIC_URL,
    ),
    token_verifier=StaticTokenVerifier(),
)


def _read_log_lines() -> list[str]:
    """Read non-empty log lines from disk for every tool call."""
    if not LOG_PATH.is_file():
        raise FileNotFoundError(f"Log file not found: {LOG_PATH}")
    return [
        line.strip()
        for line in LOG_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _parse_log_line(line: str) -> dict[str, Any]:
    """Convert one log line to a structured record."""
    match = LOG_PATTERN.match(line)
    if not match:
        return {"raw": line, "parsed": False}
    return {**match.groupdict(), "parsed": True}


@mcp.tool()
def search_logs(keyword: str) -> list[str]:
    """[v1, deprecated] Search log lines containing a keyword.

    Args:
        keyword: Case-insensitive text to find in the application log.
    """
    keyword = keyword.strip()
    if not keyword:
        raise ValueError("keyword must not be empty")
    return [line for line in _read_log_lines() if keyword.casefold() in line.casefold()]


@mcp.tool()
def get_recent_errors(limit: int = 10) -> list[str]:
    """Return the newest ERROR and CRITICAL log lines.

    Args:
        limit: Maximum number of records, from 1 to 100.
    """
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    errors = [
        line
        for line in _read_log_lines()
        if " ERROR " in line or " CRITICAL " in line
    ]
    return errors[-limit:][::-1]


@mcp.tool()
def search_logs_v2(
    keyword: str,
    level: str = "all",
    limit: int = 50,
) -> dict[str, Any]:
    """[v2] Search logs and return structured records with metadata.

    Args:
        keyword: Case-insensitive text to find in a complete log line.
        level: Optional level filter: all, debug, info, warning, error, critical.
        limit: Maximum number of records, from 1 to 100.
    """
    keyword = keyword.strip()
    normalized_level = level.strip().upper()
    valid_levels = {"ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

    if not keyword:
        raise ValueError("keyword must not be empty")
    if normalized_level not in valid_levels:
        raise ValueError(f"level must be one of: {', '.join(sorted(valid_levels))}")
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")

    records = []
    for line in _read_log_lines():
        if keyword.casefold() not in line.casefold():
            continue
        record = _parse_log_line(line)
        if normalized_level != "ALL" and record.get("level") != normalized_level:
            continue
        records.append(record)

    selected = records[:limit]
    return {
        "api_version": "2.0",
        "query": keyword,
        "level": normalized_level.lower(),
        "limit": limit,
        "total_matches": len(records),
        "returned": len(selected),
        "results": selected,
    }


@mcp.resource("server://info")
def server_info() -> str:
    """Publish server version, tools, and compatibility information."""
    return json.dumps(
        {
            "name": "log-analysis-mcp",
            "version": SERVER_VERSION,
            "data_source": str(LOG_PATH),
            "tools": {
                "search_logs": {"version": "1.0.0", "deprecated": True},
                "get_recent_errors": {"version": "1.0.0", "deprecated": False},
                "search_logs_v2": {"version": "2.0.0", "deprecated": False},
            },
            "migration": (
                "Use search_logs_v2 instead of search_logs for structured output. "
                "The keyword parameter is unchanged."
            ),
        },
        ensure_ascii=False,
    )


if __name__ == "__main__":
    print(f"Log file: {LOG_PATH}")
    print(f"MCP endpoint: http://{HOST}:{PORT}/mcp")
    mcp.run(transport="streamable-http", host=HOST, port=PORT)
