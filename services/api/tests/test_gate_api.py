"""Gate API against a fake JSON-RPC node. No network access."""

import json

import httpx
import pytest
from eth_account import Account
from fastapi.testclient import TestClient

from app.chain.adapter import ChainAdapter
from app.chain.payload import TRANSFER_EVENT_TOPIC
from app.chain.rpc import JsonRpcClient
from app.config import get_settings
from app.main import app
from tests.conftest import TOKEN_ADDRESS

RECIPIENT = "0x2222222222222222222222222222222222222222"
BASE_FEE = 100_000_000_000
PRIORITY = 2_000_000_000


class FakeNode:
    def __init__(self):
        self.nonce = 5
        self.code = "0x"
        self.transactions: dict[str, dict] = {}
        self.receipts: dict[str, dict] = {}
        self.finalized = 1_000
        self.send_error: dict | None = None
        self.calls: list[str] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        method, params = body["method"], body["params"]
        self.calls.append(method)
        result = self.dispatch(method, params)
        if isinstance(result, dict) and "__error__" in result:
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "error": result["__error__"]})
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": result})

    def dispatch(self, method, params):
        match method:
            case "eth_chainId":
                return hex(10143)
            case "eth_getTransactionCount":
                return hex(self.nonce)
            case "eth_getCode":
                return self.code
            case "eth_getBalance":
                return hex(10**19)
            case "eth_call":
                return hex(100_000_000)
            case "eth_estimateGas":
                return hex(50_000)
            case "eth_maxPriorityFeePerGas":
                return hex(PRIORITY)
            case "eth_getBlockByNumber":
                tag = params[0]
                if tag == "latest":
                    return {"number": hex(self.finalized + 3), "baseFeePerGas": hex(BASE_FEE), "hash": "0xlatest"}
                if tag == "finalized":
                    return {"number": hex(self.finalized), "hash": "0xfinal"}
                return {"number": tag, "hash": f"0xblock{int(tag, 16)}"}
            case "eth_sendRawTransaction":
                return {"__error__": self.send_error} if self.send_error else "0xaccepted"
            case "eth_getTransactionByHash":
                return self.transactions.get(params[0])
            case "eth_getTransactionReceipt":
                return self.receipts.get(params[0])
        raise AssertionError(f"unexpected RPC {method}")


@pytest.fixture
def node():
    return FakeNode()


@pytest.fixture
def client(node, tmp_path):
    settings = get_settings()
    settings.gate_results_path = tmp_path / "results.jsonl"
    with TestClient(app) as c:
        rpc = JsonRpcClient("http://fake-rpc.invalid", 5, transport=httpx.MockTransport(node.handle))
        app.state.chain = ChainAdapter(rpc, settings)
        yield c


def prepare_transfer(client, headers, sender):
    r = client.post(
        "/v1/gate/prepare",
        json={"sender": sender, "kind": "token_transfer", "recipient": RECIPIENT, "amount": "15"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


def sign(account, pinned, **overrides):
    body = {
        "type": 2,
        "chainId": int(pinned["chain_id"]),
        "nonce": int(pinned["nonce"]),
        "to": pinned["to"],
        "value": int(pinned["value"]),
        "data": pinned["data"],
        "gas": int(pinned["gas"]),
        "maxFeePerGas": int(pinned["max_fee_per_gas"]),
        "maxPriorityFeePerGas": int(pinned["max_priority_fee_per_gas"]),
    }
    body.update(overrides)
    signed = account.sign_transaction(body)
    return "0x" + signed.raw_transaction.hex(), "0x" + signed.hash.hex().removeprefix("0x")


def rpc_tx(account, pinned, tx_hash, **overrides):
    tx = {
        "hash": tx_hash,
        "from": account.address,
        "chainId": hex(int(pinned["chain_id"])),
        "to": pinned["to"],
        "input": pinned["data"],
        "value": "0x0",
        "nonce": hex(int(pinned["nonce"])),
        "gas": hex(int(pinned["gas"])),
        "maxFeePerGas": hex(int(pinned["max_fee_per_gas"])),
        "maxPriorityFeePerGas": hex(int(pinned["max_priority_fee_per_gas"])),
        "type": "0x2",
    }
    tx.update(overrides)
    return tx


def receipt(account, block, status=1):
    return {
        "blockNumber": hex(block),
        "blockHash": f"0xblock{block}",
        "status": hex(status),
        "gasUsed": hex(40_000),
        "effectiveGasPrice": hex(BASE_FEE + PRIORITY),
        "logs": [
            {
                "address": TOKEN_ADDRESS,
                "topics": [
                    TRANSFER_EVENT_TOPIC,
                    "0x" + "0" * 24 + account.address[2:].lower(),
                    "0x" + "0" * 24 + RECIPIENT[2:].lower(),
                ],
                "data": hex(15_000_000),
            }
        ],
    }


def test_requires_authentication(client):
    assert client.post("/v1/gate/prepare", json={}).status_code == 401
    assert client.get("/v1/gate/wallet", params={"address": RECIPIENT}).status_code == 401


def test_prepare_pins_every_field(client, auth_header):
    acct = Account.create()
    out = prepare_transfer(client, auth_header(), acct.address)
    pinned = out["pinned"]
    assert pinned["nonce"] == "5"
    assert pinned["gas"] == str(55_000)  # 50,000 estimate + 10% margin
    assert pinned["max_fee_per_gas"] == str(2 * BASE_FEE + PRIORITY)
    assert pinned["max_priority_fee_per_gas"] == str(PRIORITY)
    assert pinned["value"] == "0" and pinned["to"] == TOKEN_ADDRESS
    assert pinned["fee_bound"] == str(55_000 * (2 * BASE_FEE + PRIORITY))
    assert out["wallet_request"]["gasLimit"] == hex(55_000)


def test_prepare_rejects_over_precise_amount(client, auth_header):
    r = client.post(
        "/v1/gate/prepare",
        json={"sender": Account.create().address, "kind": "token_transfer", "recipient": RECIPIENT, "amount": "1.0000001"},
        headers=auth_header(),
    )
    assert r.status_code == 400 and r.json()["detail"]["code"] == "AMOUNT_INVALID"


def test_replacement_shape_uses_override_nonce(client, auth_header):
    acct = Account.create()
    r = client.post(
        "/v1/gate/prepare", json={"sender": acct.address, "kind": "self_transfer", "nonce": 3}, headers=auth_header()
    )
    pinned = r.json()["pinned"]
    assert pinned["to"] == acct.address and pinned["value"] == "0" and pinned["data"] == "0x"
    assert pinned["nonce"] == "3" and pinned["gas"] == "21000"


def test_prepared_transaction_is_private_to_its_user(client, auth_header):
    acct = Account.create()
    out = prepare_transfer(client, auth_header("did:privy:alice"), acct.address)
    raw, _ = sign(acct, out["pinned"])
    r = client.post(
        "/v1/gate/inspect-signed",
        json={"prepared_id": out["prepared_id"], "signed_transaction": raw},
        headers=auth_header("did:privy:mallory"),
    )
    assert r.status_code == 404


def test_inspect_signed_reports_fee_change_as_compliance_only(client, auth_header):
    acct = Account.create()
    out = prepare_transfer(client, auth_header(), acct.address)
    raw, tx_hash = sign(acct, out["pinned"], maxFeePerGas=999 * 10**9)
    r = client.post(
        "/v1/gate/inspect-signed", json={"prepared_id": out["prepared_id"], "signed_transaction": raw}, headers=auth_header()
    ).json()
    assert r["tx_hash"] == tx_hash
    assert r["comparison"]["payload_matches"] is True
    assert r["comparison"]["field_compliance"] == "mismatched"


def test_broadcast_reports_node_rejection(client, auth_header, node):
    acct = Account.create()
    out = prepare_transfer(client, auth_header(), acct.address)
    raw, tx_hash = sign(acct, out["pinned"])
    node.send_error = {"code": -32000, "message": "nonce too low"}
    r = client.post(
        "/v1/gate/broadcast", json={"prepared_id": out["prepared_id"], "signed_transaction": raw}, headers=auth_header()
    ).json()
    assert r["broadcast"] == "rejected" and r["tx_hash"] == tx_hash
    assert r["rpc_error"]["message"] == "nonce too low"


def test_verify_distinguishes_included_from_finalized(client, auth_header, node):
    acct = Account.create()
    out = prepare_transfer(client, auth_header(), acct.address)
    tx_hash = "0x" + "ab" * 32
    node.transactions[tx_hash] = rpc_tx(acct, out["pinned"], tx_hash)

    def verify():
        return client.post(
            "/v1/gate/verify", json={"prepared_id": out["prepared_id"], "tx_hash": tx_hash}, headers=auth_header()
        ).json()

    assert verify()["status"] == "pending"

    node.receipts[tx_hash] = receipt(acct, block=node.finalized + 2)
    included = verify()
    assert included["status"] == "included" and included["receipt_status"] == "success"

    node.finalized += 5
    done = verify()
    assert done["status"] == "finalized"
    assert done["transfer_event_found"] is True
    assert done["comparison"]["field_compliance"] == "matched"
    # Monad charges the gas limit, not gas used.
    assert done["fee_charged_wei"] == str(int(out["pinned"]["gas"]) * (BASE_FEE + PRIORITY))


def test_verify_keeps_payment_outcome_when_fee_fields_differ(client, auth_header, node):
    acct = Account.create()
    out = prepare_transfer(client, auth_header(), acct.address)
    tx_hash = "0x" + "cd" * 32
    node.transactions[tx_hash] = rpc_tx(acct, out["pinned"], tx_hash, gas=hex(90_000))
    node.receipts[tx_hash] = receipt(acct, block=node.finalized - 1)
    r = client.post(
        "/v1/gate/verify", json={"prepared_id": out["prepared_id"], "tx_hash": tx_hash}, headers=auth_header()
    ).json()
    assert r["status"] == "finalized" and r["receipt_status"] == "success"
    assert r["comparison"]["payload_matches"] is True
    assert r["comparison"]["field_compliance"] == "mismatched"


def test_wallet_reports_type_and_nonces(client, auth_header, node):
    node.code = "0xef0100" + "44" * 20
    r = client.get("/v1/gate/wallet", params={"address": RECIPIENT}, headers=auth_header()).json()
    assert r["wallet"]["wallet_type"] == "eip7702_delegated"
    assert r["token"]["balance_base_units"] == "100000000"


def test_results_are_appended(client, auth_header):
    body = {
        "case": "pinned_send",
        "mode": "send",
        "passed": True,
        "sdk_package": "@privy-io/react-auth",
        "sdk_version": "3.47.0",
        "summary": "fields preserved",
    }
    r = client.post("/v1/gate/results", json=body, headers=auth_header())
    assert r.status_code == 200
    lines = get_settings().gate_results_path.read_text().splitlines()
    assert json.loads(lines[-1])["case"] == "pinned_send"


def test_token_transfer_without_configured_token(client, auth_header, monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_token_address", None)
    r = client.post(
        "/v1/gate/prepare",
        json={"sender": Account.create().address, "kind": "token_transfer", "recipient": RECIPIENT, "amount": "1"},
        headers=auth_header(),
    )
    assert r.status_code == 503 and r.json()["detail"]["code"] == "UNSUPPORTED_ASSET"
