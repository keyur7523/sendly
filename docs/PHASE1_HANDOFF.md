# Sendly Phase 1 — Status, Problems, and Open Decision

**Purpose of this document:** give a second reviewer (human or AI agent) everything needed to understand where Sendly's Phase 1 stands, how to run it locally, every problem hit so far and how it was resolved, and the one open blocker that needs a decision. It is written to be read without access to the original conversation.

**Last updated:** 2026-10-07
**Repository:** https://github.com/keyur7523/sendly (local checkout: `~/projects/sendly`)
**Specs:** [`VOICE_PAYMENTS_PRD.md`](../VOICE_PAYMENTS_PRD.md) (v1.4, behavior and authorization) and [`SENDLY_DESIGN_GUIDE.md`](../SENDLY_DESIGN_GUIDE.md) (v1.1, visual layout). Both live only in this repository; ignore any copies elsewhere.

---

## 1. TL;DR

- **Goal of Phase 1:** before building any payment code, prove that the embedded wallet (Privy) signs *exactly* the transaction Sendly's backend prepares. This is the "signer gate" in PRD §10.4 and is a release blocker for payment execution.
- **Result (corrected 2026-10-07):** Privy `@privy-io/react-auth` **3.47.0 qualifies, with conditions.**
  - ✅ Gas limit, `maxFeePerGas`, `maxPriorityFeePerGas`, recipient/data/value/chain are preserved **exactly**.
  - ✅ **Nonce is preserved when sent as a hex string.** An earlier "nonce ignored" result was a false failure: Privy drops a *numeric* `0` (truthiness check) and every override test had used `0`.
  - ✅ User refusal (`code: 4001`) is distinguishable from network failure (`code: -32000`).
  - ✅ Sign-only mode returns a full signed transaction, so the hash is known **before** broadcast.
  - ✅ The embedded wallet is a plain EOA (no EIP-7702 delegation).
  - ✅ **Product path verified end to end** (sign-only + hex nonce + backend broadcast → finalized).
  - ❌ **Same-nonce replacement did not displace a queued transaction on Monad testnet** (the original payment landed; see §7.3).
- **Agreed direction (from second-opinion review):** product path = **sign-only with an explicitly pinned (hex) nonce + durable backend broadcast**; send mode stays only in the diagnostic harness. Details and remaining work in §7.

---

## 2. What Sendly is (one paragraph)

Sendly is a voice-first payments assistant on Monad: the user speaks ("send Mom fifteen"), the assistant resolves the recipient and amount, reads the exact payment back, takes an explicit confirmation, and the user's embedded wallet signs a token transfer. The PRD is strict about money safety: the model proposes and deterministic code validates; approvals are bound to an immutable review revision; "unknown" outcomes are never treated as failures; and the backend must be able to reconcile any transaction it prepared. Many of those guarantees (PRD §9.3 nonce reservations, §10.5 reconciliation, §10.6 same-nonce replacement) assume **the app chooses the nonce**, which is why the nonce result in §6 matters.

---

## 3. Repository layout (what exists now)

```text
sendly/
  VOICE_PAYMENTS_PRD.md        PRD v1.4
  SENDLY_DESIGN_GUIDE.md       Design guide v1.1
  README.md                    Run instructions (Phase 1)
  apps/web/                    Next.js 16 + React 19 + Privy 3.47.0; only page so far: /gate (signer gate harness)
    app/gate/GateHarness.tsx   All gate checks (1, 1b, 2, 3, 4) and result recording
    app/providers.tsx          PrivyProvider (email login, Monad testnet only, create embedded wallet on login)
    lib/api.ts, lib/gate.ts    API client, shared types, error capture
  services/api/                FastAPI backend (Python 3.11)
    app/auth/privy.py          ES256 Privy access-token verification
    app/chain/payload.py       Pure logic: pin/encode/decode/compare transactions (matching rule vs field compliance)
    app/chain/adapter.py       JSON-RPC chain adapter: balances, nonce, wallet type, fee quote, verify (included vs finalized)
    app/chain/rpc.py           Minimal async JSON-RPC client over httpx
    app/gate/routes.py         /v1/gate/* harness endpoints
    app/config.py              Settings (env), verification-key normalization
    tests/                     44 tests (no network)
  contracts/demo-token/        Foundry project: DemoUSD ERC-20 (6 decimals, owner-only mint), tests, deploy script
  docs/
    signer-gate.md             Gate definition, results table, findings
    signer-gate/results.jsonl  Recorded gate results with transaction-hash evidence
    demo-guide.md              Manual funding guide and deployed addresses
    PHASE1_HANDOFF.md          This file
```

Not built yet (by design): drafts/revisions/approvals, database, voice, LLM, the real payment UI. See PRD §26 build order (B0–B7). Phase 1 = B0–B2.

---

## 4. Environment and versions

| Component | Version |
|---|---|
| macOS, zsh | — |
| Node | 22.22.0 |
| Python | 3.11.5 (python.org build — see problem P3) |
| Foundry (forge/cast/anvil) | 1.5.1-stable |
| Next.js | 16.3.8 (Turbopack). **Breaking changes vs older Next.js**; agents must read `apps/web/node_modules/next/dist/docs/` before framework-level changes (see `apps/web/AGENTS.md`) |
| React | 19.2.8 |
| `@privy-io/react-auth` | 3.47.0 (pinned exactly) |
| viem | 2.57.3 (uses its built-in `monadTestnet` chain) |
| FastAPI / pydantic / httpx / PyJWT | 0.142.2 / 2.13.5 / 0.28.1 / 2.15.1 |
| eth-account / eth-abi / eth-utils / hexbytes | 0.14.0 / 6.0.0 / 6.0.0 / 2.0.0 |

**Network:** Monad testnet, chain ID **10143**, RPC `https://testnet-rpc.monad.xyz`. Observed base fee 100 gwei, priority fee 2 gwei. The RPC supports the `finalized` block tag.

### Live testnet artifacts (all public, safe to share)

| What | Address / value |
|---|---|
| DemoUSD (in use) | `0x701C0eAB78ba95d7604Ee316C52e8FF88f63a9F5` (owner = deployer below) |
| DemoUSD (abandoned, do not use) | `0x7E7DfFC7D515Eb6F7E5BB0919B95597f33F9F1f4` — owner is Foundry's placeholder sender, nobody can mint (problem P17) |
| Deployer wallet (Foundry keystore `sendly-deployer`) | `0x4205E140DcF661BDe478236CD760386B12F3c197` |
| Privy embedded wallet (test user) | `0xfA339b0Fc9D01073AF67B668ba5813d677B85956` — ~4.97 MON, 10 DemoUSD, nonce 8 at time of writing |
| Explorer | https://testnet.monadexplorer.com |

---

## 5. Running everything locally

### 5.1 Prerequisites
- Node 22, Python 3.11+, Foundry, git.
- A Privy app (dashboard: https://dashboard.privy.io) with **email login** enabled. Needed values:
  - **App ID** — public.
  - **Verification key** — public key used to verify access tokens. Found under **Configuration → App settings → Basics → "Verify with key instead"**. The dashboard shows only the base64 body (no `-----BEGIN PUBLIC KEY-----` lines); the backend accepts that form.
  - **App secret** — *not used and must not be added* to Sendly in Phase 1.
- Testnet MON from https://faucet.monad.xyz (only a public address is ever needed).

### 5.2 Secrets and env files (never commit; both are git-ignored)

`services/api/.env` (template: `services/api/.env.example`):

| Key | Notes |
|---|---|
| `PRIVY_APP_ID` | required, non-empty |
| `PRIVY_VERIFICATION_KEY` | required; full PEM, `\n`-escaped PEM, or bare base64 body all work |
| `CHAIN_ID` | `10143` |
| `RPC_URL` | `https://testnet-rpc.monad.xyz` |
| `DEMO_TOKEN_ADDRESS` | `0x701C0eAB78ba95d7604Ee316C52e8FF88f63a9F5` |
| `DEMO_TOKEN_DECIMALS` / `DEMO_TOKEN_SYMBOL` | `6` / `DemoUSD` |
| `GAS_MARGIN_BPS` / `BASE_FEE_MULTIPLIER` | `1000` (+10%) / `2` |
| `CORS_ORIGINS` | `["http://localhost:3000"]` |

`apps/web/.env.local` (template: `apps/web/.env.example`): `NEXT_PUBLIC_PRIVY_APP_ID` (same App ID), `NEXT_PUBLIC_API_URL=http://localhost:8000`.

### 5.3 Contracts (DemoUSD)

```bash
cd ~/projects/sendly/contracts/demo-token
git submodule update --init          # forge-std is a submodule
forge test                           # 8 tests
```

Deploy (only needed for a fresh environment; one is already deployed):

```bash
cast wallet new ~/.foundry/keystores sendly-deployer   # run ONCE; running again overwrites the keystore (problem P16)
# fund the printed address at https://faucet.monad.xyz
MONAD_TESTNET_RPC_URL=https://testnet-rpc.monad.xyz forge script script/Deploy.s.sol --rpc-url monad_testnet --account sendly-deployer --broadcast
```

Mint test tokens to a wallet (`10000000` = 10.000000 DemoUSD):

```bash
cast send 0x701C0eAB78ba95d7604Ee316C52e8FF88f63a9F5 "mint(address,uint256)" <WALLET> 10000000 --rpc-url https://testnet-rpc.monad.xyz --account sendly-deployer
```

### 5.4 Backend

```bash
cd ~/projects/sendly/services/api
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest                     # 44 tests, no network
.venv/bin/uvicorn app.main:app --reload --port 8000
curl localhost:8000/healthz          # {"status":"ok"}
```

Note: `--reload` watches `.py` files only. After editing `.env`, restart uvicorn (or touch a `.py` file).

### 5.5 Frontend

```bash
cd ~/projects/sendly/apps/web
npm install
npm run dev                          # http://localhost:3000/gate
npx tsc --noEmit && npm run lint     # typecheck + lint
```

If port 3000 is busy, Next.js picks 3001 and warns that another dev server is running; check `ps`/the warning and stop the duplicate.

### 5.6 Running the signer gate
1. Open `http://localhost:3000/gate`, sign in with email (Privy creates the embedded wallet).
2. Fund the wallet shown in **Gate check 4** with MON (faucet) and DemoUSD (mint command above).
3. Run checks on the page. Each card has **Record pass / fail / inconclusive**, which appends to `docs/signer-gate/results.jsonl`.
4. Verify anything important on-chain with `cast` (e.g. `cast tx <hash> --rpc-url https://testnet-rpc.monad.xyz`, `cast nonce <addr> …`).

Tip: run the gate in one browser only. If an assistant needs to read results, use the browser it can inspect; results in a different browser are invisible to it (problem P20).

---

## 6. Signer gate results (Privy 3.47.0, 2026-10-07)

Full evidence: [`docs/signer-gate/results.jsonl`](signer-gate/results.jsonl) and [`docs/signer-gate.md`](signer-gate.md).

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Pinned fields preserved (send mode) | **Pass (hex nonce)** | Fields kept: `0x4986b175…d4e3`, `0xab614ddd…3f89`. Numeric nonce `0` was dropped (→ 7, `0xdf928333…60cd`); hex `"0x0"` signed at nonce 0 and was then rejected by the network ("nonce too low"), nothing moved |
| 1b | Sign-only mode | **Pass (hex nonce)** | Full signed tx returned and decoded before broadcast. Numeric `0` → 8 (`0xa088ee2f…8a43`); numeric `3` → 3; `"0x0"` → 0 (hash equals `0x4986b175…`); `"0x3"` → 3 (hash equals `0x32fd63d8…aa0d`). None broadcast |
| 2 | Refusal distinguishable | **Pass** | ✕ and Esc → `code: 4001`, `type: "provider_error"`. Network failure → `InvalidInputRpcError`, `code: -32000`, "Transaction nonce too low" |
| 3 | Same-nonce replacement | **Fail on Monad** | Held (never broadcast) payment: replacement at nonce 2 won (`0x52c65134…1053`). **Genuinely queued payment:** payment at nonce 10 behind a gap (`0x7504b67e…3a20`) and a 300 gwei replacement (`0xbc582e0b…6649`) both "accepted"; after filling nonce 9 (`0x387f5848…35f2`) the **original payment** was included and finalized, the replacement never was |
| — | Product path (sign-only + backend broadcast) | **Pass** | `0xa088ee2f…8a43`: decoded before broadcast, backend broadcast, finalized with Transfer event, on-chain hash = precomputed hash |
| 4 | Wallet type | **Pass** | Undelegated EOA after 8 transactions |

Monad behaviour confirmed along the way: receipts report `gasUsed == gas limit` and the fee charged equals `gasLimit × effectiveGasPrice` (Monad charges the full limit).

---

## 7. Decision and remaining design work

### 7.1 What changed
The apparent blocker ("Privy ignores the nonce") was an encoding bug. Privy 3.47.0 contains `nonce: e.nonce ? BigInt(e.nonce) : void 0`, so a numeric `0` becomes `undefined` and Privy fills the account nonce. Sending the nonce as a hex string (`"0x0"`) preserves it. The wallet boundary now always sends hex (`apps/web/lib/gate.ts`, `toWalletRequest`).

### 7.2 Agreed product path (second-opinion review)
**Sign-only with an explicitly pinned nonce + durable backend broadcast.** Send mode is kept only in the diagnostic harness. Reasons: validation and durable recording happen before anything reaches the network; no dependence on the user dismissing Privy's success screen (P24); Privy's send-mode "Retry transaction" can resend at a fresh nonce (P29).

Requirements for the real payment flow (build stage B3), beyond "record the nonce":
1. Acquire the durable per-wallet execution lock / nonce reservation **before** requesting a signature.
2. On receiving the signed transaction: decode it and validate sender, chain, payload, nonce, gas limit, and fee fields against the approved revision. **Reject** mismatched, stale, or conflicting submissions; do not broadcast them. (The current harness `/v1/gate/broadcast` deliberately broadcasts even on mismatch for testing; that is not the product boundary — P30.)
3. **Atomically persist** the signed transaction bytes, hash, nonce, and a broadcast job before sending anything. Storing only the hash is insufficient: after a crash the backend must be able to rebroadcast the identical signed bytes.
4. Broadcast from the backend; on timeout, reconcile the known hash and rebroadcast the same bytes. Never request a new signature at a new nonce for the same payment.
5. Sendly's review card is the substantive payment review surface (Privy's prompt shows the wallet balance, not the amount — P26). Do not describe the wallet prompt as an independent confirmation of recipient and amount.

### 7.3 Still open
- **Replacement for stuck transactions — tested, did not work on Monad testnet.**
  - A `maxFeePerGas` below the base fee is **rejected at submission** ("Transaction fee too low"), so underpriced transactions cannot get stuck.
  - A transaction behind a **nonce gap** is "accepted" by the RPC but invisible (`eth_getTransactionByHash` returns null; pending nonce unchanged). A higher-fee same-nonce replacement was also "accepted", but once the gap was filled the **original** was included and the replacement was not. RPC acceptance is not evidence of inclusion, and replace-by-fee should not be assumed.
  - Implications to resolve: (a) PRD §10.6 (PAY-07) cannot rely on same-nonce replacement as the escape hatch on Monad; (b) Sendly must never create nonce gaps (allocate from the chain's current nonce, one unresolved attempt per wallet), which also removes the main way a transaction becomes "accepted but invisible"; (c) reconciliation by nonce works — after the nonce advanced, matching sender + nonce + payload identified exactly which transaction consumed it; (d) confirm Monad's replacement semantics with docs/support before deciding the PRD change. Single testnet observation.
  - Knowing the hash still improves recovery (rebroadcast identical bytes), but without working replacement an unconfirmed transaction could block the wallet; type-2 transactions have no built-in expiry ([EIP-1559](https://eips.ethereum.org/EIPS/eip-1559)).
- **PRD updates** to reflect §7.2 (product path = sign-only + backend broadcast; hex nonce encoding at the wallet boundary; gate item 1 wording).
- Privy's REST `eth_signTransaction` API documents a `nonce` field ([reference](https://docs.privy.io/api-reference/wallets/ethereum/eth-sign-transaction)), but server-side signing is not needed now and would be a security-design change (PRD §22.1).

## 8. Problems encountered (chronological) and resolutions

Status legend: ✅ resolved · ⚠️ worked around · ❌ open

| # | Area | Problem | Root cause | Resolution / status |
|---|---|---|---|---|
| P1 | Specs | PRD v1.0 had contradictions (naming, approval consumption, missing states, nonce assumptions) | Early draft | ✅ Revised to v1.4 over several review rounds |
| P2 | Docs | Two copies of the PRD (Desktop v1.0 vs project v1.4) confused a reviewer | Files copied between folders | ✅ Only `~/projects/sendly` is authoritative |
| P3 | Python | HTTPS calls failed with `CERTIFICATE_VERIFY_FAILED` | python.org Python on macOS ships without root CAs; web3.py's aiohttp used system certs | ⚠️ Chain client uses `httpx` (bundles certifi). Optional system fix: run `/Applications/Python 3.11/Install Certificates.command` |
| P4 | Python | `web3` installed as 8.0.0 (unfamiliar major) | Latest release | ⚠️ Not used; only `eth-account`, `eth-abi`, `eth-utils`, `hexbytes` |
| P5 | Backend | Decoding signed txs failed: `expected Hexbytes, got bytes` | `TypedTransaction.from_bytes` requires `HexBytes` in eth-account 0.14 | ✅ Fixed in `payload.py` |
| P6 | Backend | Amount `1e400000` accepted | No upper bound | ✅ Capped at uint256 |
| P7 | Frontend | `react-hooks/set-state-in-effect` lint error | setState reachable synchronously from an effect | ✅ Inline fetch with `.then` + ignore flag; effect depends on wallet address string |
| P8 | Frontend | Production build failed prerendering `/` | Privy validates App ID format even at build time | ✅ Use a real (or correctly shaped) App ID when building |
| P9 | Repo | forge-std vendored as ~100 files | `forge init --no-git` | ✅ Converted to a git submodule |
| P10 | Process | Claude co-author trailer in first commit | Default attribution | ✅ Removed from history; user-level `attribution` disabled; hard rule recorded |
| P11 | Backend | Server crashed: `privy_app_id Field required` | `services/api/.env` did not exist (tests use their own env) | ✅ Create `.env`; empty values now also rejected at startup |
| P12 | Backend | Verification key "not a valid PEM public key" | Dashboard shows bare base64 without PEM header/footer | ✅ Settings normalizes bare/escaped/full PEM; 3 tests added |
| P13 | Frontend | First click on "Sign in" did nothing | Clicked before Privy finished initializing on a cold dev compile | ✅ Not a bug; wait for ready |
| P14 | Tooling | In-app browser network log showed no `auth.privy.io` requests | The tool does not list cross-origin requests | ⚠️ Diagnose with in-page `fetch` instead |
| P15 | Funding | Confusion about "tokens and secrets" on Monad's site | Wrong page | ✅ Faucet needs only a public address: https://faucet.monad.xyz |
| P16 | Foundry | `cast wallet new … sendly-deployer` run twice | Second run overwrote the keystore | ✅ Use the second address; never rerun |
| P17 | Contracts | Deployed DemoUSD owner was `0x1804c8AB…1f38` (nobody can mint) | `msg.sender` inside a Foundry script `run()` is the placeholder `DEFAULT_SENDER`, not `--account` | ✅ Script uses `vm.readCallers()`, refuses `DEFAULT_SENDER`, asserts owner; redeployed. Old contract abandoned |
| P18 | Backend | New `DEMO_TOKEN_ADDRESS` not picked up | uvicorn `--reload` ignores `.env`; settings are cached | ✅ Restart or touch a `.py` file |
| P19 | Frontend | Second `npm run dev` started on 3001 | A dev server was already running on 3000 | ✅ Use the existing one |
| P20 | Process | Gate checks run in a different browser were invisible to the assistant | Separate browser sessions | ⚠️ Run everything in one inspectable browser; verify on-chain |
| P21 | Privy | Console error: React does not recognize `isActive` prop | Privy's transaction screen (styled-components) | ⚠️ Harmless dev-only upstream warning |
| P22 | Privy/test | "Reject" attempts sent transactions (4 unintended self-transfers) | Privy's prompt has **no Reject button** (Approve + ✕ only); Approve pressed by habit | ✅ Harness relabelled: ✕ and Esc. Confirmed both → `4001`. Cost ~0.016 test MON |
| P23 | Harness | Page froze "busy"; buttons disabled | Unsupported `chainId` makes Privy throw an *uncaught* error and never settle the promise | ✅ 120 s timeout on wallet calls → "unknown outcome"; variant replaced |
| P24 | Privy | `sendTransaction` did not resolve within 120 s after approval | It resolves only after the user dismisses Privy's "Transaction complete" screen | ❌ Product risk in send mode; avoided by sign-only (Option A) |
| P25 | Privy | Supplied nonce appeared to be ignored (send: 0→7, sign-only: 0→8) | Privy's truthiness check drops a **numeric 0**; every override test had used 0 | ✅ Send the nonce as a hex string; verified `0x0`→0, `0x3`→3, numeric 3→3 (found via second-opinion review) |
| P26 | Privy UX | Approval screen shows wallet token balance ("10 DemoUSD"), not the amount sent | Privy UI | ⚠️ Sendly's own review card must carry amount/recipient/fee (already required by PRD) |
| P27 | Monad | `gasUsed` equals the gas limit | Monad charges the full gas limit | ✅ Expected (PRD §10.3); keep gas margin tight |
| P29 | Privy | Send-mode error screen offers "Retry transaction" | Privy's retry path can reset the nonce | ⚠️ Would send a fresh duplicate; never use send mode in the product |
| P30 | Harness | `/v1/gate/broadcast` broadcasts even when the signed transaction mismatches | Deliberate, to observe network behaviour in check 3 | ⚠️ Product broadcast must reject mismatches (§7.2) |
| P31 | Monad | Same-nonce, higher-fee replacement of a queued transaction was accepted by the RPC but never included; the original won | First-seen semantics / no replace-by-fee observed on testnet | ❌ PRD §10.6 needs revisiting (§7.3) |
| P32 | Monad | Transactions with `maxFeePerGas` below base fee rejected at submission | RPC validation | ✅ Good: no stuck-underpriced state |
| P28 | Privy config | Dashboard config shows `create_on_login: "off"` while the client sets `createOnLogin: "users-without-wallets"`; wallets are still created | Client config applies | ⚠️ Note only; verify if wallet creation ever fails |

---

## 9. Uncommitted work (as of writing)

On top of commit `a37760c` (pushed):
- `contracts/demo-token/script/Deploy.s.sol` — owner fix (P17)
- `services/api/app/config.py`, `services/api/tests/test_auth.py` — non-empty settings, key normalization (P11, P12)
- `apps/web/app/gate/GateHarness.tsx`, `apps/web/lib/gate.ts` — wallet timeout, rejection variants, nonce override and hex/number encoding selector on 1b, hex nonce by default (P22, P23, P25)
- `docs/demo-guide.md`, `docs/signer-gate.md`, `docs/signer-gate/results.jsonl`, this file
- `contracts/demo-token/broadcast/` — Foundry's public deployment records (no secrets)
- `.gitignore` — `*.egg-info/`

All suites pass: 44 backend, 8 contract, web typecheck + lint.

---

## 10. Security notes for whoever continues

- Never paste or commit: Privy **app secret**, keystore passwords, private keys, seed phrases, email login codes. The verification key, App ID, wallet addresses, contract addresses, and transaction hashes are public.
- The deployer key is an encrypted Foundry keystore at `~/.foundry/keystores/sendly-deployer`; always use `--account sendly-deployer`, never `--private-key`.
- The gate endpoints are a harness: wallet ownership is not bound to the user yet (arrives in build stage B3), prepared transactions live in memory, results are written to a local file.
- A signed-but-unbroadcast self-transfer at nonce 8 exists in the browser page state from the last test; it is harmless (0.01 DemoUSD to self) and is invalidated by the wallet's next transaction.

---

## 11. Reference links

**Privy**
- Dashboard: https://dashboard.privy.io
- Send a transaction (React `useSendTransaction`): https://docs.privy.io/wallets/using-wallets/ethereum/send-a-transaction
- Sign a transaction (React `useSignTransaction`): https://docs.privy.io/wallets/using-wallets/ethereum/sign-a-transaction
- Access tokens and backend verification: https://docs.privy.io/authentication/user-authentication/access-tokens
- Verification key location (Configuration → App settings → Basics): https://docs.privy.io/recipes/dashboard/optimizing
- Configuring EVM networks / custom chains: https://docs.privy.io/basics/react/advanced/configuring-evm-networks
- Automatic embedded wallet creation: https://docs.privy.io/basics/react/advanced/automatic-wallet-creation
- REST `eth_signTransaction` (has a `nonce` field): https://docs.privy.io/api-reference/wallets/ethereum/eth-sign-transaction
- API error codes: https://docs.privy.io/basics/troubleshooting/error-handling/api-errors
- LLM-friendly index: https://docs.privy.io/llms.txt

**Monad**
- Network information (mainnet 143, testnet 10143): https://docs.monad.xyz/developer-essentials/network-information
- Testnets and faucet: https://docs.monad.xyz/developer-essentials/testnets — faucet https://faucet.monad.xyz
- Gas pricing (charged on gas limit): https://docs.monad.xyz/developer-essentials/gas-pricing
- Reserve balance (10 MON default, EIP-7702 effects): https://docs.monad.xyz/developer-essentials/reserve-balance
- Wallet developer guide (nonce tracking, no global mempool view): https://docs.monad.xyz/developer-essentials/wallet-developers
- Block states and RPC tags (`finalized`): https://docs.monad.xyz/monad-arch/consensus/block-states
- Transaction lifecycle: https://docs.monad.xyz/monad-arch/transaction-lifecycle
- Developer portal: https://developers.monad.xyz
- Testnet explorer: https://testnet.monadexplorer.com
- LLM-friendly index: https://docs.monad.xyz/llms.txt

**Tooling**
- Foundry book: https://book.getfoundry.sh
- Next.js 16 docs: bundled at `apps/web/node_modules/next/dist/docs/` (read before framework changes)
- viem chains (includes `monadTestnet`): https://viem.sh/docs/chains/introduction

---

## 12. Second-opinion review: answers received (2026-10-07)

1. **Option A sound?** Only with a durable wallet lock before signing, validation of the returned transaction, and atomic persistence of signed bytes + hash + nonce + broadcast job before sending. Adopted in §7.2.
2. **Can Privy honour a nonce?** Suggested passing it as a hex string. **Confirmed experimentally** (§6); root cause is Privy's truthiness check on numeric 0.
3. **Does knowing the hash remove the need for replacement?** No: it enables rebroadcasting identical bytes, but a stuck transaction can block the wallet indefinitely. Replacement stays; test it against a genuinely pending transaction (§7.3).
4. **Sign-only acceptable when Privy omits the amount?** Yes for the testnet product, with Sendly's review card as the substantive review surface and backend verification against the approved revision before broadcast.
5. **Send mode out of the product path?** Yes. Keep it in the diagnostic harness only.
