Category: Builder → Intelligent Contracts

Title: FrameSift: Consensus codebook audit and ordered frame ingestion

Notes / Description:

FrameSift audits a published variable-length binary codebook and ingests its telemetry in order. Leader and validators fetch the full codebook independently and compare exact normalized token mappings. A Sardinas–Patterson search activates uniquely decodable books or records a shared bit string with two distinct parses. For each sequence, validators fetch the actual frame, check its codebook binding and independently decode the full bit string. Exact agreement advances the cursor and stores the frame and tokens. Invalid and replayed frames leave the cursor unchanged. The contract retains eight frames. GenVM lint and 18 tests passed. Two StudioNet deployments verified 13 finalized receipts, including two decoded frames, a concrete ambiguity witness and seven expected rejections.

Evidence: [Contract source](contracts/frame_sift.py) · [StudioNet ingestion](https://explorer-studio.genlayer.com/address/0xa12a4eB95Caa886fcFa7f8943633b91d803Edb36) · [Onchain proofs](proofs/README.md)
