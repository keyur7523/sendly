# Signer gate (PRD Section 10.4, PAY-09)

Payment execution is enabled only for a **signer qualification**: a wallet provider, SDK version, and wallet type with a recorded passing result on the target network. There is no reduced-capability mode. Rerun the gate after any SDK upgrade.

## Checks

Criteria match PRD v1.5 Section 10.4. Every signer criterion is judged on the **decoded signed transaction**, not on whether a transaction later wins a race on-chain.

| # | Signer criterion | Harness case | Passes when |
|---|---|---|---|
| 1 | Signs exactly the requested transaction (sign-only, the product path) | `pinned_sign_only` | The decoded signed transaction carries the supplied nonce (including 0, sent as hex), gas limit, `maxFeePerGas`, `maxPriorityFeePerGas`, recipient, data, value, and chain ID, or the call errors instead of changing them |
| 1s | Same, in send mode (diagnostic only) | `pinned_send` | As 1, observed on the broadcast transaction; send mode is not used on the product path |
| 2 | Refusal distinguishable from failure | `explicit_rejection` | ✕ and Esc yield an error a stable field distinguishes from a network/provider failure |
| 3 | Replacement signed as requested while another transaction at that nonce is outstanding | `same_nonce_replacement` | A zero-value self-transfer at the specified nonce, with the requested fee fields, decodes exactly while a different transaction at that nonce has been broadcast and not yet included |
| 4 | Wallet type | `wallet_type` | The embedded wallet is an undelegated EOA (no EIP-7702 delegation designator) |

**Network observations (recorded, not signer criteria):** whether a replacement is included; how the RPC treats underpriced and future-nonce transactions.

## How to run

See the root `README.md` (Phase 1). Each case on `/gate` has **Record pass / fail / inconclusive** buttons that append to `docs/signer-gate/results.jsonl` with the SDK version.

## Results

Fill in from `results.jsonl` after a run. Do not mark the signer qualified unless checks 1–4 all pass.

| Date | Provider / SDK | Wallet type | 1 | 1s | 2 | 3 | 4 | Qualified? | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-07 (v1.5 criteria) | `@privy-io/react-auth` 3.47.0 (user-controlled server wallets) | Undelegated EOA | **Pass** (hex nonce; `0x0`→0, `0x3`→3, 3→3) | **Pass** (diagnostic; hex `0x0`→0) | **Pass** (4001 vs -32000) | **Pass** (replacement `0xbc58…6649` signed at nonce 10, 300 gwei, decoded exactly while payment `0x7504…3a20` was outstanding) | Pass | **Yes** | Network observation: the queued original was included, the replacement was not; underpriced transactions rejected at submission. Numeric nonce `0` is dropped by Privy, so the integration must send hex. |

## Findings that affect the PRD

Record anything the gate reveals that changes a PRD assumption (for example, the rejection error shape, or whether sign-only mode is usable).

- **SUPERSEDED, see the next finding.** ~~Nonce is not controllable (gate item 1 fails).~~ Requested nonce 0 was broadcast at 7 in send mode (`0xdf92…60cd`) and signed at 8 in sign-only mode (`0xa088…8a43`, not broadcast). PRD §10.4–10.6 assume the app pins the nonce; with this signer it cannot.
- **Nonce IS controllable when sent as a hex string (corrected 2026-10-07).** Privy 3.47.0 handles the nonce with `nonce ? BigInt(nonce) : undefined`, so numeric `0` is dropped and replaced by the account nonce; any other value is kept. Sign-only: number 3 → 3, `"0x0"` → 0, `"0x3"` → 3; send mode with `"0x0"` signed nonce 0. Sendly always sends the nonce as hex (`apps/web/lib/gate.ts` `toWalletRequest`).
- **Privy's send-mode error screen offers "Retry transaction"**, and its code can reset the nonce on retry, turning a failed payment into a fresh duplicate. Another reason to keep send mode out of the product.
- **Product path verified end to end:** sign-only with hex nonce → backend decode/validate → backend broadcast → finalized with Transfer event; the on-chain hash equals the hash computed before broadcast (`0xa088ee2f…8a43`).
- **Same-nonce replacement did not work on Monad testnet.** A payment queued behind a nonce gap (RPC "accepted", but invisible to `eth_getTransactionByHash`) was followed by a higher-fee replacement at the same nonce (also "accepted"). When the gap was filled, the original payment was included and the replacement never was. RPC acceptance is not evidence of inclusion.
- **Monad rejects underpriced transactions at submission** ("Transaction fee too low"), so a "stuck because the fee is too low" state does not arise.
- **Network failures are distinguishable from refusals:** `InvalidInputRpcError`, `code: -32000` ("Transaction nonce too low") vs `code: 4001` for ✕/Esc.
- **Gas limit and fee caps are preserved exactly** in every run, so `gasLimit × maxFeePerGas` is a real fee bound with this signer.
- **Sign-only mode works:** `signTransaction` returns the complete signed type-2 transaction. The backend can decode it, check every field, and know the hash and the nonce the signer chose *before* broadcasting.
- **Rejection is distinguishable:** the prompt has Approve and ✕ only (no Reject button). ✕ and Esc both reject with `code: 4001` (EIP-1193 User Rejected Request), `type: "provider_error"`; nothing is broadcast. Privy's `PrivyErrorCode` enum is not used for this (`privyErrorCode` is undefined).
- **`sendTransaction` resolves only after the user dismisses Privy's "Transaction complete" screen.** Until then the app has no hash; if the tab closes on that screen the outcome is unknown to the app. Sign-only mode avoids this.
- **An unsupported `chainId` makes Privy throw an uncaught error and never settle the promise.** Every wallet call needs a timeout (the harness now uses 120 s).
- **Privy's approval screen shows the wallet's token balance (e.g. "10 DemoUSD"), not the amount being sent.** Sendly's own review card must carry the amount; the wallet screen cannot be relied on for it.
- **Monad receipts report `gasUsed` equal to the gas limit**, consistent with charging the full limit.
- Development-only React warning about an `isActive` prop comes from Privy's own transaction screen (styled-components), not Sendly.
