from __future__ import annotations

import argparse
import asyncio
import os

from creator_signup.infrai_gateway import InfraiGateway
from creator_signup.signup_service import CreatorSignup, SignupService


async def run(email: str) -> None:
    gateway = InfraiGateway(os.environ["INFRAI_API_KEY"])
    try:
        result = await SignupService(
            gateway, os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000")
        ).register(
            CreatorSignup(
                email=email,
                creator_name="Northwind Studio",
                asset_slug="launch-notes",
                subscriber_updates=True,
                request_id="demo-launch-notes-001",
            )
        )
        print(result.model_dump_json(indent=2))
    finally:
        await gateway.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("email")
    args = parser.parse_args()
    asyncio.run(run(args.email))

