from hashlib import sha256
import json
import re

import pytest


SOURCE = ('https://raw.githubusercontent.com/mohammadisina1988-jpg/frame-sift/'
          'refs/heads/main/feeds/unique')
BOOK = {'alpha': '0', 'beta': '01', 'gamma': '110'}
BOOK_SHA256 = sha256(json.dumps(sorted(BOOK.items()), separators=(',', ':')).encode()).hexdigest()


def deploy(direct_deploy):
    return direct_deploy('contracts/frame_sift.py', SOURCE, sdk_version='v0.2.16')


def reply(vm, suffix, value, status=200):
    vm.clear_mocks()
    body = value if isinstance(value, bytes) else json.dumps(value).encode()
    vm.mock_web(re.escape(SOURCE + suffix), {'status': status, 'body': body})


def activate(vm, contract):
    reply(vm, '/codebook.json', BOOK)
    contract.activate()


def frame(seq, bits, book_hash=BOOK_SHA256):
    return {'seq': seq, 'bits': bits, 'book_sha256': book_hash}


def test_unique_non_prefix_book_requires_complete_frame_parse(direct_vm, direct_deploy):
    contract = deploy(direct_deploy)
    with direct_vm.expect_revert('No active codebook'):
        contract.ingest(0)
    activate(direct_vm, contract)
    audit = contract.get_state()['activation']
    assert audit == {'outcome': 'UNIQUE', 'book': [list(item) for item in sorted(BOOK.items())],
                     'book_sha256': BOOK_SHA256, 'witness': None}
    assert direct_vm.run_validator() is True
    reply(direct_vm, '/frames/0.json', frame(0, '0110'))
    contract.ingest(0)
    assert contract.get_frame(0) == {**frame(0, '0110'), 'tokens': ['alpha', 'gamma']}
    assert direct_vm.run_validator() is True
    reply(direct_vm, '/frames/0.json', frame(0, '01'))
    assert direct_vm.run_validator() is False
    assert contract.get_state()['next_seq'] == 1
    with direct_vm.expect_revert('Unexpected sequence'):
        contract.ingest(0)


@pytest.mark.parametrize('book', [
    {'alpha': '0', 'beta': '01', 'gamma': '10'},
    {'alpha': '010', 'beta': '010'},
])
def test_ambiguity_witness_proves_two_distinct_parses(direct_vm, direct_deploy, book):
    contract = deploy(direct_deploy)
    reply(direct_vm, '/codebook.json', book)
    contract.activate()
    audit = contract.get_state()['activation']
    assert audit['outcome'] == 'AMBIGUOUS'
    assert direct_vm.run_validator() is True
    witness = audit['witness']
    assert witness['left'] != witness['right']
    assert ''.join(book[token] for token in witness['left']) == witness['bits']
    assert ''.join(book[token] for token in witness['right']) == witness['bits']
    with direct_vm.expect_revert('No active codebook'):
        contract.ingest(0)


def test_validators_compare_full_book_and_normalize_json_order(direct_vm, direct_deploy):
    contract = deploy(direct_deploy)
    activate(direct_vm, contract)
    reply(direct_vm, '/codebook.json', {key: BOOK[key] for key in reversed(BOOK)})
    assert direct_vm.run_validator() is True
    reply(direct_vm, '/codebook.json', {**BOOK, 'gamma': '10'})
    assert direct_vm.run_validator() is False
    with direct_vm.expect_revert('Already audited'):
        contract.activate()


def test_duplicate_keys_do_not_activate(direct_vm, direct_deploy):
    contract = deploy(direct_deploy)
    reply(direct_vm, '/codebook.json', b'{"alpha":"0","alpha":"11","beta":"1"}')
    with direct_vm.expect_revert('Source unavailable or invalid JSON'):
        contract.activate()
    assert contract.get_state()['activation'] is None


@pytest.mark.parametrize(('value', 'reason'), [
    (frame(1, '0'), 'Invalid frame sequence'),
    (frame(True, '0'), 'Invalid frame sequence'),
    (frame(0, '0', '0' * 64), 'Wrong codebook'),
    (frame(0, '010x'), 'Invalid frame bits'),
    (frame(0, '1'), 'Undecodable frame'),
])
def test_rejected_frame_can_be_corrected_without_advancing(direct_vm, direct_deploy, value, reason):
    contract = deploy(direct_deploy)
    activate(direct_vm, contract)
    before = contract.get_state()
    reply(direct_vm, '/frames/0.json', value)
    with direct_vm.expect_revert(reason):
        contract.ingest(0)
    assert contract.get_state() == before
    reply(direct_vm, '/frames/0.json', frame(0, '0'))
    contract.ingest(0)
    assert contract.get_frame(0)['tokens'] == ['alpha']


def test_bounded_history_uses_exact_sequence_on_wrap(direct_vm, direct_deploy):
    contract = deploy(direct_deploy)
    activate(direct_vm, contract)
    for seq in range(10):
        reply(direct_vm, f'/frames/{seq}.json', frame(seq, '0'))
        contract.ingest(seq)
    assert contract.get_state()['retained'] == 8
    assert contract.get_state()['next_seq'] == 10
    assert [contract.get_frame(seq)['seq'] for seq in range(2, 10)] == list(range(2, 10))
    for seq in (-1, 1, 10):
        with direct_vm.expect_revert('Frame not retained'):
            contract.get_frame(seq)
