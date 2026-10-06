# DemoUSD (test-network demo token)

Minimal ERC-20 for Sendly's Monad testnet demo: `Sendly Demo USD` / `DemoUSD`, 6 decimals, owner-only mint. It has no value and no relationship to any real dollar or stablecoin (PRD Section 3.4).

## Test

```bash
forge test
```

## Deploy to Monad testnet

Use an encrypted Foundry keystore for the deployer; never put a private key in a file or command line.

```bash
cast wallet import sendly-deployer --interactive
export MONAD_TESTNET_RPC_URL=https://testnet-rpc.monad.xyz
forge script script/Deploy.s.sol --rpc-url monad_testnet --account sendly-deployer --broadcast
```

The deployer needs testnet MON for gas. Record the deployed address in `services/api/.env` (`DEMO_TOKEN_ADDRESS`) and in `docs/demo-guide.md`.

## Mint test balances (manual prefunding)

```bash
cast send <DEMO_TOKEN_ADDRESS> "mint(address,uint256)" <WALLET> 100000000 \
  --rpc-url monad_testnet --account sendly-deployer
```

`100000000` base units = 100.000000 DemoUSD.
