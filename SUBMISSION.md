Category: Builder → Intelligent Contracts

Title: FrameSift: Consensus codebook audit and ordered frame ingestion

Notes / Description:

FrameSift audits a published variable-length binary codebook and ingests its telemetry in order. Leader and validators fetch the full codebook independently and compare its exact normalized token mappings. A finite Sardinas–Patterson search either activates the unique code or records a shared bit string with two distinct parses. For each sequence, validators fetch the actual frame, check its codebook binding and independently derive the complete decoded token list. Exact agreement on bits and tokens advances the cursor and stores the decoded frame. Invalid and replayed frames leave the cursor unchanged. The contract retains eight frames and supports public commit or branch feeds.
