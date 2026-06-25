# Phase-3 Cu-64 Common Raw-Deposit Production

- status: `PHASE3_CU64_COMMON_RAW_PRODUCTION_PASS`
- histories_requested_per_code: `1000000`
- chunks: `20`
- max_parallel: `4`
- parent_list_sha256: `a2b5dbb883e49e16154290c0275561f41a6799f3753f4396262ad07f291a3975`
- work_root_untracked: `/tmp/phase3prod`
- raw_truth_retained_locally: `True`
- started_at_utc: `2026-06-25T13:22:20Z`
- finished_at_utc: `2026-06-25T13:30:50Z`
- wall_elapsed_s: `510.180`
- aggregated_at_utc: `2026-06-25T13:45:56Z`
- aggregation_wall_elapsed_s: `0.004`

## Band Comparison

| band | FLUKA events / histories | MEGAlib events / histories | FLUKA/MEGAlib | z |
|---|---:|---:|---:|---:|
| `all TES > 0` | `6566 / 1000000` | `2797 / 1000000` | `2.34752` | `39.1` |
| `480-550 keV` | `1470 / 1000000` | `1072 / 1000000` | `1.37127` | `7.9` |
| `W2 510.58-511.42 keV` | `1269 / 1000000` | `1008 / 1000000` | `1.25893` | `5.47` |
| `1500-3000 keV` | `1 / 1000000` | `0 / 1000000` | `n/a` | `1` |
| `3000-10000 keV` | `0 / 1000000` | `0 / 1000000` | `n/a` | `n/a` |

## Output Files

- chunk_manifest_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_common_raw_production_1e6/chunk_manifest.csv`
- fluka_band_summary_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_common_raw_production_1e6/fluka_band_summary.csv`
- megalib_band_summary_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_common_raw_production_1e6/megalib_band_summary.csv`
- comparison_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_common_raw_production_1e6/comparison_band_summary.csv`

## Boundary

- This is a production-statistics raw-deposit comparison for the common Cu-64 parent stream.
- Full raw truth is retained only under the ignored local work root.
- This does not yet apply the common active-veto/topology/FoV event builder or analytic W2 response.
