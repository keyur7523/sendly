import pytest
from eth_account import Account

from app.chain.payload import (
    PayloadError,
    PinnedTransaction,
    classify_account_code,
    compare,
    decode_signed_transaction,
    decode_token_transfer,
    encode_token_transfer,
    find_transfer_event,
    parse_amount,
    TRANSFER_EVENT_TOPIC,
)

TOKEN = "0x1111111111111111111111111111111111111111"
RECIPIENT = "0x2222222222222222222222222222222222222222"


def pinned(sender: str, **overrides) -> PinnedTransaction:
    fields = dict(
        chain_id=10143,
        sender=sender,
        to=TOKEN,
        data=encode_token_transfer(RECIPIENT, 15_000_000),
        value=0,
        nonce=7,
        gas=56_000,
        max_fee_per_gas=202_000_000_000,
        max_priority_fee_per_gas=2_000_000_000,
    )
    fields.update(overrides)
    return PinnedTransaction(**fields)


def sign(account, tx: PinnedTransaction, **overrides) -> str:
    body = {
        "type": 2,
        "chainId": tx.chain_id,
        "nonce": tx.nonce,
        "to": tx.to,
        "value": tx.value,
        "data": tx.data,
        "gas": tx.gas,
        "maxFeePerGas": tx.max_fee_per_gas,
        "maxPriorityFeePerGas": tx.max_priority_fee_per_gas,
    }
    body.update(overrides)
    return "0x" + account.sign_transaction(body).raw_transaction.hex()


@pytest.mark.parametrize(
    "display, expected",
    [("15", 15_000_000), ("15.00", 15_000_000), ("1.5", 1_500_000), ("0.000001", 1)],
)
def test_parse_amount_exact(display, expected):
    assert parse_amount(display, 6) == expected


@pytest.mark.parametrize("display", ["0", "-1", "abc", "1.0000001", "NaN", "Infinity", "1e400000"])
def test_parse_amount_rejects(display):
    with pytest.raises(PayloadError):
        parse_amount(display, 6)


def test_transfer_round_trip():
    data = encode_token_transfer(RECIPIENT, 15_000_000)
    assert data.startswith("0xa9059cbb")
    assert decode_token_transfer(data) == (RECIPIENT, 15_000_000)
    assert decode_token_transfer("0x") is None


def test_encode_rejects_bad_recipient_and_zero_amount():
    with pytest.raises(PayloadError):
        encode_token_transfer("0x123", 1)
    with pytest.raises(PayloadError):
        encode_token_transfer(RECIPIENT, 0)


def test_digest_is_stable_and_field_sensitive():
    a = pinned("0x3333333333333333333333333333333333333333")
    assert a.digest() == pinned("0x3333333333333333333333333333333333333333").digest()
    assert a.digest() != pinned("0x3333333333333333333333333333333333333333", nonce=8).digest()
    assert a.fee_bound == 56_000 * 202_000_000_000


def test_classify_account_code():
    assert classify_account_code("0x") == {"wallet_type": "eoa", "delegated": False}
    delegated = classify_account_code("0xef0100" + "44" * 20)
    assert delegated["wallet_type"] == "eip7702_delegated" and delegated["delegated"]
    assert classify_account_code("0x6080604052")["wallet_type"] == "contract"


def test_signed_transaction_matching_and_compliant():
    acct = Account.create()
    tx = pinned(acct.address)
    observed = decode_signed_transaction(sign(acct, tx))
    result = compare(tx, observed)
    assert observed.sender == acct.address
    assert result.payload_matches and result.sender_matches
    assert result.field_compliance == "matched"


def test_fee_change_is_compliance_only_never_payload():
    """PRD 9.4/9.5: a wallet that changes only fee fields has still made the payment."""
    acct = Account.create()
    tx = pinned(acct.address)
    observed = decode_signed_transaction(sign(acct, tx, maxFeePerGas=300_000_000_000, gas=90_000))
    result = compare(tx, observed)
    assert result.payload_matches
    assert result.field_compliance == "mismatched"
    assert {d.field for d in result.compliance_differences} == {"max_fee_per_gas", "gas"}


def test_nonce_change_is_reported_as_compliance_mismatch():
    acct = Account.create()
    tx = pinned(acct.address)
    result = compare(tx, decode_signed_transaction(sign(acct, tx, nonce=8)))
    assert result.payload_matches
    assert [d.field for d in result.compliance_differences] == ["nonce"]


def test_recipient_change_breaks_payload_match():
    acct = Account.create()
    tx = pinned(acct.address)
    other = encode_token_transfer("0x5555555555555555555555555555555555555555", 15_000_000)
    result = compare(tx, decode_signed_transaction(sign(acct, tx, data=other)))
    assert not result.payload_matches
    assert [d.field for d in result.payload_differences] == ["data"]


def test_wrong_signer_is_detected():
    acct, other = Account.create(), Account.create()
    tx = pinned(acct.address)
    assert not compare(tx, decode_signed_transaction(sign(other, tx))).sender_matches


def test_undecodable_signed_transaction():
    with pytest.raises(PayloadError):
        decode_signed_transaction("0xdeadbeef")


def test_find_transfer_event():
    sender = "0x3333333333333333333333333333333333333333"
    log = {
        "address": TOKEN,
        "topics": [TRANSFER_EVENT_TOPIC, "0x" + "0" * 24 + sender[2:], "0x" + "0" * 24 + RECIPIENT[2:]],
        "data": hex(15_000_000),
    }
    assert find_transfer_event({"logs": [log]}, TOKEN, sender, RECIPIENT, 15_000_000)
    assert not find_transfer_event({"logs": [log]}, TOKEN, sender, RECIPIENT, 14_000_000)
    assert not find_transfer_event({"logs": [{**log, "address": RECIPIENT}]}, TOKEN, sender, RECIPIENT, 15_000_000)
