# FrameSift

FrameSift audits a public variable-length binary codebook and ingests its
telemetry frames in order. A downstream contract or client can read the exact
decoded tokens from the most recent eight accepted frames.

The constructor fixes an HTTPS feed root under raw GitHub. It accepts a commit
hash or a named branch. Anyone can call `activate()`. The leader and validators
independently fetch `codebook.json`, parse its full contents and agree on the
exact sorted token-to-codeword pairs. The contract audits unique decodability
with the [Sardinas–Patterson criterion](https://www.sciencedirect.com/science/article/pii/S001999586380011X).
It explores residual suffixes until it finds a collision or exhausts the finite
state space. A collision records the shared bits and two distinct token
sequences. The contract only activates ingestion for a uniquely decodable book.

`ingest(expected_seq)` takes a sequence number. The contract fetches
`frames/<seq>.json` itself. Each validator independently checks the frame's
sequence, activated book hash and complete binary parse. Consensus compares
the exact bits and decoded tokens. An accepted frame stores both and advances
the cursor once. The next sequence remains available for retry after an invalid
or unavailable frame. Older frames remain in transaction history as the
eight-frame state buffer rolls over.

The codebook is frozen at activation. Changing a mutable feed's codebook file
cannot change how frames are decoded. The frame's `book_sha256` is the hash of
the UTF-8 JSON array of token/word pairs sorted by token, with compact separators.
Books support two to eight tokens and words of one to eight bits. Frames support
one to 256 bits. The publisher controls the feed contents. The contract verifies
what its validators observe and how those bits decode.

The proof fixtures contain synthetic telemetry. The unique book
`{alpha: 0, beta: 01, gamma: 110}` decodes `0110` as `alpha, gamma`, even
though selecting the longest initial codeword would strand the parser. The
ambiguous book `{alpha: 0, beta: 01, gamma: 10}` gives two parses for
`010` and cannot ingest frames.

```sh
pip install -r requirements-dev.txt
genvm-lint download --version v0.2.16
genvm-lint check contracts/frame_sift.py
python -m pytest tests/direct -q
node --test tests/rpc-preflight.test.cjs
```

The StudioNet workflow deploys each fixture and independently enumerates the
parses of its example frames. Both deployments verified 13 finalized receipts,
including two stored frames and seven expected rejections.
[StudioNet receipts and contract addresses](proofs/README.md) · [Submission text](SUBMISSION.md)

The consensus pattern follows the
[GenLayer Equivalence Principle](https://docs.genlayer.com/developers/intelligent-contracts/equivalence-principle).
Generic CLI transport and test signing helpers are reused under MIT from
[ArchiveLift](https://github.com/gabrieladash123-bit/archive-lift).
