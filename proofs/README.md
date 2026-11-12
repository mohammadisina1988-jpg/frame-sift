# FrameSift StudioNet proofs

Verified 13 finalized receipts across two deployments, with 6 successful calls and 7 expected rejections.

| Scenario | Address | Deployment | Audit | Workflow |
|---|---|---|---|---|
| unique | [Contract](https://explorer-studio.genlayer.com/address/0xa12a4eB95Caa886fcFa7f8943633b91d803Edb36) | [Deploy](https://explorer-studio.genlayer.com/tx/0x0fddf245e7535f90a9dd018410a4e81d34c387e257a884f51f953a109a9108bd) | [Activate](https://explorer-studio.genlayer.com/tx/0xfcd0298202226339ecc8b7d2c55e5eb117fda2a6b570407278c5617e5e463974) | [Run](https://github.com/mohammadisina1988-jpg/frame-sift/actions/runs/43174522866) |
| ambiguous | [Contract](https://explorer-studio.genlayer.com/address/0xefb5A69a0a8F929Bae4F2aA329B2fA31aCaCFf1F) | [Deploy](https://explorer-studio.genlayer.com/tx/0x1efea58bf318c16161c86f190c327cf7b6b4fc5a353cfcfa471d780d074a967a) | [Activate](https://explorer-studio.genlayer.com/tx/0x65248851e675256404d1e305339f0b118104d3f099dbefac3657f415577e4a81) | [Run](https://github.com/mohammadisina1988-jpg/frame-sift/actions/runs/43174532472) |

The unique book stored two frames. Its first frame, `0110`, decodes as `alpha, gamma`.
The ambiguous book stored two parses of `010` and refused ingestion.

Source SHA-256: `831f4afa47be18388f10be87fa5b81b7b6ab806036e79900c6edda435a2cbcf9`.
Fixture commit: `dcc13151ab4b311fd02443cfafb4a4e023d95592`.
