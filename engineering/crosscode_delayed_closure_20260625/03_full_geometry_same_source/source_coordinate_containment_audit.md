# Phase-3 Cu-64 Source Coordinate Containment Audit

- status: `SOURCE_COORDINATE_CONTAINMENT_STATIC_PASS`
- rows: `6927`
- pass_static_containment_rows: `6927`
- failing_rows: `0`
- runtime_point_location_tested: `False`
- coordinate_transform_policy: `source-v2 coordinates are inverse-rotated by InstrumentFrame.Rotation 0 45 0 into the MEGAlib/FLUKA-translator local frame before static containment`
- audit_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/cu64_source_coordinate_containment_audit.csv`

## Status Summary

| audit_status | rows | activity_weight_Bq | activity_fraction |
|---|---:|---:|---:|
| `PASS_STATIC_CONTAINMENT` | `6927` | `4.7019049431490107524463624743795999999999999999999999999999999999999999999999523` | `1` |

## Boundary

- This is a static containment audit using the same MEGAlib geometry authority parsed by the FLUKA translator.
- It checks whether each common Cu-64 coordinate is inside its declared source volume and whether that volume is the deepest translated object containing the point.
- It is not a FLUKA runtime point-location scorer and does not replace a future engine-level locator check.
