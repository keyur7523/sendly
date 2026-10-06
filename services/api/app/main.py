from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.privy import CurrentUser
from app.chain.adapter import ChainAdapter
from app.chain.rpc import JsonRpcClient
from app.config import get_settings
from app.gate.routes import router as gate_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    rpc = JsonRpcClient(settings.rpc_url, settings.rpc_timeout_seconds)
    app.state.chain = ChainAdapter(rpc, settings)
    # Signer gate harness only: prepared transactions live in memory for one process.
    app.state.prepared = {}
    yield
    await rpc.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Sendly API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @app.get("/v1/me")
    async def me(user: CurrentUser):
        return {"privy_did": user.privy_did}

    app.include_router(gate_router)
    return app


app = create_app()
