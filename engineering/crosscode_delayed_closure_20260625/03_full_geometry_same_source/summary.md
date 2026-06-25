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
- fluka_common_raw_smoke: `PHASE3_CU64_COMMON_FLUKA_RAW_PASS`
- megalib_common_raw_smoke: `PHASE3_CU64_COMMON_MEGALIB_RAW_PASS`

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
- The FLUKA-side `1000`-history raw-deposit smoke runs directly from that parent list, without `.sim.gz` replay, and closes raw dump versus score output at `1.34e-10` TES relative delta and `2.28e-10` shield relative delta.
- The MEGAlib-side `1000`-event raw-hit smoke also runs directly from that parent list, without `.sim.gz` replay, using `Run.Events` and `PreTriggerMode Everything`.
- Runtime Geant4/FLUKA point-location has not been tested by these static artifacts.
- MEGAlib native HTsim detector/readout semantics are not yet calibrated to the FLUKA raw-deposit schema; production-statistics FLUKA/MEGAlib transport has not yet been run from the resampled parent list.
- `sampling_probability` is normalized over Cu-64 rows only and is suitable for deterministic Cu-64 parent resampling.

## FLUKA Raw-Deposit Smoke

Artifact:

```text
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/fluka_cu64_common_raw_smoke_1k/summary.md
```

| band | events / histories | efficiency |
|---|---:|---:|
| all TES > 0 | `5 / 1000` | `0.005` |
| 480-550 keV | `2 / 1000` | `0.002` |
| W2 510.58-511.42 keV | `2 / 1000` | `0.002` |
| 1500-3000 keV | `0 / 1000` | `0.0` |
| 3000-10000 keV | `0 / 1000` | `0.0` |

Boundary: this is a FLUKA-only plumbing smoke. It proves the common Cu-64 parent
stream can drive the full FLUKA geometry and raw-deposit scorer without replay,
and that raw dump/scoring energy closure is numerically tight. It is not a
MEGAlib comparison, common event-builder result, or production-statistics
delayed-W2 conclusion.

## MEGAlib Raw-Hit Smoke

Artifact:

```text
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/megalib_cu64_common_raw_smoke_1k/summary.md
```

| band | events / histories | efficiency |
|---|---:|---:|
| all TES > 0 | `1000 / 1000` | `1.0` |
| 480-550 keV | `12 / 1000` | `0.012` |
| W2 510.58-511.42 keV | `1 / 1000` | `0.001` |
| 1500-3000 keV | `1 / 1000` | `0.001` |
| 3000-10000 keV | `0 / 1000` | `0.0` |

Detector-hit summary:

| detector/readout | histories_with_hit | hit_rows | deposit_keV_sum |
|---|---:|---:|---:|
| `D4 / TES_L3` | `1000` | `1349` | `212788.603` |
| `D2 / TES_L1` | `3` | `3` | `727.334` |

Boundary: this is a MEGAlib-only runner/parser smoke. It proves the same
independent parent stream can drive Cosima and be parsed without replay, but
the native HTsim detector/readout semantics are not yet a FLUKA-equivalent
raw-deposit schema. Do not compare the MEGAlib `1000/1000` all-TES count
directly to the FLUKA `5/1000` raw-deposit count; detector/readout semantic
calibration or a common deposit-level scorer is required before interpreting
per-parent W2 efficiency.
