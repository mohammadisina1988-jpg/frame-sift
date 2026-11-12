const fs = require('node:fs');
const path = require('node:path');
const {root, assert, equal, digest, sourceHash, invoke, read, rpc, receipt, receiptSummary, save} = require('./transport.cjs');
const {decodeReceipt} = require('./receipt-calldata.cjs');

function allParses(bits, book, offset = 0) {
  if (offset === bits.length) return [[]];
  const paths = [];
  for (const [token, word] of book) {
    if (bits.startsWith(word, offset)) {
      for (const tail of allParses(bits, book, offset + word.length)) paths.push([token, ...tail]);
    }
  }
  return paths;
}

async function main() {
  const scenario = process.env.FRAME_SCENARIO;
  assert(['unique', 'ambiguous'].includes(scenario), 'Choose a supported scenario');
  const revision = process.env.GITHUB_SHA || process.env.FRAME_FIXTURE_REVISION || '';
  assert(/^[a-f0-9]{40}$/.test(revision), 'Missing public fixture revision');
  const prefix = scenario + '-';
  const source = 'https://raw.githubusercontent.com/mohammadisina1988-jpg/frame-sift/' + revision + '/feeds/' + scenario;
  const wallets = JSON.parse(process.env.FRAME_ACCOUNTS || '[]');
  assert(wallets.length === 2 && wallets[0].address !== wallets[1].address, 'Two independent wallets required');
  const code = fs.readFileSync(path.join(root, 'contracts/frame_sift.py'));
  const book = Object.entries(require('../feeds/' + scenario + '/codebook.json')).sort();
  const bookHash = digest(JSON.stringify(book));
  const expected = {source, activation: null, next_seq: 0, retained: 0};
  assert(await rpc('eth_chainId', []) === '0xf22f', 'StudioNet only');

  process.env.FRAME_ACCOUNT = wallets[0].name;
  const deployment = await invoke(prefix + 'deploy', ['deploy', '--contract', 'contracts/frame_sift.py', '--args', source]);
  const deployed = await receipt(prefix + 'deploy', deployment, true);
  const contract = deployed.to_address || deployed.recipient;
  assert(/^0x[0-9a-f]{40}$/i.test(contract), 'Missing deployed contract');
  assert(code.equals(Buffer.from(deployed.data.contract_code, 'base64')), 'Deployed source mismatch');
  const report = {scenario, contract, deployment, source_sha256: sourceHash, revision, trace: [], frames: []};

  async function verify(label, raw, actor, args, error = null) {
    const info = receiptSummary(raw);
    assert((raw.from_address || raw.sender).toLowerCase() === wallets[actor].address, 'Wrong receipt sender');
    assert((raw.to_address || raw.recipient).toLowerCase() === contract.toLowerCase(), 'Wrong receipt recipient');
    assert(equal(await decodeReceipt(raw), args), 'Unexpected signed calldata');
    if (error) {
      const payload = Buffer.from(raw.consensus_data.leader_receipt[0].result, 'base64');
      assert(payload[0] === 1 && payload.subarray(1).toString() === error, 'Wrong revert reason: ' + label);
    }
    const state = await read(prefix + label + '-state', ['call', contract, 'get_state']);
    if (!equal(state, expected)) save(prefix + 'state-mismatch', {label, state, expected});
    assert(equal(state, expected), 'Unexpected state after ' + label);
    report.trace.push({label, ...info, signer: wallets[actor].address, args, error, state});
    save(prefix + 'progress', report);
  }
  await verify('deploy', deployed, 0, {args: [source]});

  async function write(label, actor, method, args, error, update = () => {}) {
    process.env.FRAME_ACCOUNT = wallets[actor].name;
    const cli = ['write', contract, method];
    if (args.length) cli.push('--args', ...args.map(String));
    const hash = await invoke(prefix + label, cli);
    const raw = await receipt(prefix + label, hash, !error);
    update();
    await verify(label, raw, actor, {method, args}, error);
  }
  await write('before-audit', 1, 'ingest', [0], 'No active codebook');
  await write('activate', 1, 'activate', [], null, () => {
    const witness = scenario === 'ambiguous'
      ? {bits: '010', left: ['alpha', 'gamma'], right: ['beta', 'alpha']} : null;
    if (witness) {
      const parses = allParses(witness.bits, book);
      assert(parses.length === 2 && parses.some(x => equal(x, witness.left))
        && parses.some(x => equal(x, witness.right)), 'Invalid ambiguity fixture');
    }
    expected.activation = {outcome: scenario.toUpperCase(), book, book_sha256: bookHash, witness};
  });
  if (scenario === 'unique') {
    for (const seq of [0, 1]) {
      const fixture = require('../feeds/unique/frames/' + seq + '.json');
      const parses = allParses(fixture.bits, book);
      assert(parses.length === 1 && fixture.book_sha256 === bookHash, 'Fixture must have one parse');
      await write('frame-' + seq, seq, 'ingest', [seq], null, () => {
        expected.next_seq++;
        expected.retained++;
      });
      const frame = await read(prefix + 'stored-frame-' + seq, ['call', contract, 'get_frame', '--args', String(seq)]);
      assert(equal(frame, {...fixture, tokens: parses[0]}), 'Stored frame differs from independent parse');
      report.frames.push(frame);
    }
    await write('replay', 1, 'ingest', [0], 'Unexpected sequence');
    assert(allParses(require('../feeds/unique/frames/2.json').bits, book).length === 0, 'Expected an invalid frame');
    await write('invalid-frame', 0, 'ingest', [2], 'Undecodable frame');
  } else {
    await write('blocked-frame', 0, 'ingest', [0], 'No active codebook');
  }
  await write('reaudit', 0, 'activate', [], 'Already audited');
  assert(code.equals(Buffer.from(await rpc('gen_getContractCode', [contract]), 'base64')), 'Fresh source read mismatch');
  save(prefix + 'verified', report);
  console.log(JSON.stringify({scenario, contract, deployment, receipts: report.trace.length, final: expected}));
}

main().catch(error => { console.error(error.stack); process.exitCode = 1; });
