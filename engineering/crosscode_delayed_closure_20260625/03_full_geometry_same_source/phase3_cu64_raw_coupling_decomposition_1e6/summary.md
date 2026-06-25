# Phase-3 Cu-64 Raw-Coupling Decomposition

- status: `PHASE3_CU64_RAW_COUPLING_DECOMPOSITION_PASS`
- parent_list_sha256: `a2b5dbb883e49e16154290c0275561f41a6799f3753f4396262ad07f291a3975`
- work_root: `/tmp/phase3prod`
- histories_per_code: `FLUKA 1000000; MEGAlib 1000000`

## Headline

The W2 raw excess is distributed across multiple copper source volumes, with `ColdPlate_MXC_50mK_SD_anchor` and `Cu_50mK_StillLike_Can_side_wall_above_side_port` among the largest positive contributors; it is not isolated to CuNi or a non-neutron production tag.

## Top W2 Raw Source-Volume Contributors

| source_volume | source histories | FLUKA W2 | MEGAlib W2 | diff / parent | share of total diff | conditional FLUKA/MEGAlib |
|---|---:|---:|---:|---:|---:|---:|
| `ColdPlate_MXC_50mK_SD_anchor` | `84445` | `438` | `227` | `0.000211` | `0.808` | `1.92952` |
| `Cu_SubstrateSupport_SolidDisk_L0_deepest` | `4708` | `74` | `164` | `-9e-05` | `-0.345` | `0.45122` |
| `Cu_50mK_StillLike_Can_side_wall_above_side_port` | `26299` | `132` | `77` | `5.5e-05` | `0.211` | `1.71429` |
| `ColdPlate_CP_100mK_intercept` | `95876` | `88` | `42` | `4.6e-05` | `0.176` | `2.09524` |
| `Cu_50mK_StillLike_Can_side_wall_rectcut_window_band` | `31280` | `150` | `107` | `4.3e-05` | `0.165` | `1.40187` |
| `ColdPlate_Still_0p7K` | `188826` | `47` | `22` | `2.5e-05` | `0.0958` | `2.13636` |
| `Cu_50mK_StillLike_Can_bottom_cap_2mm` | `26982` | `90` | `114` | `-2.4e-05` | `-0.092` | `0.789474` |
| `DR_MixingChamber_Cu` | `14457` | `39` | `17` | `2.2e-05` | `0.0843` | `2.29412` |
| `DR_Continuous_HEX_CuNi_MXC_to_CP` | `9197` | `30` | `12` | `1.8e-05` | `0.069` | `2.5` |
| `Cu_SubstrateSupport_OpenRing_L4_ZM_panel` | `277` | `2` | `16` | `-1.4e-05` | `-0.0536` | `0.125` |

## Local TES Carrier Check

| code | metric | stage | carrier group | histories | hit rows | deposit keV |
|---|---|---|---|---:|---:|---:|
| `fluka` | `w2_510p58_511p42` | `raw` | `EM_BELOW_THRESHOLD` | `1269` | `1846` | `640735` |
| `fluka` | `w2_510p58_511p42` | `raw` | `ELECTRON` | `31` | `34` | `7722.64` |
| `megalib` | `w2_510p58_511p42` | `raw` | `e-|parent=gamma|creator=phot|step=eIoni` | `1008` | `3236` | `319499` |
| `megalib` | `w2_510p58_511p42` | `raw` | `e-|parent=gamma|creator=compt|step=eIoni` | `480` | `742` | `95191.1` |
| `megalib` | `w2_510p58_511p42` | `raw` | `e-|parent=gamma|creator=phot|step=msc` | `216` | `3646` | `33219.1` |
| `megalib` | `w2_510p58_511p42` | `raw` | `e-|parent=gamma|creator=phot|step=eBrem` | `231` | `268` | `23417.6` |
| `megalib` | `w2_510p58_511p42` | `raw` | `e-|parent=e-|creator=eIoni|step=eIoni` | `174` | `184` | `14222` |
| `megalib` | `w2_510p58_511p42` | `raw` | `gamma|parent=e+|creator=annihil|step=phot` | `1008` | `1008` | `8408.2` |
| `megalib` | `w2_510p58_511p42` | `raw` | `gamma|parent=gamma|creator=phot|step=phot` | `845` | `1216` | `7438.13` |
| `megalib` | `w2_510p58_511p42` | `raw` | `e-|parent=gamma|creator=compt|step=eBrem` | `58` | `64` | `5250.47` |
| `megalib` | `w2_510p58_511p42` | `raw` | `e-|parent=gamma|creator=compt|step=msc` | `46` | `729` | `4679.86` |
| `megalib` | `w2_510p58_511p42` | `raw` | `gamma|parent=e-|creator=eBrem|step=phot` | `284` | `332` | `1871.14` |
| `megalib` | `w2_510p58_511p42` | `raw` | `gamma|parent=e+|creator=annihil|step=compt` | `471` | `629` | `1066.09` |
| `megalib` | `w2_510p58_511p42` | `raw` | `e-|parent=e-|creator=eIoni|step=eBrem` | `8` | `8` | `316.035` |
| `megalib` | `w2_510p58_511p42` | `raw` | `gamma|parent=e-|creator=eIoni|step=phot` | `111` | `122` | `268.346` |
| `megalib` | `w2_510p58_511p42` | `raw` | `gamma|parent=gamma|creator=compt|step=phot` | `30` | `34` | `175.287` |

## Output Files

- dimension_comparison_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_raw_coupling_decomposition_1e6/dimension_comparison.csv`
- top_source_volume_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_raw_coupling_decomposition_1e6/top_source_volume_contributors.csv`
- local_carrier_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_raw_coupling_decomposition_1e6/local_tes_carrier_summary.csv`

## Boundary

- This decomposes the already-produced parent-history raw and active-veto totals.
- It does not add a runtime point-location scorer or a positron stopping/annihilation locator.
- FLUKA raw rows carry local particle code only; MEGAlib `CC HIT` rows carry richer TES ancestry.
