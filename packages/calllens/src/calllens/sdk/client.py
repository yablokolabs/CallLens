"""Async Python SDK for CallLens.

```python
from calllens import CallLens

client = CallLens(base_url="http://localhost:8000")
call = await client.calls.upload("sales-call.mp3")
result = await call.analyze(rubric="consultative-sales")
print(result.overall_score)
```
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx


class CallLensError(RuntimeError):
    """Raised when the CallLens API returns an error."""


class _CallsResource:
    def __init__(self, client: CallLens) -> None:
        self._client = client

    async def upload(self, path: str | Path, *, filename: str | None = None) -> Call:
        """Upload an audio file or transcript and register a call."""
        p = Path(path)
        url = f"{self._client.base_url}/api/v1/calls"
        files = {"file": (filename or p.name, p.read_bytes())}
        data: dict[str, Any] = {}
        if p.suffix.lower() in {".json", ".txt"}:
            data["transcript_source"] = p.read_text(encoding="utf-8")
        resp = await self._client._http.post(url, files=files, data=data)  # noqa: SLF001
        payload = self._client._expect(resp)  # noqa: SLF001
        return Call(self._client, payload["id"])

    async def list(self, **params: Any) -> list[dict[str, Any]]:
        resp = await self._client._http.get(f"{self._client.base_url}/api/v1/calls", params=params)  # noqa: SLF001
        return self._client._expect(resp)  # noqa: SLF001

    async def get(self, call_id: str) -> dict[str, Any]:
        resp = await self._client._http.get(f"{self._client.base_url}/api/v1/calls/{call_id}")  # noqa: SLF001
        return self._client._expect(resp)  # noqa: SLF001


class Call:
    """A remote call resource."""

    def __init__(self, client: CallLens, call_id: str) -> None:
        self._client = client
        self.id = call_id

    async def analyze(self, rubric: str = "consultative_sales") -> dict[str, Any]:
        resp = await self._client._http.post(  # noqa: SLF001
            f"{self._client.base_url}/api/v1/calls/{self.id}/analyze",
            json={"rubric_name": rubric},
        )
        return self._client._expect(resp)  # noqa: SLF001

    async def report(self) -> dict[str, Any]:
        resp = await self._client._http.get(
            f"{self._client.base_url}/api/v1/calls/{self.id}/analysis"
        )  # noqa: SLF001
        return self._client._expect(resp)  # noqa: SLF001

    async def delete(self) -> None:
        resp = await self._client._http.delete(f"{self._client.base_url}/api/v1/calls/{self.id}")  # noqa: SLF001
        self._client._expect(resp)  # noqa: SLF001


class CallLens:
    """CallLens API client."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        *,
        api_key: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._http = httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=timeout)
        self.calls = _CallsResource(self)

    @staticmethod
    def _expect(resp: httpx.Response) -> Any:
        if resp.status_code >= 400:
            detail = resp.text[:300]
            raise CallLensError(f"CallLens API error {resp.status_code}: {detail}")
        if resp.status_code == 204:
            return None
        return resp.json()

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> CallLens:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()
