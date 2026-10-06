"""Minimal async JSON-RPC client over httpx (bundled CA certificates, explicit timeouts)."""

from __future__ import annotations

import itertools
from typing import Any

import httpx


class RpcError(Exception):
    """The node answered with a JSON-RPC error (e.g. nonce too low, execution reverted)."""

    def __init__(self, method: str, code: int | None, message: str, data: Any = None):
        super().__init__(f"{method}: {message}")
        self.method = method
        self.code = code
        self.message = message
        self.data = data


class RpcUnavailable(Exception):
    """Transport failure or malformed response. The outcome of a write is unknown."""


class JsonRpcClient:
    def __init__(self, url: str, timeout: float, transport: httpx.AsyncBaseTransport | None = None):
        self._client = httpx.AsyncClient(timeout=timeout, transport=transport)
        self._url = url
        self._ids = itertools.count(1)

    async def call(self, method: str, *params: Any) -> Any:
        body = {"jsonrpc": "2.0", "id": next(self._ids), "method": method, "params": list(params)}
        try:
            response = await self._client.post(self._url, json=body)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RpcUnavailable(f"{method}: {exc}") from exc
        if "error" in payload:
            err = payload["error"] or {}
            raise RpcError(method, err.get("code"), err.get("message", "unknown error"), err.get("data"))
        if "result" not in payload:
            raise RpcUnavailable(f"{method}: response has no result")
        return payload["result"]

    async def aclose(self) -> None:
        await self._client.aclose()
