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
- raw_production_1e6: `PHASE3_CU64_COMMON_RAW_PRODUCTION_PASS`
- parent_history_event_builder: `PHASE3_CU64_COMMON_PARENT_EVENT_BUILDER_PASS`
- raw_coupling_decomposition: `PHASE3_CU64_RAW_COUPLING_DECOMPOSITION_PASS`
- boundary_margin_audit: `PHASE3_CU64_BOUNDARY_MARGIN_AUDIT_PASS`
- time_topology_event_builder: `PHASE3_CU64_COMMON_TIME_TOPOLOGY_BUILDER_PASS`

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
- MEGAlib HTsim semantics are calibrated: HTsim first field is detector type, not `.det` detector id. Comparable MEGAlib TES/W2 counts now use `CC HIT` volume-deposit truth.
- Production-statistics FLUKA/MEGAlib transport has now run for the shared `1,000,000`-parent Cu-64 stream. Full raw truth is retained locally under `/tmp/phase3prod`; committed outputs are bounded summaries only.
- The common parent-history builder applies identical active-veto and analytic W2 response calculations to both codes.
- The common time/topology builder now also applies 1 microsecond and 1 nanosecond clustering plus TES/active-shield channel bookkeeping. It does not implement the final side-Compton/FoV reconstruction cut.
- The raw-coupling decomposition shows the W2 difference is distributed across source volumes/materials and is not isolated to `CuNi` or a non-neutron production tag.
- The static boundary-margin audit shows the net W2 raw excess is not dominated by source positions with margin `< 0.01 cm`.
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
| all TES > 0 | `3 / 1000` | `0.003` |
| 480-550 keV | `1 / 1000` | `0.001` |
| W2 510.58-511.42 keV | `1 / 1000` | `0.001` |
| 1500-3000 keV | `0 / 1000` | `0.0` |
| 3000-10000 keV | `0 / 1000` | `0.0` |

`CC HIT` TES particle/ancestry summary:

| TES local secondary | parent | creator/step process | histories | hit_rows | deposit_keV_sum |
|---|---|---|---:|---:|---:|
| `e-` | `gamma` | `phot -> eIoni` | `2` | `5` | `605.294` |
| `e-` | `gamma` | `compt -> eIoni` | `1` | `1` | `76.360` |
| `gamma` | `gamma` | `phot -> phot` | `2` | `2` | `23.312` |
| `gamma` | `e+` | `annihil -> phot` | `2` | `2` | `22.326` |
| `gamma` | `e+` | `annihil -> compt` | `1` | `1` | `0.0419` |

Boundary: this is a MEGAlib-only smoke-statistics raw-deposit plumbing result.
It proves the same independent parent stream can drive Cosima and be parsed
without replay. It also calibrates the HTsim ambiguity: native HTsim type `4`
means `Scintillator`, not `.det` detector `D4`. The comparable smoke counts are
FLUKA `5/1000` any-TES and `2/1000` W2 versus MEGAlib `3/1000` any-TES and
`1/1000` W2, too small for an efficiency conclusion.

## Production Raw-Deposit Gate

Artifact:

```text
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_common_raw_production_1e6/summary.md
```

| band | FLUKA events / histories | MEGAlib events / histories | FLUKA/MEGAlib | z |
|---|---:|---:|---:|---:|
| all TES > 0 | `6566 / 1000000` | `2797 / 1000000` | `2.34752` | `39.1` |
| 480-550 keV | `1470 / 1000000` | `1072 / 1000000` | `1.37127` | `7.9` |
| W2 510.58-511.42 keV | `1269 / 1000000` | `1008 / 1000000` | `1.25893` | `5.47` |
| 1500-3000 keV | `1 / 1000000` | `0 / 1000000` | `n/a` | `1` |
| 3000-10000 keV | `0 / 1000000` | `0 / 1000000` | `n/a` | `n/a` |

Boundary: this is a full-geometry raw-deposit production-statistics comparison
for the common Cu-64 parent stream. It is not a `.sim.gz` replay. The raw truth
is local/ignored; committed files are the chunk manifest and band summaries.

## Parent-History Event Builder

Artifact:

```text
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_common_event_builder_parent_1e6/summary.md
```

| metric | stage | FLUKA sum_w / histories | MEGAlib sum_w / histories | FLUKA/MEGAlib | z |
|---|---|---:|---:|---:|---:|
| W2 exact window | raw | `1269 / 1000000` | `1008 / 1000000` | `1.25893` | `5.47` |
| W2 analytic Gaussian expectation | raw | `1265.99 / 1000000` | `1005.19 / 1000000` | `1.25946` | `5.48` |
| W2 exact window | active-veto | `662 / 1000000` | `563 / 1000000` | `1.17584` | `2.83` |
| W2 analytic Gaussian expectation | active-veto | `660.692 / 1000000` | `561.302 / 1000000` | `1.17707` | `2.85` |

Interpretation: the common parent-history event builder and analytic W2 response
do not remove the discrepancy. The first failed phase is full-geometry
raw-deposit/source-material coupling, before common detector response.

## Common Time/Topology Event Builder

Artifact:

```text
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_common_event_builder_time_topology_1e6/summary.md
```

W2 focus comparison:

| event definition | stage | FLUKA W2 / histories | MEGAlib W2 / histories | FLUKA/MEGAlib | z |
|---|---|---:|---:|---:|---:|
| parent | raw | `1269 / 1000000` | `1008 / 1000000` | `1.25893` | `5.47` |
| parent | active-veto | `662 / 1000000` | `563 / 1000000` | `1.17584` | `2.83` |
| within 1 us | raw | `1269 / 1000000` | `1008 / 1000000` | `1.25893` | `5.47` |
| within 1 us | active-veto | `662 / 1000000` | `563 / 1000000` | `1.17584` | `2.83` |
| within 1 ns | raw | `1269 / 1000000` | `1008 / 1000000` | `1.25893` | `5.47` |
| within 1 ns | active-veto | `662 / 1000000` | `568 / 1000000` | `1.16549` | `2.68` |

Interpretation: parent-history and 1 microsecond clustering are identical for
this W2 observable. The 1 nanosecond split affects only a small MEGAlib
active-veto tail (`563` to `568`) and does not remove the raw W2 excess. The
builder also reports single/multi TES-pixel and active-shield-touch topology;
final side-Compton/FoV reconstruction remains open.

## Raw-Coupling Decomposition

Artifact:

```text
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_raw_coupling_decomposition_1e6/summary.md
```

Top W2 raw source-volume contributors:

| source volume | FLUKA W2 | MEGAlib W2 | diff / parent | share of total diff | conditional FLUKA/MEGAlib |
|---|---:|---:|---:|---:|---:|
| `ColdPlate_MXC_50mK_SD_anchor` | `438` | `227` | `+0.000211` | `0.808` | `1.9295` |
| `Cu_SubstrateSupport_SolidDisk_L0_deepest` | `74` | `164` | `-0.000090` | `-0.345` | `0.4512` |
| `Cu_50mK_StillLike_Can_side_wall_above_side_port` | `132` | `77` | `+0.000055` | `0.211` | `1.7143` |
| `ColdPlate_CP_100mK_intercept` | `88` | `42` | `+0.000046` | `0.176` | `2.0952` |
| `Cu_50mK_StillLike_Can_side_wall_rectcut_window_band` | `150` | `107` | `+0.000043` | `0.165` | `1.4019` |

Rollup:

| dimension | key | FLUKA W2 | MEGAlib W2 | diff / parent | share of total diff |
|---|---|---:|---:|---:|---:|
| material | `Copper` | `1210` | `989` | `+0.000221` | `0.847` |
| material | `CuNi` | `59` | `19` | `+0.000040` | `0.153` |
| production tag | `n` | `1267` | `1002` | `+0.000265` | `1.015` |
| production tag | `p` | `2` | `6` | `-0.000004` | `-0.015` |

Interpretation: the raw W2 excess is a distributed full-geometry coupling
difference. It is not explained by a single CuNi source class or by non-neutron
production. Several source volumes pull in opposite directions, so the next
discriminator is a more physical raw-coupling audit: runtime point location,
boundary-near behavior, positron stopping/annihilation location, and incident
TES ancestry.

## Static Boundary-Margin Audit

Artifact:

```text
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_boundary_margin_audit_1e6/summary.md
```

W2 raw by static source-boundary margin:

| margin bin | FLUKA W2 | MEGAlib W2 | diff / parent | share of total diff |
|---|---:|---:|---:|---:|
| `< 1e-4 cm` | `5` | `2` | `+0.000003` | `0.0115` |
| `1e-4-1e-3 cm` | `0` | `2` | `-0.000002` | `-0.0077` |
| `1e-3-1e-2 cm` | `89` | `56` | `+0.000033` | `0.126` |
| `1e-2-5e-2 cm` | `377` | `351` | `+0.000026` | `0.0996` |
| `5e-2-1e-1 cm` | `370` | `316` | `+0.000054` | `0.207` |
| `1e-1-5e-1 cm` | `422` | `278` | `+0.000144` | `0.552` |
| `>= 5e-1 cm` | `6` | `3` | `+0.000003` | `0.0115` |

Interpretation: static margins `< 0.01 cm` contribute only `0.13` of the net
W2 raw difference. A pure static boundary-proximity explanation is therefore
weak, but this does not replace runtime point-location, stopping/annihilation,
or incident-ancestry audits.
