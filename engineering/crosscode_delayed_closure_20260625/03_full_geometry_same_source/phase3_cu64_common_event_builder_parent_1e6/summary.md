# Phase-3 Cu-64 Common Parent-History Event Builder

- status: `PHASE3_CU64_COMMON_PARENT_EVENT_BUILDER_PASS`
- work_root: `/tmp/phase3prod`
- active_veto_threshold_keV: `50.0`
- w2_sigma_keV: `0.14`

## Stage Ratios

| metric | stage | FLUKA sum_w / histories | MEGAlib sum_w / histories | FLUKA/MEGAlib | z |
|---|---|---:|---:|---:|---:|
| `all TES > 0` | `raw` | `6566 / 1000000` | `2797 / 1000000` | `2.34752` | `39.1` |
| `all TES > 0` | `active_veto` | `4434 / 1000000` | `1609 / 1000000` | `2.75575` | `36.4` |
| `480-550 keV` | `raw` | `1470 / 1000000` | `1072 / 1000000` | `1.37127` | `7.9` |
| `480-550 keV` | `active_veto` | `779 / 1000000` | `606 / 1000000` | `1.28548` | `4.65` |
| `W2 510.58-511.42 keV` | `raw` | `1269 / 1000000` | `1008 / 1000000` | `1.25893` | `5.47` |
| `W2 510.58-511.42 keV` | `active_veto` | `662 / 1000000` | `563 / 1000000` | `1.17584` | `2.83` |
| `1500-3000 keV` | `raw` | `1 / 1000000` | `0 / 1000000` | `n/a` | `1` |
| `1500-3000 keV` | `active_veto` | `1 / 1000000` | `0 / 1000000` | `n/a` | `1` |
| `3000-10000 keV` | `raw` | `0 / 1000000` | `0 / 1000000` | `n/a` | `n/a` |
| `3000-10000 keV` | `active_veto` | `0 / 1000000` | `0 / 1000000` | `n/a` | `n/a` |
| `W2 analytic Gaussian expectation` | `raw` | `1265.99 / 1000000` | `1005.19 / 1000000` | `1.25946` | `5.48` |
| `W2 analytic Gaussian expectation` | `active_veto` | `660.692 / 1000000` | `561.302 / 1000000` | `1.17707` | `2.85` |

## Interpretation

- The common parent-history event builder does not remove the discrepancy.
- Raw W2 and analytic Gaussian W2 give the same FLUKA/MEGAlib ratio within statistics.
- The first failed phase is therefore full-geometry raw-deposit/source-material coupling, before common detector response.

## Output Files

- stage_rows_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_common_event_builder_parent_1e6/stage_rows.csv`
- comparison_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_common_event_builder_parent_1e6/comparison_stage_ratios.csv`

## Boundary

- This is the common parent-history event definition only.
- It uses identical active-veto and analytic W2 response calculations for both codes.
- It does not yet perform 1 microsecond / 1 nanosecond sub-event splitting or side-Compton/FoV topology.
