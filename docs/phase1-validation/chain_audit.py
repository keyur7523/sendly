import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from eth_abi import decode
from app.chain.adapter import ChainAdapter
from app.chain.payload import PinnedTransaction, encode_token_transfer
from app.chain.rpc import JsonRpcClient
from app.config import Settings

WALLET = '0xfA339b0Fc9D01073AF67B668ba5813d677B85956'
TOKEN = '0x701C0eAB78ba95d7604Ee316C52e8FF88f63a9F5'
HASHES = {
    'product_transfer': '0xa088ee2fa8d06337e5629a31baac1e5ab53f14c61ae2529ee85299d1fa118a43',
    'held_replacement_winner': '0x52c65134da910985e57cfe060d8bdd3667cc0babf58542381bec8ffeeea41053',
    'queued_original': '0x7504b67ec2dde94476f390e702d3933716620256c837b3ece74effae7bf43a20',
    'queued_replacement': '0xbc582e0b337517d77e9efa7c7d9cd18e692c11913441b55eba4c270e54446649',
    'gap_filler': '0x387f58481d04eb86cff0349b894d62a3694830a906696dd0bfa2afa2c41a35f2',
}

async def main():
    rpc = JsonRpcClient('https://testnet-rpc.monad.xyz', 20)
    settings = Settings(_env_file=None, privy_app_id='audit', privy_verification_key='audit', demo_token_address=TOKEN)
    chain = ChainAdapter(rpc, settings)
    try:
        await chain.check_chain()
        results = {'chain_id': 10143, 'wallet_type': await chain.wallet_type(WALLET), 'finalized_block': await chain.finalized_block_number(), 'transactions': {}}
        for name, tx_hash in HASHES.items():
            tx = await rpc.call('eth_getTransactionByHash', tx_hash)
            receipt = await rpc.call('eth_getTransactionReceipt', tx_hash)
            item = {'hash': tx_hash, 'found': tx is not None, 'receipt_found': receipt is not None}
            if tx:
                item.update({k: tx.get(k) for k in ['from','to','nonce','gas','maxFeePerGas','maxPriorityFeePerGas','value','input','chainId','type']})
            if receipt:
                block = await rpc.call('eth_getBlockByNumber', receipt['blockNumber'], False)
                item.update(status=int(receipt['status'],16), block=int(receipt['blockNumber'],16), canonical=block['hash'].lower()==receipt['blockHash'].lower())
            results['transactions'][name] = item
        # Expected payload from the documented .01 DemoUSD self-transfer, nonce 8,
        # gate fee settings and 39374 gas. Do not derive the expectation from RPC.
        expected = PinnedTransaction(chain_id=10143, sender=WALLET, to=TOKEN, data=encode_token_transfer(WALLET,10000), value=0, nonce=8, gas=39374, max_fee_per_gas=202000000000, max_priority_fee_per_gas=2000000000)
        results['adapter_product_verification'] = asdict(await chain.verify(expected,HASHES['product_transfer']))
        results['token_metadata'] = {}
        for label, selector, kind in [('decimals','0x313ce567','uint8'),('symbol','0x95d89b41','string'),('owner','0x8da5cb5b','address')]:
            raw=await rpc.call('eth_call', {'to':TOKEN,'data':selector}, 'latest')
            results['token_metadata'][label]=decode([kind],bytes.fromhex(raw[2:]))[0]
        Path(__file__).with_name('chain-evidence.json').write_text(json.dumps(results,indent=2))
        print(json.dumps(results,indent=2))
    finally:
        await rpc.aclose()

asyncio.run(main())
