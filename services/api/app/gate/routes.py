"""Signer gate harness (PRD Section 10.4, build stage B2).

These endpoints exist to measure what the wallet SDK does with a fully pinned transaction.
They are not the payment API: no drafts, approvals, or reservations, and the wallet address
is taken from the client without an ownership binding (that arrives with B3).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth.privy import CurrentUser
from app.chain.adapter import ChainAdapter, ChainMismatch, TokenNotConfigured, Verification
from app.chain.payload import (
    PayloadError,
    PinnedTransaction,
    compare,
    decode_signed_transaction,
    parse_amount,
    require_address,
)
from app.chain.rpc import RpcError, RpcUnavailable
from app.config import Settings, get_settings

router = APIRouter(prefix="/v1/gate", tags=["signer-gate"])

GateCase = Literal["pinned_send", "pinned_sign_only", "explicit_rejection", "same_nonce_replacement", "wallet_type"]


def get_adapter(request: Request) -> ChainAdapter:
    return request.app.state.chain


def get_store(request: Request) -> dict[str, dict[str, Any]]:
    return request.app.state.prepared


Adapter = Annotated[ChainAdapter, Depends(get_adapter)]
Store = Annotated[dict[str, dict[str, Any]], Depends(get_store)]


class PrepareRequest(BaseModel):
    sender: str
    kind: Literal["token_transfer", "self_transfer"]
    recipient: str | None = None
    amount: str | None = Field(default=None, description="Exact decimal string, e.g. '1.50'")
    nonce: int | None = Field(default=None, ge=0, description="Override, for the replacement case only")


class SignedRequest(BaseModel):
    prepared_id: str
    signed_transaction: str


class VerifyRequest(BaseModel):
    prepared_id: str
    tx_hash: str


class ResultRequest(BaseModel):
    case: GateCase
    mode: Literal["send", "sign_only", "n/a"]
    passed: bool | None = Field(description="None when the case is inconclusive")
    sdk_package: str
    sdk_version: str
    summary: str
    details: dict[str, Any] = {}


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status, detail={"code": code, "message": message})


def _lookup(store: dict[str, dict[str, Any]], prepared_id: str, user_did: str) -> PinnedTransaction:
    entry = store.get(prepared_id)
    if entry is None or entry["owner"] != user_did:
        raise _error(404, "NOT_FOUND", "unknown prepared transaction")
    return entry["tx"]


def _comparison_json(comparison: Any) -> dict[str, Any] | None:
    return asdict(comparison) if comparison is not None else None


def _verification_json(v: Verification) -> dict[str, Any]:
    return {
        "status": v.status,
        "receipt_status": v.receipt_status,
        "block_number": v.block_number,
        "finalized_block_number": v.finalized_block_number,
        "transfer_event_found": v.transfer_event_found,
        "fee_charged_wei": str(v.fee_charged) if v.fee_charged is not None else None,
        "observed": {k: (str(x) if isinstance(x, int) else x) for k, x in asdict(v.observed).items()}
        if v.observed
        else None,
        "comparison": _comparison_json(v.comparison),
    }


@router.get("/wallet")
async def wallet(address: str, user: CurrentUser, chain: Adapter, settings: Annotated[Settings, Depends(get_settings)]):
    try:
        address = require_address(address, "address")
        await chain.check_chain()
        token_balance = (
            await chain.token_balance(settings.demo_token_address, address) if settings.demo_token_address else None
        )
        return {
            "address": address,
            "chain_id": settings.chain_id,
            "wallet": await chain.wallet_type(address),
            "native_balance_wei": str(await chain.native_balance(address)),
            "token": {
                "address": settings.demo_token_address,
                "symbol": settings.demo_token_symbol,
                "decimals": settings.demo_token_decimals,
                "balance_base_units": str(token_balance) if token_balance is not None else None,
            },
            "nonce_latest": await chain.nonce(address, "latest"),
            "nonce_pending": await chain.nonce(address, "pending"),
        }
    except PayloadError as exc:
        raise _error(400, "INVALID_ADDRESS", str(exc)) from None
    except ChainMismatch as exc:
        raise _error(503, "WRONG_NETWORK", str(exc)) from None
    except (RpcError, RpcUnavailable) as exc:
        raise _error(503, "CHAIN_UNAVAILABLE", str(exc)) from None


@router.post("/prepare")
async def prepare(
    body: PrepareRequest,
    user: CurrentUser,
    chain: Adapter,
    store: Store,
    settings: Annotated[Settings, Depends(get_settings)],
):
    try:
        if body.kind == "token_transfer":
            if not body.recipient or not body.amount:
                raise PayloadError("token_transfer requires recipient and amount")
            amount = parse_amount(body.amount, settings.demo_token_decimals)
            tx = await chain.pin_token_transfer(body.sender, body.recipient, amount, body.nonce)
        else:
            tx = await chain.pin_self_transfer(body.sender, body.nonce)
    except PayloadError as exc:
        raise _error(400, "AMOUNT_INVALID" if body.amount else "INVALID_REQUEST", str(exc)) from None
    except TokenNotConfigured as exc:
        raise _error(503, "UNSUPPORTED_ASSET", str(exc)) from None
    except ChainMismatch as exc:
        raise _error(503, "WRONG_NETWORK", str(exc)) from None
    except RpcError as exc:
        # eth_estimateGas reverts, e.g. insufficient token balance.
        raise _error(422, "ESTIMATE_FAILED", exc.message) from None
    except RpcUnavailable as exc:
        raise _error(503, "CHAIN_UNAVAILABLE", str(exc)) from None

    prepared_id = str(uuid.uuid4())
    store[prepared_id] = {"owner": user.privy_did, "tx": tx}
    return {"prepared_id": prepared_id, "pinned": tx.to_json(), "wallet_request": tx.to_wallet_request()}


@router.post("/inspect-signed")
async def inspect_signed(body: SignedRequest, user: CurrentUser, store: Store):
    """Sign-only mode: decode and compare without broadcasting."""
    expected = _lookup(store, body.prepared_id, user.privy_did)
    try:
        observed = decode_signed_transaction(body.signed_transaction)
    except PayloadError as exc:
        raise _error(400, "UNDECODABLE_SIGNED_TRANSACTION", str(exc)) from None
    return {
        "tx_hash": observed.hash,
        "observed": {k: (str(x) if isinstance(x, int) else x) for k, x in asdict(observed).items()},
        "comparison": asdict(compare(expected, observed)),
    }


@router.post("/broadcast")
async def broadcast(body: SignedRequest, user: CurrentUser, chain: Adapter, store: Store):
    """Broadcast a sign-only transaction. The hash is known before broadcast; a transport
    failure therefore leaves a known hash with an unknown outcome, never a lost one."""
    expected = _lookup(store, body.prepared_id, user.privy_did)
    try:
        observed = decode_signed_transaction(body.signed_transaction)
    except PayloadError as exc:
        raise _error(400, "UNDECODABLE_SIGNED_TRANSACTION", str(exc)) from None
    comparison = compare(expected, observed)
    result: dict[str, Any] = {"tx_hash": observed.hash, "comparison": asdict(comparison)}
    try:
        result["rpc_hash"] = await chain.broadcast(body.signed_transaction)
        result["broadcast"] = "accepted"
    except RpcError as exc:
        result["broadcast"] = "rejected"
        result["rpc_error"] = {"code": exc.code, "message": exc.message}
    except RpcUnavailable as exc:
        result["broadcast"] = "unknown"
        result["rpc_error"] = {"code": None, "message": str(exc)}
    return result


@router.post("/verify")
async def verify(body: VerifyRequest, user: CurrentUser, chain: Adapter, store: Store):
    expected = _lookup(store, body.prepared_id, user.privy_did)
    try:
        return _verification_json(await chain.verify(expected, body.tx_hash))
    except (RpcError, RpcUnavailable) as exc:
        raise _error(503, "CHAIN_UNAVAILABLE", str(exc)) from None


@router.post("/results")
async def record_result(body: ResultRequest, user: CurrentUser, settings: Annotated[Settings, Depends(get_settings)]):
    record = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "chain_id": settings.chain_id,
        "user": user.privy_did,
        **body.model_dump(),
    }
    path = settings.gate_results_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    return {"recorded": True, "path": str(path)}
