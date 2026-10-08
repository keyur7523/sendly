const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');

const web = path.resolve(__dirname, '../../apps/web');
const webRequire = createRequire(path.join(web, 'package.json'));
const sdkRequire = createRequire(webRequire.resolve('@privy-io/react-auth'));
const ts = webRequire('typescript');
const { toViemTransactionSerializable } = sdkRequire('@privy-io/ethereum');
const compiled = ts.transpileModule(fs.readFileSync(path.join(web, 'lib/gate.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const mod = { exports: {} };
new Function('exports', 'require', 'module', compiled)(mod.exports, webRequire, mod);

for (const nonce of [0, 1, 3, 8]) {
  const wallet_request = {
    nonce, chainId: 10143,
    from: '0x1111111111111111111111111111111111111111',
    to: '0x1111111111111111111111111111111111111111',
    data: '0x', value: '0x0', gasLimit: '0x5208',
    maxFeePerGas: '0x2f08236400', maxPriorityFeePerGas: '0x77359400', type: 2,
  };
  const request = mod.exports.toWalletRequest({ wallet_request });
  assert.equal(request.nonce, `0x${nonce.toString(16)}`);
  assert.equal(toViemTransactionSerializable(request).nonce, nonce);
  console.log(JSON.stringify({ input: nonce, encoded: request.nonce, pass: true }));
}
