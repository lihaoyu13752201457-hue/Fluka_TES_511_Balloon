# Phase-3 Cu-64 Common Positions

- status: `CU64_COMMON_POSITIONS_COMPLETE`
- rows: `6927`
- total_activity_weight_Bq: `4.7019049431490107524463624743795999999999999999999999999999999999999999999999523`
- source_csv: `/home/ubuntu/TES_511_Balloon/engineering/delayed_source_authority_v2_20260624/04_custom_source_v2/delayed_position_weights_v2.csv`
- output_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/cu64_common_positions.csv`
- volume_summary_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/cu64_common_position_volume_summary.csv`

## Production Tags

| production_tag | rows | activity_weight_Bq |
|---|---:|---:|
| `muminus` | `1` | `0.0006753252346540412812810649609` |
| `n` | `6918` | `4.6958012556875166061534138233229999999999999999999999999999999999999999999999523` |
| `p` | `8` | `0.0054283622268401050116675860957` |

## Boundary

- This is a source-position authority only; it does not resolve final Geant4 logical volume or FLUKA region/material.
- `source_material` is intentionally `PENDING_REGION_AUDIT` and must be replaced by the Phase-3 region/material audit.
- `sampling_probability` is normalized over Cu-64 rows only and is suitable for deterministic Cu-64 parent resampling.
