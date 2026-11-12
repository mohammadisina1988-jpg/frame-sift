# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
from collections import deque
from hashlib import sha256
import json
import re


SOURCE = (r'https://raw\.githubusercontent\.com/[A-Za-z0-9-]{1,39}/'
          r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}/(?:[a-f0-9]{40}|refs/heads/[A-Za-z0-9_-]{1,40})/'
          r'feeds/[A-Za-z0-9_-]{1,32}')
HISTORY = 8


def fail(message):
    raise gl.vm.UserError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


def unique_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError('Duplicate JSON key')
        obj[key] = value
    return obj


def fetch_json(url):
    try:
        response = gl.nondet.web.get(url)
        if response.status != 200 or len(response.body) > 2048:
            fail('Source unavailable')
        return json.loads(response.body.decode('utf-8'), object_pairs_hook=unique_keys)
    except Exception:
        fail('Source unavailable or invalid JSON')


def verifier(sample):
    def verify(leader):
        try:
            local = sample()
        except gl.vm.UserError as error:
            return (not isinstance(leader, gl.vm.Return)
                    and getattr(leader, 'message', None) == error.message)
        except Exception:
            return False
        return isinstance(leader, gl.vm.Return) and local == leader.calldata

    return verify


def observe_book(url):
    def sample():
        obj = fetch_json(url)
        if not isinstance(obj, dict) or not 2 <= len(obj) <= 8:
            fail('Invalid codebook')
        if any(not re.fullmatch(r'[a-z][a-z0-9_]{0,19}', token)
               or not isinstance(word, str) or not re.fullmatch(r'[01]{1,8}', word)
               for token, word in obj.items()):
            fail('Invalid codebook')
        return [[token, obj[token]] for token in sorted(obj)]

    return gl.vm.run_nondet_unsafe(sample, verifier(sample))


def ambiguity(book):
    """Explore Sardinas–Patterson residuals and keep paths to a collision."""
    queue = deque()
    seen = set()
    words = dict(book)

    def enqueue(residual, longer, left, right):
        state = (residual, longer)
        if state not in seen:
            seen.add(state)
            queue.append((residual, longer, left, right))

    for i, (left, a) in enumerate(book):
        for right, b in book[i + 1:]:
            if a == b:
                return {'bits': a, 'left': [left], 'right': [right]}
            if a.startswith(b):
                enqueue(a[len(b):], 0, [left], [right])
            elif b.startswith(a):
                enqueue(b[len(a):], 1, [left], [right])

    while queue:
        residual, longer, left, right = queue.popleft()
        for token, word in book:
            extended_left = left + [token] if longer == 1 else left
            extended_right = right + [token] if longer == 0 else right
            if residual == word:
                bits = ''.join(words[x] for x in extended_left)
                return {'bits': bits, 'left': extended_left, 'right': extended_right}
            if residual.startswith(word):
                enqueue(residual[len(word):], longer, extended_left, extended_right)
            elif word.startswith(residual):
                enqueue(word[len(residual):], 1 - longer, extended_left, extended_right)
    return None


def decode(bits, book):
    """Find the single complete parse of a frame under an activated codebook."""
    end = len(bits)
    choices = [None] * (end + 1)
    for start in range(end - 1, -1, -1):
        for token, word in book:
            stop = start + len(word)
            if bits.startswith(word, start) and (stop == end or choices[stop] is not None):
                choices[start] = (token, stop)
                break
    if choices[0] is None:
        fail('Undecodable frame')
    tokens = []
    start = 0
    while start < end:
        token, start = choices[start]
        tokens.append(token)
    return tokens


def observe_frame(url, expected, book, book_hash):
    def sample():
        obj = fetch_json(url)
        if (not isinstance(obj, dict) or set(obj) != {'seq', 'bits', 'book_sha256'}
                or type(obj['seq']) is not int or obj['seq'] != expected):
            fail('Invalid frame sequence')
        if obj['book_sha256'] != book_hash:
            fail('Wrong codebook')
        bits = obj['bits']
        if not isinstance(bits, str) or not re.fullmatch(r'[01]{1,256}', bits):
            fail('Invalid frame bits')
        return {'seq': expected, 'bits': bits, 'book_sha256': book_hash,
                'tokens': decode(bits, book)}

    return gl.vm.run_nondet_unsafe(sample, verifier(sample))


class FrameSift(gl.Contract):
    source: str
    activation: str
    next_seq: u256
    frames: DynArray[str]

    def __init__(self, source: str):
        if not re.fullmatch(SOURCE, source):
            fail('Invalid source root')
        self.source = source
        self.activation = 'null'
        self.next_seq = u256(0)

    @gl.public.write
    def activate(self) -> None:
        if self.activation != 'null':
            fail('Already audited')
        book = observe_book(self.source + '/codebook.json')
        witness = ambiguity(book)
        self.activation = canonical({'outcome': 'UNIQUE' if witness is None else 'AMBIGUOUS',
                                     'book': book, 'book_sha256': digest(book), 'witness': witness})

    @gl.public.write
    def ingest(self, expected_seq: int) -> None:
        activation = json.loads(self.activation)
        if activation is None or activation['outcome'] != 'UNIQUE':
            fail('No active codebook')
        seq = int(self.next_seq)
        if expected_seq != seq:
            fail('Unexpected sequence')
        if seq >= 2**64:
            fail('Sequence exhausted')
        url = self.source + '/frames/' + str(seq) + '.json'
        frame = observe_frame(url, seq, activation['book'], activation['book_sha256'])
        if len(self.frames) < HISTORY:
            self.frames.append(canonical(frame))
        else:
            self.frames[seq % HISTORY] = canonical(frame)
        self.next_seq = u256(seq + 1)

    @gl.public.view
    def get_state(self) -> dict:
        return {'source': self.source, 'activation': json.loads(self.activation),
                'next_seq': int(self.next_seq), 'retained': len(self.frames)}

    @gl.public.view
    def get_frame(self, seq: int) -> dict:
        next_seq = int(self.next_seq)
        if not 0 <= seq < next_seq or next_seq - seq > HISTORY:
            fail('Frame not retained')
        return json.loads(self.frames[seq % HISTORY])
