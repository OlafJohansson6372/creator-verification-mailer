from __future__ import annotations

import asyncio
from typing import Any, Mapping

from creator_signup.signup_service import CreatorSignup, SignupService


class RecordingGateway:
    def __init__(self) -> None:
        self.created: dict[str, Any] = {}
        self.sent: dict[str, Any] = {}

    async def create_user(self, **kwargs: Any) -> Mapping[str, Any]:
        self.created = kwargs
        return {"user_id": "usr_creator_42"}

    async def send_verification_email(self, **kwargs: Any) -> Mapping[str, Any]:
        self.sent = kwargs
        return {"message_id": "msg_verify_42"}


def test_auth_identity_flows_directly_into_verification_mail() -> None:
    gateway = RecordingGateway()
    signup = CreatorSignup(
        email="maker@example.com",
        creator_name="Mira Makes",
        asset_slug="lighting-presets",
        subscriber_updates=True,
        request_id="signup-request-42",
    )

    result = asyncio.run(SignupService(gateway, "https://creator.example").register(signup))  # type: ignore[arg-type]

    assert result.status == "verification_pending"
    assert result.asset_slug == "lighting-presets"
    assert gateway.created["metadata"] == {
        "asset_slug": "lighting-presets",
        "subscriber_updates": True,
        "delivery_state": "verification_pending",
    }
    assert gateway.sent["verification_url"] == (
        "https://creator.example/verify?user_id=usr_creator_42&asset=lighting-presets"
    )

