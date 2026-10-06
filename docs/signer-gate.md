# Signer gate (PRD Section 10.4, PAY-09)

Payment execution is enabled only for a **signer qualification**: a wallet provider, SDK version, and wallet type with a recorded passing result on the target network. There is no reduced-capability mode. Rerun the gate after any SDK upgrade.

## Checks

| # | Check | Harness case | Passes when |
|---|---|---|---|
| 1 | Pinned fields preserved | `pinned_send` | The broadcast transaction's nonce, gas limit, `maxFeePerGas`, and `maxPriorityFeePerGas` equal the pinned values (or the SDK errors instead of changing them); the transfer finalizes with the expected Transfer event |
| 1b | Sign-only mode (informational) | `pinned_sign_only` | `signTransaction` returns a full signed transaction that decodes to the pinned fields before broadcast. Not required by the PRD; if it passes, it can narrow the crash window in Section 10.5 |
| 2 | Explicit rejection is distinguishable | `explicit_rejection` | Pressing reject and closing the modal both yield an error that a stable field (not message text) distinguishes from a non-rejection failure |
| 3 | Same-nonce replacement | `same_nonce_replacement` | The SDK signs a zero-value self-transfer at the specified nonce N; it finalizes at N; a payment signed earlier at N is then rejected by the network |
| 4 | Wallet type | `wallet_type` | The embedded wallet is an undelegated EOA (no EIP-7702 delegation designator) |

Known limitation of check 3: it holds the original payment unbroadcast (sign-only), so it shows that the SDK honours a specified nonce and that one transaction per nonce is included. It does not test a payment that is genuinely pending in a node's mempool.

## How to run

See the root `README.md` (Phase 1). Each case on `/gate` has **Record pass / fail / inconclusive** buttons that append to `docs/signer-gate/results.jsonl` with the SDK version.

## Results

Fill in from `results.jsonl` after a run. Do not mark the signer qualified unless checks 1–4 all pass.

| Date | Provider / SDK | Wallet type | 1 | 1b | 2 | 3 | 4 | Qualified? | Notes |
|---|---|---|---|---|---|---|---|---|---|
| | `@privy-io/react-auth` 3.47.0 | | | | | | | | |

## Findings that affect the PRD

Record anything the gate reveals that changes a PRD assumption (for example, the rejection error shape, or whether sign-only mode is usable).

- Privy 3.47.0's public `PrivyErrorCode` enum has no dedicated "user rejected transaction" code; it has `transaction_failure` and several `exited_*_flow` codes. Check 2 determines whether rejection can be distinguished in practice.
