# Phase-3 Cu-64 Common FLUKA Raw-Deposit Run

- status: `PHASE3_CU64_COMMON_FLUKA_RAW_PASS`
- source_mode: `phase3_cu64_common_parent_resampling`
- no `.sim.gz` replay: `True`
- histories: `1000`
- raw_event_rows: `107`
- scoring_closure: `PASS`
- elapsed_s: `5.871`
- band_summary_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/fluka_cu64_common_raw_smoke_1k/band_summary.csv`

## Smoke Band Counts

| band | events / histories | efficiency_per_parent | top_material_counts |
|---|---:|---:|---|
| `all TES > 0` | `5 / 1000` | `0.005` | `{"Copper": 5}` |
| `480-550 keV` | `2 / 1000` | `0.002` | `{"Copper": 2}` |
| `W2 510.58-511.42 keV` | `2 / 1000` | `0.002` | `{"Copper": 2}` |
| `1500-3000 keV` | `0 / 1000` | `0` | `{}` |
| `3000-10000 keV` | `0 / 1000` | `0` | `{}` |

## Scoring Closure

- raw_dump_tes_total_keV: `1458.19986065`
- score_tes_total_keV: `1458.1998604550001`
- tes_relative_delta: `1.3372635812717172e-10`
- raw_dump_shield_total_keV: `33465.141153662`
- score_shield_total_keV: `33465.141161299995`
- shield_relative_delta: `2.282373373635355e-10`

## Boundary

- This is the FLUKA side only.
- It validates full-geometry raw-deposit plumbing for the Phase-3 common Cu-64 parent stream.
- MEGAlib runner/parser smoke has run separately, but detector/readout semantic calibration, common event building, and production-statistics closure remain open.
