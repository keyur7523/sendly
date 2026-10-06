"""Pure transaction logic: build pinned payloads, decode signed transactions, and apply the
PRD's matching rule (Section 9.4) and field-compliance check (Section 9.5) separately.

Nothing here performs I/O, so every rule is unit-testable.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from eth_abi import decode as abi_decode
from eth_abi import encode as abi_encode
from eth_account import Account
from eth_account.typed_transactions import TypedTransaction
from eth_utils import is_address, keccak, to_checksum_address
from hexbytes import HexBytes

TRANSFER_SELECTOR = keccak(text="transfer(address,uint256)")[:4]
TRANSFER_EVENT_TOPIC = "0x" + keccak(text="Transfer(address,address,uint256)").hex()
EIP7702_DELEGATION_PREFIX = bytes.fromhex("ef0100")
MAX_UINT256 = 2**256 - 1

# Fields that decide whether a transaction *is* the approved payment (matching rule).
PAYLOAD_FIELDS = ("chain_id", "to", "data", "value")
# Fields checked for compliance only; a mismatch never changes the payment outcome.
COMPLIANCE_FIELDS = ("nonce", "gas", "max_fee_per_gas", "max_priority_fee_per_gas", "type")


class PayloadError(ValueError):
    pass


@dataclass(frozen=True)
class PinnedTransaction:
    """A fully specified type-2 transaction. Integers are exact; serialized as strings."""

    chain_id: int
    sender: str
    to: str
    data: str
    value: int
    nonce: int
    gas: int
    max_fee_per_gas: int
    max_priority_fee_per_gas: int
    type: int = 2

    @property
    def fee_bound(self) -> int:
        return self.gas * self.max_fee_per_gas

    def digest(self) -> str:
        """Canonical digest: fixed field names, lowercase hex, integers as decimal strings."""
        canonical = {
            "chain_id": str(self.chain_id),
            "sender": self.sender.lower(),
            "to": self.to.lower(),
            "data": self.data.lower(),
            "value": str(self.value),
            "nonce": str(self.nonce),
            "gas": str(self.gas),
            "max_fee_per_gas": str(self.max_fee_per_gas),
            "max_priority_fee_per_gas": str(self.max_priority_fee_per_gas),
            "type": str(self.type),
        }
        encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        return "0x" + hashlib.sha256(encoded).hexdigest()

    def to_wallet_request(self) -> dict[str, Any]:
        """Shape passed to the wallet SDK; quantities as hex strings to avoid JS number loss."""
        return {
            "chainId": self.chain_id,
            "from": self.sender,
            "to": self.to,
            "data": self.data,
            "value": hex(self.value),
            "nonce": self.nonce,
            "gasLimit": hex(self.gas),
            "maxFeePerGas": hex(self.max_fee_per_gas),
            "maxPriorityFeePerGas": hex(self.max_priority_fee_per_gas),
            "type": self.type,
        }

    def to_json(self) -> dict[str, Any]:
        out = {k: (str(v) if isinstance(v, int) else v) for k, v in asdict(self).items()}
        out["fee_bound"] = str(self.fee_bound)
        out["digest"] = self.digest()
        return out


@dataclass(frozen=True)
class ObservedTransaction:
    """A transaction as signed or as found on chain, normalized for comparison."""

    hash: str
    sender: str
    chain_id: int
    to: str
    data: str
    value: int
    nonce: int
    gas: int
    max_fee_per_gas: int | None
    max_priority_fee_per_gas: int | None
    type: int


@dataclass(frozen=True)
class FieldDifference:
    field: str
    expected: str
    observed: str


@dataclass(frozen=True)
class Comparison:
    payload_matches: bool
    payload_differences: list[FieldDifference]
    sender_matches: bool
    field_compliance: str  # "matched" | "mismatched"
    compliance_differences: list[FieldDifference]


def require_address(value: str, label: str) -> str:
    if not is_address(value):
        raise PayloadError(f"{label} is not a valid address")
    return to_checksum_address(value)


def parse_amount(display: str, decimals: int) -> int:
    """Exact decimal string -> integer base units. Rejects over-precision; no floats."""
    try:
        amount = Decimal(display)
    except InvalidOperation as exc:
        raise PayloadError("amount is not a decimal number") from exc
    if not amount.is_finite() or amount <= 0:
        raise PayloadError("amount must be greater than zero")
    exponent = amount.as_tuple().exponent
    if isinstance(exponent, int) and -exponent > decimals:
        raise PayloadError(f"amount has more than {decimals} decimal places")
    base_units = int(amount.scaleb(decimals))
    if base_units > MAX_UINT256:
        raise PayloadError("amount is too large")
    return base_units


def encode_token_transfer(recipient: str, amount_base_units: int) -> str:
    if amount_base_units <= 0:
        raise PayloadError("amount must be greater than zero")
    recipient = require_address(recipient, "recipient")
    return "0x" + (TRANSFER_SELECTOR + abi_encode(["address", "uint256"], [recipient, amount_base_units])).hex()


def decode_token_transfer(data: str) -> tuple[str, int] | None:
    raw = bytes.fromhex(data.removeprefix("0x"))
    if len(raw) != 68 or raw[:4] != TRANSFER_SELECTOR:
        return None
    recipient, amount = abi_decode(["address", "uint256"], raw[4:])
    return to_checksum_address(recipient), amount


def classify_account_code(code: str) -> dict[str, Any]:
    """Wallet type from account code: plain EOA, EIP-7702 delegated EOA, or contract."""
    raw = bytes.fromhex(code.removeprefix("0x"))
    if not raw:
        return {"wallet_type": "eoa", "delegated": False}
    if len(raw) == 23 and raw.startswith(EIP7702_DELEGATION_PREFIX):
        return {"wallet_type": "eip7702_delegated", "delegated": True, "delegate": to_checksum_address(raw[3:])}
    return {"wallet_type": "contract", "delegated": False}


def decode_signed_transaction(raw_hex: str) -> ObservedTransaction:
    """Decode a signed raw transaction (sign-only mode) without broadcasting it."""
    try:
        raw = HexBytes(raw_hex)
        typed = TypedTransaction.from_bytes(raw)
        fields = typed.as_dict()
        sender = Account.recover_transaction(raw)
    except Exception as exc:  # malformed input from the client
        raise PayloadError("not a decodable signed typed transaction") from exc
    if fields.get("type") != 2:
        raise PayloadError("only type-2 (EIP-1559) transactions are supported")
    to = fields.get("to") or b""
    to_hex = to if isinstance(to, str) else to.hex()
    data = fields.get("data") or b""
    data_hex = data if isinstance(data, str) else data.hex()
    return ObservedTransaction(
        hash="0x" + keccak(bytes(raw)).hex(),
        sender=to_checksum_address(sender),
        chain_id=int(fields["chainId"]),
        to=to_checksum_address("0x" + to_hex.removeprefix("0x")) if to_hex else "",
        data="0x" + data_hex.removeprefix("0x"),
        value=int(fields["value"]),
        nonce=int(fields["nonce"]),
        gas=int(fields["gas"]),
        max_fee_per_gas=int(fields["maxFeePerGas"]),
        max_priority_fee_per_gas=int(fields["maxPriorityFeePerGas"]),
        type=2,
    )


def observed_from_rpc(tx: dict[str, Any]) -> ObservedTransaction:
    """Normalize an eth_getTransactionByHash result."""

    def q(key: str) -> int | None:
        value = tx.get(key)
        return int(value, 16) if value is not None else None

    return ObservedTransaction(
        hash=tx["hash"],
        sender=to_checksum_address(tx["from"]),
        chain_id=q("chainId") or 0,
        to=to_checksum_address(tx["to"]) if tx.get("to") else "",
        data=tx.get("input") or tx.get("data") or "0x",
        value=q("value") or 0,
        nonce=q("nonce") or 0,
        gas=q("gas") or 0,
        max_fee_per_gas=q("maxFeePerGas"),
        max_priority_fee_per_gas=q("maxPriorityFeePerGas"),
        type=q("type") or 0,
    )


def compare(expected: PinnedTransaction, observed: ObservedTransaction) -> Comparison:
    """Matching rule and field compliance, reported separately (PRD Sections 9.4 and 9.5)."""

    def norm(field: str, value: Any) -> str:
        if value is None:
            return "none"
        if field in ("to", "data"):
            return str(value).lower()
        return str(value)

    def diffs(fields: tuple[str, ...]) -> list[FieldDifference]:
        out = []
        for field in fields:
            e, o = norm(field, getattr(expected, field)), norm(field, getattr(observed, field))
            if e != o:
                out.append(FieldDifference(field, e, o))
        return out

    payload_differences = diffs(PAYLOAD_FIELDS)
    compliance_differences = diffs(COMPLIANCE_FIELDS)
    return Comparison(
        payload_matches=not payload_differences,
        payload_differences=payload_differences,
        sender_matches=expected.sender.lower() == observed.sender.lower(),
        field_compliance="matched" if not compliance_differences else "mismatched",
        compliance_differences=compliance_differences,
    )


def find_transfer_event(
    receipt: dict[str, Any], token: str, sender: str, recipient: str, amount: int
) -> bool:
    """True if the receipt contains the expected ERC-20 Transfer event from the token contract."""
    for log in receipt.get("logs", []):
        topics = log.get("topics", [])
        if (
            log.get("address", "").lower() == token.lower()
            and len(topics) == 3
            and topics[0].lower() == TRANSFER_EVENT_TOPIC
            and "0x" + topics[1][-40:].lower() == sender.lower()
            and "0x" + topics[2][-40:].lower() == recipient.lower()
            and int(log.get("data", "0x0"), 16) == amount
        ):
            return True
    return False
