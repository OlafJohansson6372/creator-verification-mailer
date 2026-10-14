from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .infrai_gateway import InfraiError, InfraiGateway
from .signup_service import CreatorSignup, PendingDelivery, SignupService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    api_key = os.environ["INFRAI_API_KEY"]
    public_base_url = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000")
    gateway = InfraiGateway(api_key)
    app.state.signup_service = SignupService(gateway, public_base_url)
    yield
    await gateway.close()


app = FastAPI(title="Creator verification signup", lifespan=lifespan)


@app.exception_handler(InfraiError)
async def infrai_error_handler(_request: Request, error: InfraiError) -> JSONResponse:
    status = error.status_code if 400 <= error.status_code < 500 else 502
    return JSONResponse(
        status_code=status,
        content={"detail": {"code": error.code, "message": str(error)}},
    )


@app.post("/signups", response_model=PendingDelivery, status_code=202)
async def create_signup(signup: CreatorSignup, request: Request) -> PendingDelivery:
    service: SignupService = request.app.state.signup_service
    return await service.register(signup)
