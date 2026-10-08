import pytest
from app.chain.payload import PayloadError, parse_amount, require_address
from app.chain.rpc import RpcUnavailable
from tests.conftest import auth_header
from tests.test_gate_api import client, node, prepare_transfer, sign, rpc_tx, receipt
from eth_account import Account

def test_exact_uint256_amount_conversion():
    assert parse_amount('12345678901234567890123.123456',6)==12345678901234567890123123456

def test_extreme_exponent_is_validation_error():
    with pytest.raises(PayloadError):
        parse_amount('1e1000000',6)

def test_invalid_mixed_case_checksum_rejected():
    with pytest.raises(PayloadError):
        require_address('0x52908400098527886e0F7030069857D2E4169EE7','recipient')

def test_wrong_rpc_chain_rejected_at_prepare(client,auth_header,node):
    dispatch=node.dispatch
    node.dispatch=lambda method,params: hex(1) if method=='eth_chainId' else dispatch(method,params)
    response=client.post('/v1/gate/prepare',json={'sender':Account.create().address,'kind':'self_transfer'},headers=auth_header())
    assert response.status_code==503

@pytest.mark.parametrize('path,body',[
    ('/v1/gate/prepare',{}),('/v1/gate/inspect-signed',{}),
    ('/v1/gate/broadcast',{}),('/v1/gate/verify',{}),('/v1/gate/results',{})])
def test_all_gate_writes_require_auth(client,path,body):
    assert client.post(path,json=body).status_code==401

@pytest.mark.parametrize('path',['inspect-signed','broadcast','verify'])
def test_all_prepared_reads_and_writes_enforce_owner(client,auth_header,path):
    account=Account.create()
    prepared=prepare_transfer(client,auth_header('did:privy:alice'),account.address)
    raw,tx_hash=sign(account,prepared['pinned'])
    body={'prepared_id':prepared['prepared_id'],'signed_transaction':raw,'tx_hash':tx_hash}
    assert client.post('/v1/gate/'+path,json=body,headers=auth_header('did:privy:bob')).status_code==404

def test_transport_failure_keeps_known_hash_unknown(client,auth_header):
    account=Account.create()
    prepared=prepare_transfer(client,auth_header(),account.address)
    raw,tx_hash=sign(account,prepared['pinned'])
    async def unavailable(raw):
        raise RpcUnavailable('simulated timeout after submission')
    client.app.state.chain.broadcast=unavailable
    result=client.post('/v1/gate/broadcast',json={'prepared_id':prepared['prepared_id'],'signed_transaction':raw},headers=auth_header()).json()
    assert result['broadcast']=='unknown'
    assert result['tx_hash']==tx_hash

def test_noncanonical_receipt_never_finalizes(client,auth_header,node):
    account=Account.create()
    prepared=prepare_transfer(client,auth_header(),account.address)
    tx_hash='0x'+'ab'*32
    node.transactions[tx_hash]=rpc_tx(account,prepared['pinned'],tx_hash)
    node.receipts[tx_hash]={**receipt(account,node.finalized-1),'blockHash':'0xnoncanonical'}
    result=client.post('/v1/gate/verify',json={'prepared_id':prepared['prepared_id'],'tx_hash':tx_hash},headers=auth_header()).json()
    assert result['status']!='finalized'
