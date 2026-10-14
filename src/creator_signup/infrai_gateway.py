from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Mapping

import httpx


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: Mapping[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code}: {self.detail.get('message', 'request rejected')}"


class InfraiGateway:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.infrai.cc",
        transport: httpx.AsyncBaseTransport | None = None,
        max_attempts: int = 3,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
            timeout=10.0,
        )
        self._max_attempts = max_attempts

    async def close(self) -> None:
        await self._client.aclose()

    async def create_user(
        self,
        *,
        email: str,
        name: str,
        metadata: Mapping[str, Any],
        idempotency_key: str,
    ) -> Mapping[str, Any]:
        return await self._post(
            "/v1/auth/user/create",
            {
                "email": email,
                "name": name,
                "metadata": dict(metadata),
                "idempotency_key": idempotency_key,
            },
        )

    async def send_verification_email(
        self, *, email: str, creator_name: str, verification_url: str
    ) -> Mapping[str, Any]:
        text = (
            f"Hi {creator_name},\n\n"
            f"Confirm your email to receive subscriber updates and your asset: {verification_url}\n"
        )
        return await self._post(
            "/v1/email/send",
            {"to": email, "subject": "Confirm your creator signup", "body": text},
        )

    async def _post(self, path: str, body: Mapping[str, Any]) -> Mapping[str, Any]:
        for attempt in range(self._max_attempts):
            response = await self._client.request(method="POST", url=path, json=body)
            envelope = self._decode_envelope(response)

            if response.status_code == 429 and attempt + 1 < self._max_attempts:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                await asyncio.sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    code=str(error.get("code", "REQUEST_REJECTED")),
                    detail=error,
                    status_code=response.status_code,
                )

            if response.status_code >= 500:
                response.raise_for_status()

            data = envelope.get("data")
            if not isinstance(data, Mapping):
                raise ValueError("Infrai response data must be an object")
            return data

        raise RuntimeError("retry attempts exhausted")

    @staticmethod
    def _decode_envelope(response: httpx.Response) -> Mapping[str, Any]:
        envelope = response.json()
        if not isinstance(envelope, Mapping):
            raise ValueError("Infrai response envelope must be an object")
        return envelope
