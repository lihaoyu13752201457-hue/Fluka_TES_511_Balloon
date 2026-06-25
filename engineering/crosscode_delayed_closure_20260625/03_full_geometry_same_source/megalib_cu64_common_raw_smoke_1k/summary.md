# Phase-3 Cu-64 Common MEGAlib Raw-Hit Run

- status: `PHASE3_CU64_COMMON_MEGALIB_RAW_PASS`
- source_mode: `phase3_cu64_common_parent_resampling`
- stop_condition: `Events`
- pre_trigger_mode: `Everything`
- no `.sim.gz` replay: `True`
- histories: `1000`
- sim_event_count: `1000`
- raw_schema: `CC HIT volume energy deposits`
- cc_hit_rows: `6477`
- cc_tes_hit_rows: `11`
- htsim_hit_rows: `1352`
- htsim_first_field: `MEGAlib detector type, not .det detector instance id`
- run_products_retained: `False`
- elapsed_s: `3.809`
- cc_band_summary_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/megalib_cu64_common_raw_smoke_1k/cc_band_summary.csv`
- cc_tes_hit_sample_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/megalib_cu64_common_raw_smoke_1k/cc_tes_hit_sample.csv`
- cc_tes_particle_summary_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/megalib_cu64_common_raw_smoke_1k/cc_tes_particle_summary.csv`

## CC HIT Volume-Truth Band Counts

| band | events / histories | efficiency_per_parent | top_material_counts |
|---|---:|---:|---|
| `all TES > 0` | `3 / 1000` | `0.003` | `{"Copper": 3}` |
| `480-550 keV` | `1 / 1000` | `0.001` | `{"Copper": 1}` |
| `W2 510.58-511.42 keV` | `1 / 1000` | `0.001` | `{"Copper": 1}` |
| `1500-3000 keV` | `0 / 1000` | `0` | `{}` |
| `3000-10000 keV` | `0 / 1000` | `0` | `{}` |

## CC HIT Volume Summary

| volume | region_kind | histories_with_hit | hit_rows | deposit_keV_sum |
|---|---|---:|---:|---:|
| `ColdPlate_4K` | `OTHER` | `406` | `1688` | `57448.7` |
| `ColdPlate_Still_0p7K` | `OTHER` | `218` | `1016` | `30981.8` |
| `ColdPlate_CP_100mK_intercept` | `OTHER` | `103` | `462` | `18353.8` |
| `ColdPlate_MXC_50mK_SD_anchor` | `OTHER` | `82` | `379` | `15070.6` |
| `DR_Still_Pot_Cu` | `OTHER` | `40` | `192` | `8411.38` |
| `Vacuum_Jacket_Al_266mmClass_side_port_side_wall_above_side_port` | `OTHER` | `38` | `179` | `5385.54` |
| `Passive_W_Bottom_Plate_detector_bay` | `OTHER` | `13` | `86` | `4372.83` |
| `DR_4K_Condenser_Cu` | `OTHER` | `23` | `92` | `4145.21` |
| `Cu_50mK_StillLike_Can_side_wall_rectcut_window_band` | `OTHER` | `33` | `148` | `4120.62` |
| `Cu_50mK_StillLike_Can_side_wall_above_side_port` | `OTHER` | `32` | `160` | `4063.46` |

## CC HIT TES Particle/Ancestry Summary

| secondary | parent | creator_process | step_process | histories_with_hit | hit_rows | deposit_keV_sum |
|---|---|---|---|---:|---:|---:|
| `e-` | `gamma` | `phot` | `eIoni` | `2` | `5` | `605.294` |
| `e-` | `gamma` | `compt` | `eIoni` | `1` | `1` | `76.3604` |
| `gamma` | `gamma` | `phot` | `phot` | `2` | `2` | `23.312` |
| `gamma` | `e+` | `annihil` | `phot` | `2` | `2` | `22.326` |
| `gamma` | `e+` | `annihil` | `compt` | `1` | `1` | `0.04189` |

## Native HTsim Detector-Type Summary

| detector_type | type_name | histories_with_hit | hit_rows | deposit_keV_sum |
|---:|---|---:|---:|---:|
| `4` | `Scintillator` | `1000` | `1349` | `212789` |
| `2` | `Calorimeter` | `3` | `3` | `727.334` |

## Boundary

- This is the MEGAlib side only.
- It validates full-geometry raw-hit plumbing for the Phase-3 common Cu-64 parent stream without `.sim.gz` replay.
- `CC HIT` comments provide the common volume-deposit schema for TES/W2 band counts.
- Native `HTsim` is retained only as a MEGAlib detector-type/readout summary; its first field is not a `.det` detector-instance id.
- Cosima `.sim.gz` run products are deleted by default after parsing.
- FLUKA production comparison, common event building, and production-statistics closure remain open.
