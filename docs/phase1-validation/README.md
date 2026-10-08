# Phase 1 validation — October 7, 2026

Audited application commit: `9d8b3a8`. The working tree was clean before this audit.
Scope: README's Phase 1 claim (PRD build stages B0–B2), the existing signer harness,
and the corrected gate evidence. No application fixes, wallet signatures, or new
transactions were performed. This directory contains validation artifacts only.

**Overall: not a complete pass against PRD B0–B2.** Existing suites and the build
pass, but additional validation checks fail and some B0/B1 requirements remain
unimplemented. The signer qualification is not independently fully established
by this audit.

## Executed checks

| Check | Result | Evidence / limit |
|---|---|---|
| Backend suite | PASS: 46 tests | `.venv/bin/pytest -q`; two dependency/test warnings |
| Contract suite | PASS: 8 tests | `forge test --offline`; supply fuzz test ran 256 cases |
| Frontend lint | PASS | `npm run lint` |
| Frontend TypeScript | PASS | `npx tsc --noEmit` |
| Frontend production build | PASS | `npm run build`; `/` and `/gate` prerendered |
| Production startup / HTTP | PASS: 4 checks | API health 200, unauthenticated `/v1/me` 401, built web `/` and `/gate` 200; temporary loopback servers were stopped |
| Hex nonce regression | PASS: 4 inputs | Actual `toWalletRequest` plus installed Privy converter preserve 0, 1, 3, 8; no live signing |
| Additional acceptance checks | FAIL: 4 failed, 10 passed | `acceptance_checks.py`; details below |
| Deployed DemoUSD | PASS on fresh RPC read | Symbol DemoUSD, decimals 6, owner matches documented deployer |
| Wallet type | PASS on fresh RPC read | Documented embedded wallet currently has no code/delegation |
| Recorded successful transfer | PASS on fresh RPC read | Adapter independently verifies nonce 8, payload, sender, fee fields, Transfer event, successful receipt and canonical finalized block |
| New browser login / wallet prompt tests | NOT RUN | Browser automation timed out twice; no fresh signing or refusal test was possible |

The production transfer was already on-chain before this audit. The expected
transaction for the read-only adapter check was reconstructed from documented
gate settings and the .01 DemoUSD self-transfer, not copied from the fetched
transaction. This confirms those fields; it does not replace an archived original
prepared-payload record or a new signing run. See `chain-evidence.json`.

## Reproduced validation failures

1. **Exact amount conversion:** `12345678901234567890123.123456` at six decimals
   should become `12345678901234567890123123456`, but becomes
   `12345678901234567890123123460`. `Decimal.scaleb()` rounds at the default
   context precision. PRD 9.6 requires exact integer conversion.
2. **Oversized input handling:** `1e1000000` raises uncaught `decimal.Overflow`
   instead of `PayloadError`. The HTTP handler does not catch that exception.
3. **Address checksum:** invalid mixed-case address
   `0x52908400098527886e0F7030069857D2E4169EE7` is accepted and normalized.
   PRD 5.7 requires rejecting invalid mixed-case checksums. Contacts are not yet
   implemented; this test identifies a gap in the shared validator before reuse.
4. **Wrong-chain preparation:** with a fake node reporting chain ID 1, the
   self-transfer prepare endpoint returns 200 for configured chain 10143.
   `/wallet` checks the network, but preparation does not enforce that check.

The 10 passing additional checks cover authentication on all five gate POST
endpoints, owner isolation on inspect/broadcast/verify, preservation of the known
hash with an unknown broadcast outcome on transport failure, and refusal to mark
a noncanonical receipt finalized.

## PRD stage assessment

| Stage | Assessment |
|---|---|
| B0 foundations | PARTIAL: token verification and owner scoping for prepared records exist. PostgreSQL, migrations, and provider-verified wallet binding do not. README defers binding to B3, while PRD 26 requires it in B0. |
| B1 chain and token | PARTIAL: deployment, metadata, fees, payload/receipt checks and finality have evidence. Reserve-window evaluation/configuration and above/below-reserve tests are absent. Validation failures above remain. |
| B2 signer gate | Hex-nonce correction is supported by existing signed-result records and fresh offline checks; chain evidence supports the prior transfer and wallet type. Fresh wallet interaction was unavailable, and replacement qualification needs consistent criteria/evidence. |

## Replacement evidence and qualification

Fresh chain reads confirm:

- The historical zero-value self-transfer at nonce 2 finalized successfully.
  That experiment held the original unbroadcast.
- In the later queued experiment, the original payment at nonce 10 finalized.
  The reported competing replacement hash has no transaction or receipt from the
  queried RPC. The nonce-9 gap filler finalized immediately before the original.

**An original-wins race alone is not proof that the signer cannot replace.**
PRD 10.4 requires signing at the specified competing nonce, and PRD 10.6 explicitly
allows either transaction to win. The gate document's stronger inclusion criterion
and its simultaneous “Fail on Monad” / “Yes, with conditions” labels are inconsistent.
The queued replacement's raw signed fields were not available in the persisted
result, and its missing RPC transaction cannot independently verify those fields.
Resolve the criteria and retain decoded signed evidence before claiming every gate
item passed. One experiment also cannot establish universal first-seen behavior.

Likewise, rejection of one underpriced submission does not prove that every
accepted transaction can never become stuck after fees or network conditions change.

Additional scope distinction: `/v1/gate/broadcast` computes comparison results but
does not reject mismatches or durably persist signed bytes before broadcasting.
It is a measurement harness, not the validated/durable B3 payment executor.
Four wallet calls also remain unwrapped by the timeout used in the rejection case.

## Reproduce

From `services/api`:

```sh
.venv/bin/pytest -q
PYTHONPATH="$PWD" .venv/bin/pytest ../../docs/phase1-validation/acceptance_checks.py -q --tb=short
# Network read only; refreshes chain-evidence.json. Never signs or broadcasts.
PYTHONPATH="$PWD" .venv/bin/python ../../docs/phase1-validation/chain_audit.py
```

From the repository root:

```sh
node docs/phase1-validation/nonce_checks.cjs
```

From `apps/web`: `npm run lint`, `npx tsc --noEmit`, `npm run build`.
From `contracts/demo-token`: `forge test --offline`.

The additional acceptance suite is intentionally separate from the existing suite
and currently exits nonzero for the four reproduced failures. Application code and
the historical signer results have not been changed by this audit.
