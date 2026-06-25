# Phase-3 Cu-64 Common MEGAlib Raw-Hit Run

- status: `PHASE3_CU64_COMMON_MEGALIB_RAW_PASS`
- source_mode: `phase3_cu64_common_parent_resampling`
- stop_condition: `Events`
- pre_trigger_mode: `Everything`
- no `.sim.gz` replay: `True`
- histories: `1000`
- sim_event_count: `1000`
- raw_hit_rows: `1352`
- run_products_retained: `False`
- elapsed_s: `3.997`
- band_summary_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/megalib_cu64_common_raw_smoke_1k/band_summary.csv`

## Smoke Band Counts

| band | events / histories | efficiency_per_parent | top_material_counts |
|---|---:|---:|---|
| `all TES > 0` | `1000 / 1000` | `1` | `{"Copper": 932, "CuNi": 68}` |
| `480-550 keV` | `12 / 1000` | `0.012` | `{"Copper": 12}` |
| `W2 510.58-511.42 keV` | `1 / 1000` | `0.001` | `{"Copper": 1}` |
| `1500-3000 keV` | `1 / 1000` | `0.001` | `{"Copper": 1}` |
| `3000-10000 keV` | `0 / 1000` | `0` | `{}` |

## Detector Hit Summary

| detector | histories_with_hit | hit_rows | deposit_keV_sum |
|---|---:|---:|---:|
| `D4` / `TES_L3` | `1000` | `1349` | `212789` |
| `D2` / `TES_L1` | `3` | `3` | `727.334` |

## Boundary

- This is the MEGAlib side only.
- It validates full-geometry raw-hit plumbing for the Phase-3 common Cu-64 parent stream.
- The native HTsim detector/readout semantics are not yet a FLUKA-equivalent raw-deposit schema.
- Cosima `.sim.gz` run products are deleted by default after parsing.
- FLUKA production comparison, common event building, and production-statistics closure remain open.
