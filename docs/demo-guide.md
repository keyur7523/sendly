# Demo guide: manual prefunding (DEMO-01)

Sendly's first release uses manual prefunding (PRD Section 10.8). No server holds a funding key.

Each tester's embedded wallet needs:

| Asset | Why | Amount for Phase 1 |
|---|---|---|
| Testnet MON | Gas. Monad charges the full gas limit; one pinned transfer costs at most `gasLimit × maxFeePerGas` (about 0.004–0.02 MON at current testnet prices) | 0.5 MON covers the whole gate run |
| DemoUSD | The token being sent | 10 DemoUSD |

## Steps

1. Sign in at `http://localhost:3000/gate`. Copy the wallet address shown under **Gate check 4 · Wallet**.
2. Send testnet MON to that address from a public Monad testnet faucet or from your own funded testnet wallet.
3. Mint DemoUSD as the token owner (see `contracts/demo-token/README.md`):

   ```bash
   cast send "$DEMO_TOKEN_ADDRESS" "mint(address,uint256)" <WALLET> 10000000 \
     --rpc-url monad_testnet --account sendly-deployer
   ```

4. Press **Refresh** on the gate page and confirm both balances.

## Reserve balance note

Monad's reserve-balance rules (PRD Section 10.3) mean a wallet with very little MON may see transactions excluded or reverted. If a gate check fails with a reserve-related error, record it as inconclusive, fund more MON, and rerun.

## Deployed addresses

| Network | Contract | Address | Deployed |
|---|---|---|---|
| Monad testnet (10143) | DemoUSD | `0x701C0eAB78ba95d7604Ee316C52e8FF88f63a9F5` | 2026-10-07, owner `0x4205E140DcF661BDe478236CD760386B12F3c197` |
| Monad testnet (10143) | DemoUSD (abandoned) | `0x7E7DfFC7D515Eb6F7E5BB0919B95597f33F9F1f4` | 2026-10-07; owner set to Foundry's placeholder sender by a script bug, cannot mint. Do not use. |
