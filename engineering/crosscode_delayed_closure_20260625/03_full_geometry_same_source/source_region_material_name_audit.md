# Phase-3 Cu-64 Source Region/Material Name Audit

- status: `SOURCE_REGION_MATERIAL_NAME_AUDIT_PASS`
- rows: `6927`
- pass_name_level_rows: `6927`
- missing_region_map_rows: `0`
- coordinate_containment_tested: `False`
- audit_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/cu64_source_region_material_name_audit.csv`

## Material Summary

| material | rows | activity_weight_Bq | activity_fraction |
|---|---:|---:|---:|
| `Copper` | `6494` | `4.4079931270587108550100473276045999999999999999999999999999999999999999999999526` | `0.93749090642112001319389791948369939349258776105825776093556586215641067691740606` |
| `CuNi` | `433` | `0.29391181609029989743631514677500000000000000000000000000000000000000000000000003` | `0.062509093578879986806102080516300606507412238941742239064434137843589323082593945` |

## Boundary

- This audit checks source-volume name mapping against the FLUKA translation `region_map.csv`.
- It does not test coordinate containment, nearest-boundary distance, or runtime Geant4/FLUKA point location.
- A later coordinate-level audit must still resolve each point in both engines before high-stat full transport.
