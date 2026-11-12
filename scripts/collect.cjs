const fs = require('node:fs');
const path = require('node:path');
const {root, assert, digest, equal, sourceHash, receiptSummary, save} = require('./transport.cjs');

const runs = process.argv.slice(2);
const cases = {
  unique: ['deploy', 'before-audit', 'activate', 'frame-0', 'frame-1', 'replay', 'invalid-frame', 'reaudit'],
  ambiguous: ['deploy', 'before-audit', 'activate', 'blocked-frame', 'reaudit'],
};
const errors = {'before-audit': 'No active codebook', replay: 'Unexpected sequence',
  'invalid-frame': 'Undecodable frame', 'blocked-frame': 'No active codebook', reaudit: 'Already audited'};
const explorer = 'https://explorer-studio.genlayer.com/';
const repo = 'https://github.com/mohammadisina1988-jpg/frame-sift';
assert(runs.length === 2 && runs.every(id => /^\d+$/.test(id)) && runs[0] !== runs[1],
  'Pass the completed unique and ambiguous run IDs');

const instances = [];
const files = [];
let revision;
let successes = 0;
let rejections = 0;
for (const [i, [scenario, labels]] of Object.entries(cases).entries()) {
  const folder = path.join(root, '.proof-journal', 'run-' + runs[i]);
  const read = label => JSON.parse(fs.readFileSync(path.join(folder, scenario + '-' + label + '.json')));
  const report = read('verified');
  revision ??= report.revision;
  assert(report.scenario === scenario && report.source_sha256 === sourceHash && report.revision === revision,
    'Proof must match the source and fixture commit');
  assert(equal(report.trace.map(step => step.label), labels), 'Unexpected trace');
  let previous;
  for (const step of report.trace) {
    const raw = read(step.label + '-receipt');
    const summary = receiptSummary(raw);
    assert(summary.hash === step.hash && summary.status === 'FINALIZED' && summary.result === 'MAJORITY_AGREE'
      && summary.agree > (summary.agree + summary.disagree + summary.idle) / 2, 'Finalized strict majority required');
    assert((raw.from_address || raw.sender).toLowerCase() === step.signer
      && (raw.to_address || raw.recipient).toLowerCase() === report.contract.toLowerCase(), 'Receipt identity mismatch');
    if (step.label === 'deploy') {
      assert(summary.hash === report.deployment && digest(Buffer.from(raw.data.contract_code, 'base64')) === sourceHash,
        'Deployment source mismatch');
    }
    const error = errors[step.label];
    if (error) {
      const payload = Buffer.from(raw.consensus_data.leader_receipt[0].result, 'base64');
      assert(summary.execution === 'ERROR' && payload[0] === 1 && payload.subarray(1).toString() === error
        && equal(step.state, previous), 'Expected rejection with unchanged state');
      rejections++;
    } else {
      assert(['SUCCESS', 'FINISHED_WITH_RETURN'].includes(summary.execution), 'Expected successful execution');
      successes++;
    }
    previous = step.state;
    files.push([scenario + '-' + step.label + '-receipt', raw]);
  }
  const audit = report.trace.find(step => step.label === 'activate');
  assert(audit.signer !== report.trace[0].signer, 'Permissionless activation was not exercised');
  const {activation, next_seq: next} = previous;
  const book = Object.fromEntries(activation.book);
  const encode = tokens => tokens.map(token => {
    assert(Object.hasOwn(book, token), 'Unknown token');
    return book[token];
  }).join('');
  assert(digest(JSON.stringify(activation.book)) === activation.book_sha256, 'Book commitment mismatch');
  assert(activation.outcome === scenario.toUpperCase(), 'Wrong audit outcome');
  if (scenario === 'ambiguous') {
    const {bits, left, right} = activation.witness;
    assert(!equal(left, right) && encode(left) === bits && encode(right) === bits
      && next === 0 && report.frames.length === 0, 'Invalid ambiguity witness or frame state');
  } else {
    assert(next === 2 && report.frames.length === 2 && activation.witness === null, 'Unexpected accepted frame count');
    for (const [seq, frame] of report.frames.entries()) {
      const fixture = require('../feeds/unique/frames/' + seq + '.json');
      assert(frame.seq === seq && frame.book_sha256 === activation.book_sha256
        && frame.bits === fixture.bits && encode(frame.tokens) === frame.bits, 'Invalid frame record');
    }
  }
  instances.push({scenario, contract: report.contract, deployment: report.deployment, activation: audit.hash,
    frame_transactions: report.trace.filter(step => step.label.startsWith('frame-')).map(step => step.hash),
    witness: activation.witness, workflow: repo + '/actions/runs/' + runs[i]});
  files.push([scenario + '-verified', report]);
}

for (const [name, value] of files) save(name, value);
save('index', {source_sha256: sourceHash, revision, successes, rejections, instances});
const rows = instances.map(x => '| ' + [
  x.scenario, '[Contract](' + explorer + 'address/' + x.contract + ')',
  '[Deploy](' + explorer + 'tx/' + x.deployment + ')',
  '[Activate](' + explorer + 'tx/' + x.activation + ')', '[Run](' + x.workflow + ')',
].join(' | ') + ' |');
fs.writeFileSync(path.join(root, 'proofs/README.md'), [
  '# FrameSift StudioNet proofs', '',
  'Verified ' + (successes + rejections) + ' finalized receipts across two deployments, with '
    + successes + ' successful calls and ' + rejections + ' expected rejections.', '',
  '| Scenario | Address | Deployment | Audit | Workflow |', '|---|---|---|---|---|', ...rows, '',
  'The unique book stored two frames. Its first frame, `0110`, decodes as `alpha, gamma`.',
  'The ambiguous book stored two parses of `010` and refused ingestion.', '',
  'Source SHA-256: `' + sourceHash + '`.', 'Fixture commit: `' + revision + '`.', '',
].join('\n'));
console.log(JSON.stringify({sourceHash, successes, rejections, instances}, null, 2));
