# Phase-3 Cu-64 Mechanism Focus Audit

- status: `PHASE3_CU64_MECHANISM_FOCUS_AUDIT_PASS`
- histories_per_code: `FLUKA 1000000; MEGAlib 1000000`
- W2 raw: `FLUKA 1269; MEGAlib 1008`
- W2 active-veto: `FLUKA 662; MEGAlib 563`

## Mechanism Summary

The existing raw truth supports a geometry/raw-coupling mechanism, not a detector-response or time-grouping mechanism.
The excess is source-volume specific and changes sign by volume: `ColdPlate_MXC_50mK_SD_anchor` is FLUKA-high, while `Cu_SubstrateSupport_SolidDisk_L0_deepest` is MEGAlib-high.
The global source-to-TES distance distributions for W2 selected histories are similar, so the effect is not explained by a simple near/far distance scalar.
MEGAlib TES W2 rows carry mostly gamma `phot`/`compt` ancestry into local TES electron deposits; FLUKA exposes only local deposit proxies (`EM_BELOW_THRESHOLD`), so incident photon ancestry still needs a dedicated scorer.

## Source-To-TES Distance

| code | stage | events | median cm | p10 cm | p90 cm | shield touched | multi TES pixel |
|---|---|---:|---:|---:|---:|---:|---:|
| `fluka` | `raw` | `1269` | `5.5281` | `2.046` | `11.027` | `0.492` | `0.396` |
| `fluka` | `active_veto` | `662` | `5.6047` | `1.977` | `13.187` | `0.0257` | `0.378` |
| `megalib` | `raw` | `1008` | `5.8465` | `1.087` | `9.8954` | `0.451` | `0.38` |
| `megalib` | `active_veto` | `563` | `6.1179` | `1.1883` | `11.825` | `0.0178` | `0.393` |

## Largest Source-Volume Differences

| source volume | source histories | FLUKA W2 | MEGAlib W2 | diff | share of net | FLUKA/MEGAlib | FLUKA median cm | MEGAlib median cm |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `ColdPlate_MXC_50mK_SD_anchor` | `84445` | `438` | `227` | `+211` | `0.808` | `1.92952` | `4.5778` | `6.5659` |
| `Cu_SubstrateSupport_SolidDisk_L0_deepest` | `4708` | `74` | `164` | `-90` | `-0.345` | `0.45122` | `1.7269` | `1.2517` |
| `Cu_50mK_StillLike_Can_side_wall_above_side_port` | `26299` | `132` | `77` | `+55` | `0.211` | `1.71429` | `4.5668` | `7.1343` |
| `ColdPlate_CP_100mK_intercept` | `95876` | `88` | `42` | `+46` | `0.176` | `2.09524` | `9.4988` | `11.717` |
| `Cu_50mK_StillLike_Can_side_wall_rectcut_window_band` | `31280` | `150` | `107` | `+43` | `0.165` | `1.40187` | `5.8552` | `6.7262` |
| `ColdPlate_Still_0p7K` | `188826` | `47` | `22` | `+25` | `0.0958` | `2.13636` | `15.4` | `17.202` |
| `Cu_50mK_StillLike_Can_bottom_cap_2mm` | `26982` | `90` | `114` | `-24` | `-0.092` | `0.789474` | `6.6255` | `5.8193` |
| `DR_MixingChamber_Cu` | `14457` | `39` | `17` | `+22` | `0.0843` | `2.29412` | `5.7062` | `6.331` |
| `DR_Continuous_HEX_CuNi_MXC_to_CP` | `9197` | `30` | `12` | `+18` | `0.069` | `2.5` | `5.6878` | `9.2585` |
| `Cu_SubstrateSupport_OpenRing_L4_ZM_panel` | `277` | `2` | `16` | `-14` | `-0.0536` | `0.125` | `3.3827` | `2.9071` |

## Mechanism Interpretation

1. The W2 difference is generated before common response and before final FoV logic.
2. It is not a global source-boundary or source-to-TES-distance effect; the sign flips between nearby Cu structures.
3. The evidence points to local full-geometry coupling in specific Cu volumes: positron stopping/annihilation, photon escape paths through surrounding Cu/shield/Ta geometry, or runtime region/material assignment at those locations.
4. The photon concern is real: MEGAlib shows gamma ancestry feeding TES-local electrons. FLUKA's current raw dump records local deposit proxies only, so a TES-boundary/ancestry scorer is required to say which incident particles reach TES in FLUKA.

## Output Files

- distance_summary_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_mechanism_focus_audit_1e6/w2_source_to_tes_distance_summary.csv`
- source_volume_mechanism_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_mechanism_focus_audit_1e6/w2_source_volume_mechanism_summary.csv`
- source_volume_comparison_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_mechanism_focus_audit_1e6/w2_source_volume_mechanism_comparison.csv`
- local_carrier_ancestry_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_mechanism_focus_audit_1e6/w2_local_carrier_ancestry_summary.csv`
- selected_event_sample_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_mechanism_focus_audit_1e6/w2_selected_event_distance_sample.csv`

## Boundary

- This audit reuses existing independent-source raw truth under `/tmp/phase3prod`; it does not replay `.sim.gz`.
- It is a mechanism-focus post-processing audit, not a new FLUKA/Geant4 runtime scorer.
- FLUKA incident TES ancestry remains unmeasured by the existing raw schema.
