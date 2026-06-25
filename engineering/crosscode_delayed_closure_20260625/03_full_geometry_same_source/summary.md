# Phase-3 Cu-64 Common Positions

- status: `CU64_COMMON_POSITIONS_COMPLETE`
- rows: `6927`
- total_activity_weight_Bq: `4.7019049431490107524463624743795999999999999999999999999999999999999999999999523`
- source_csv: `/home/ubuntu/TES_511_Balloon/engineering/delayed_source_authority_v2_20260624/04_custom_source_v2/delayed_position_weights_v2.csv`
- output_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/cu64_common_positions.csv`
- volume_summary_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/cu64_common_position_volume_summary.csv`
- source_region_material_name_audit: `SOURCE_REGION_MATERIAL_NAME_AUDIT_PASS`
- source_coordinate_containment_audit: `SOURCE_COORDINATE_CONTAINMENT_STATIC_PASS`
- parent_resampling_authority: `CU64_PARENT_RESAMPLING_AUTHORITY_COMPLETE`

## Production Tags

| production_tag | rows | activity_weight_Bq |
|---|---:|---:|
| `muminus` | `1` | `0.0006753252346540412812810649609` |
| `n` | `6918` | `4.6958012556875166061534138233229999999999999999999999999999999999999999999999523` |
| `p` | `8` | `0.0054283622268401050116675860957` |

## Boundary

- `cu64_common_positions.csv` is the source-position authority; its `source_material` column remains intentionally `PENDING_REGION_AUDIT`.
- The separate name-level audit maps all `6927` rows to translated FLUKA region/material names: `Copper` `93.749%` activity and `CuNi` `6.251%`.
- The separate static coordinate audit inverse-rotates source-v2 coordinates by `InstrumentFrame.Rotation 0 45 0` and verifies `6927/6927` rows are inside their declared source volume as the deepest translated object.
- The separate parent-resampling authority draws `1,000,000` deterministic Cu-64 parent histories; all `6927` source rows are represented, and the full selected-index list is local/ignored with SHA256 `a2b5dbb883e49e16154290c0275561f41a6799f3753f4396262ad07f291a3975`.
- Runtime Geant4/FLUKA point-location has not been tested by these static artifacts.
- Full FLUKA/MEGAlib transport has not yet been run from the resampled parent list.
- `sampling_probability` is normalized over Cu-64 rows only and is suitable for deterministic Cu-64 parent resampling.
