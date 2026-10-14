from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from urllib.parse import urlencode

from pydantic import BaseModel, EmailStr, Field, HttpUrl

from .infrai_gateway import InfraiGateway


class CreatorSignup(BaseModel):
    email: EmailStr
    creator_name: str = Field(min_length=1, max_length=80)
    asset_slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    subscriber_updates: bool
    request_id: str = Field(min_length=8, max_length=100)


class PendingDelivery(BaseModel):
    user_id: str
    message_id: str
    asset_slug: str
    status: str


@dataclass(frozen=True)
class SignupService:
    infrai: InfraiGateway
    public_base_url: str

    async def register(self, signup: CreatorSignup) -> PendingDelivery:
        idempotency_key = sha256(signup.request_id.encode("utf-8")).hexdigest()
        user = await self.infrai.create_user(
            email=str(signup.email),
            name=signup.creator_name,
            metadata={
                "asset_slug": signup.asset_slug,
                "subscriber_updates": signup.subscriber_updates,
                "delivery_state": "verification_pending",
            },
            idempotency_key=idempotency_key,
        )
        user_id = str(user["user_id"])
        query = urlencode({"user_id": user_id, "asset": signup.asset_slug})
        verification_url = f"{self.public_base_url.rstrip('/')}/verify?{query}"
        mail = await self.infrai.send_verification_email(
            email=str(signup.email),
            creator_name=signup.creator_name,
            verification_url=verification_url,
        )
        return PendingDelivery(
            user_id=user_id,
            message_id=str(mail["message_id"]),
            asset_slug=signup.asset_slug,
            status="verification_pending",
        )

