"""Chain adapter: balances, wallet type, nonce, fee quotes, and transaction verification.

Finality uses the RPC "finalized" tag (PRD Section 10.7); a receipt alone is "included".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from eth_abi import encode as abi_encode
from eth_utils import keccak

from app.chain.payload import (
    Comparison,
    ObservedTransaction,
    PinnedTransaction,
    classify_account_code,
    compare,
    decode_token_transfer,
    encode_token_transfer,
    find_transfer_event,
    observed_from_rpc,
    require_address,
)
from app.chain.rpc import JsonRpcClient
from app.config import Settings

BALANCE_OF_SELECTOR = keccak(text="balanceOf(address)")[:4]


class ChainMismatch(Exception):
    pass


class TokenNotConfigured(Exception):
    pass


@dataclass(frozen=True)
class FeeQuote:
    base_fee_per_gas: int
    max_priority_fee_per_gas: int
    max_fee_per_gas: int


@dataclass(frozen=True)
class Verification:
    status: str  # "not_found" | "pending" | "included" | "finalized"
    observed: ObservedTransaction | None
    comparison: Comparison | None
    receipt_status: str | None  # "success" | "reverted" | None
    block_number: int | None
    finalized_block_number: int
    transfer_event_found: bool | None
    fee_charged: int | None


def _q(value: str | None) -> int | None:
    return int(value, 16) if value is not None else None


class ChainAdapter:
    def __init__(self, rpc: JsonRpcClient, settings: Settings):
        self._rpc = rpc
        self._settings = settings

    async def check_chain(self) -> None:
        chain_id = int(await self._rpc.call("eth_chainId"), 16)
        if chain_id != self._settings.chain_id:
            raise ChainMismatch(f"RPC chain {chain_id} != configured {self._settings.chain_id}")

    async def native_balance(self, address: str) -> int:
        return int(await self._rpc.call("eth_getBalance", address, "latest"), 16)

    async def token_balance(self, token: str, address: str) -> int:
        data = "0x" + (BALANCE_OF_SELECTOR + abi_encode(["address"], [address])).hex()
        return int(await self._rpc.call("eth_call", {"to": token, "data": data}, "latest"), 16)

    async def nonce(self, address: str, block: str = "latest") -> int:
        return int(await self._rpc.call("eth_getTransactionCount", address, block), 16)

    async def wallet_type(self, address: str) -> dict[str, Any]:
        return classify_account_code(await self._rpc.call("eth_getCode", address, "latest"))

    async def finalized_block_number(self) -> int:
        block = await self._rpc.call("eth_getBlockByNumber", "finalized", False)
        return int(block["number"], 16)

    async def fee_quote(self) -> FeeQuote:
        latest = await self._rpc.call("eth_getBlockByNumber", "latest", False)
        base_fee = int(latest["baseFeePerGas"], 16)
        priority = int(await self._rpc.call("eth_maxPriorityFeePerGas"), 16)
        max_fee = base_fee * self._settings.base_fee_multiplier + priority
        return FeeQuote(base_fee, priority, max_fee)

    async def estimate_gas(self, sender: str, to: str, data: str, value: int) -> int:
        estimate = int(
            await self._rpc.call("eth_estimateGas", {"from": sender, "to": to, "data": data, "value": hex(value)}),
            16,
        )
        return estimate + estimate * self._settings.gas_margin_bps // 10_000

    async def pin_token_transfer(
        self,
        sender: str,
        recipient: str,
        amount_base_units: int,
        nonce: int | None = None,
        max_fee_per_gas: int | None = None,
    ) -> PinnedTransaction:
        token = self._require_token()
        sender = require_address(sender, "sender")
        data = encode_token_transfer(recipient, amount_base_units)
        gas = await self.estimate_gas(sender, token, data, 0)
        return await self._pin(sender, token, data, 0, gas, nonce, max_fee_per_gas)

    async def pin_self_transfer(
        self, sender: str, nonce: int | None = None, max_fee_per_gas: int | None = None
    ) -> PinnedTransaction:
        """Zero-value transfer to self: the replacement transaction shape (PRD Section 10.6)."""
        sender = require_address(sender, "sender")
        return await self._pin(sender, sender, "0x", 0, self._settings.native_transfer_gas, nonce, max_fee_per_gas)

    async def _pin(
        self,
        sender: str,
        to: str,
        data: str,
        value: int,
        gas: int,
        nonce: int | None,
        max_fee_per_gas: int | None = None,
    ) -> PinnedTransaction:
        fees = await self.fee_quote()
        if max_fee_per_gas is not None:
            # Signer-gate harness only: deliberately price a transaction (e.g. below the base fee
            # so it stays pending). The priority fee can never exceed the max fee.
            fees = FeeQuote(
                fees.base_fee_per_gas, min(fees.max_priority_fee_per_gas, max_fee_per_gas), max_fee_per_gas
            )
        return PinnedTransaction(
            chain_id=self._settings.chain_id,
            sender=sender,
            to=to,
            data=data,
            value=value,
            nonce=await self.nonce(sender) if nonce is None else nonce,
            gas=gas,
            max_fee_per_gas=fees.max_fee_per_gas,
            max_priority_fee_per_gas=fees.max_priority_fee_per_gas,
        )

    async def broadcast(self, raw_hex: str) -> str:
        return await self._rpc.call("eth_sendRawTransaction", raw_hex)

    async def verify(self, expected: PinnedTransaction, tx_hash: str) -> Verification:
        finalized = await self.finalized_block_number()
        tx = await self._rpc.call("eth_getTransactionByHash", tx_hash)
        if tx is None:
            return Verification("not_found", None, None, None, None, finalized, None, None)
        observed = observed_from_rpc(tx)
        comparison = compare(expected, observed)
        receipt = await self._rpc.call("eth_getTransactionReceipt", tx_hash)
        if receipt is None:
            return Verification("pending", observed, comparison, None, None, finalized, None, None)

        block_number = int(receipt["blockNumber"], 16)
        receipt_status = "success" if _q(receipt.get("status")) == 1 else "reverted"
        # Monad charges the gas limit, not gas used (PRD Section 10.3).
        fee_charged = observed.gas * (_q(receipt.get("effectiveGasPrice")) or 0)

        transfer_event_found = None
        decoded = decode_token_transfer(expected.data)
        if decoded is not None:
            recipient, amount = decoded
            transfer_event_found = find_transfer_event(receipt, expected.to, expected.sender, recipient, amount)

        status = "included"
        if block_number <= finalized:
            # Confirm the canonical block at that height is the one holding the receipt.
            block = await self._rpc.call("eth_getBlockByNumber", hex(block_number), False)
            if block and block["hash"].lower() == receipt["blockHash"].lower():
                status = "finalized"
        return Verification(
            status, observed, comparison, receipt_status, block_number, finalized, transfer_event_found, fee_charged
        )

    def _require_token(self) -> str:
        if not self._settings.demo_token_address:
            raise TokenNotConfigured("DEMO_TOKEN_ADDRESS is not configured")
        return require_address(self._settings.demo_token_address, "DEMO_TOKEN_ADDRESS")
