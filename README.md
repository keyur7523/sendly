# Sendly

Voice-first payments on Monad (test network). Product and behavior: [`VOICE_PAYMENTS_PRD.md`](VOICE_PAYMENTS_PRD.md). Visual design: [`SENDLY_DESIGN_GUIDE.md`](SENDLY_DESIGN_GUIDE.md).

## Repository

```text
apps/web/                 Next.js app (Phase 1: signer gate harness at /gate)
services/api/             FastAPI backend (Phase 1: auth, chain adapter, gate endpoints)
contracts/demo-token/     DemoUSD test token (Foundry)
docs/                     Signer gate results, demo funding guide
```

Further directories from PRD Section 25 (worker, evals, generated API types) are added when their build stage starts.

## Phase 1: signer gate (build stages B0–B2)

Goal: prove the embedded wallet signs exactly what Sendly prepares, before any payment code is built. Definition: [`docs/signer-gate.md`](docs/signer-gate.md).

### Prerequisites

- Node 22, Python 3.11+, Foundry
- A Privy app with **email login** enabled. You need its **App ID** and **verification key** (dashboard → App settings).

### 1. Deploy the demo token

```bash
cd contracts/demo-token
forge test
cast wallet import sendly-deployer --interactive
export MONAD_TESTNET_RPC_URL=https://testnet-rpc.monad.xyz
forge script script/Deploy.s.sol --rpc-url monad_testnet --account sendly-deployer --broadcast
```

The deployer account needs testnet MON. Record the address in `docs/demo-guide.md`.

### 2. Backend

```bash
cd services/api
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env    # fill in PRIVY_APP_ID, PRIVY_VERIFICATION_KEY, DEMO_TOKEN_ADDRESS
.venv/bin/pytest
.venv/bin/uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd apps/web
npm install
cp .env.example .env.local   # fill in NEXT_PUBLIC_PRIVY_APP_ID
npm run dev
```

In the Privy dashboard, allow `http://localhost:3000` as an origin.

### 4. Run the gate

1. Open `http://localhost:3000/gate` and sign in with email.
2. Fund the wallet shown (see [`docs/demo-guide.md`](docs/demo-guide.md)).
3. Run checks 1–4, recording each result. Results append to `docs/signer-gate/results.jsonl`.
4. Summarize in the results table in `docs/signer-gate.md`.

The gate endpoints are a harness: no drafts, approvals, or reservations, and the wallet address is not yet bound to the user (that arrives in B3).
