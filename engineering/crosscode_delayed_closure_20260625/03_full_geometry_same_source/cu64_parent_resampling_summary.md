# Phase-3 Cu-64 Parent Resampling Authority

- status: `CU64_PARENT_RESAMPLING_AUTHORITY_COMPLETE`
- histories: `1000000`
- seed: `20260625_phase3_cu64`
- selected_unique_positions: `6927`
- selection_stream_sha256: `3be6695480c8b130ea9a396cbe34efdc47e97be4aa3575bcf4b2968be147a98e`
- full_list_written: `True`
- full_list_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/full_untracked/cu64_parent_resampling_1e6.csv`
- full_list_csv_sha256: `a2b5dbb883e49e16154290c0275561f41a6799f3753f4396262ad07f291a3975`

## Boundary

- This is a deterministic parent-index resampling authority for Phase-3 common Cu-64 runs.
- The full list is reproducible from `cu64_common_positions.csv`, this script, the seed, and `histories`.
- The full 1e6-row CSV is intentionally written under ignored `full_untracked/`; git keeps only hashes, summaries, and a bounded sample.
- This does not run FLUKA or MEGAlib transport.
