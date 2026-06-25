# Phase-3 Cu-64 Boundary-Margin Audit

- status: `PHASE3_CU64_BOUNDARY_MARGIN_AUDIT_PASS`
- histories_per_code: `FLUKA 1000000; MEGAlib 1000000`
- coordinate_audit: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/cu64_source_coordinate_containment_audit.csv`

## Headline

The W2 raw FLUKA excess is not dominated by very near-boundary source positions: positions with static margin < 0.01 cm contribute 0.13 of the net W2 difference. This weakens a pure boundary-proximity explanation, though runtime point-location and stopping/annihilation audits remain open.

## W2 Raw By Static Boundary-Margin Bin

| margin bin | source histories | FLUKA W2 | MEGAlib W2 | diff / parent | share of total diff | FLUKA/MEGAlib conditional |
|---|---:|---:|---:|---:|---:|---:|
| `lt_1e-4_cm` | `298` | `5` | `2` | `3e-06` | `0.0115` | `2.5` |
| `1e-4_1e-3_cm` | `3627` | `0` | `2` | `-2e-06` | `-0.00766` | `0` |
| `1e-3_1e-2_cm` | `56235` | `89` | `56` | `3.3e-05` | `0.126` | `1.58929` |
| `1e-2_5e-2_cm` | `218430` | `377` | `351` | `2.6e-05` | `0.0996` | `1.07407` |
| `5e-2_1e-1_cm` | `225167` | `370` | `316` | `5.4e-05` | `0.207` | `1.17089` |
| `1e-1_5e-1_cm` | `487576` | `422` | `278` | `0.000144` | `0.552` | `1.51799` |
| `ge_5e-1_cm` | `8667` | `6` | `3` | `3e-06` | `0.0115` | `2` |

## W2 Raw Margin Distribution

| code | events | min cm | p10 cm | median cm | p90 cm | events < 0.01 cm |
|---|---:|---:|---:|---:|---:|---:|
| `fluka` | `1269` | `2.97471e-05` | `0.0137684` | `0.0717751` | `0.246298` | `94` |
| `megalib` | `1008` | `2.97471e-05` | `0.0135722` | `0.0629481` | `0.208875` | `60` |

## Output Files

- margin_bin_comparison_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_boundary_margin_audit_1e6/margin_bin_comparison.csv`
- selected_margin_summary_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_boundary_margin_audit_1e6/selected_margin_summary.csv`
- nearest_w2_raw_events_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_boundary_margin_audit_1e6/nearest_w2_raw_events.csv`

## Boundary

- This is a static translator boundary-margin audit, not a runtime Geant4/FLUKA point-location scorer.
- It tests whether the observed W2 raw difference is dominated by source positions very near declared source-volume boundaries.
