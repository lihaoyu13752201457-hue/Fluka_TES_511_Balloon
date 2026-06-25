# Delayed Cross-Code Closure Status

Date: 2026-06-25

## Current Decision

The FLUKA delayed-source identity gate passes. The dummy production card
`HI-PROPE 53 128` is not the observed source identity for the checked delayed
histories; the source routine overrides it with source-v2 Z/A/isomer before
`set_primary`.

This removes one plausible bookkeeping failure from the delayed discrepancy:
the FLUKA delayed result is not high because all delayed parents were silently
run as dummy I-128.

The FLUKA-side vacuum decay-kernel production gate passes for `Cu-64`,
`Na-24`, `Al-28`, and `I-128` at `1000000` parents per isotope. The
Geant4/MEGAlib independent EventList vacuum decay-kernel smoke also passes for
the same isotope set at `20000` parents per isotope. Both installed decay
engines emit the expected high-energy `Na-24` and `Al-28` gamma lines; the
high-energy delayed deficit is therefore not explained by a total absence of
those decay photons in either decay kernel.

The first Phase-2 common-source bookkeeping gate also passes. FLUKA and
MEGAlib both start the same explicit photon/positron primary table (`2048`
rows) with closed count, particle-code, kinetic-energy, direction, and weight
bookkeeping. This removes source-adapter resampling/unit drift from the T0
layer, but it does not yet test Cu/Ta transport or W2/TES deposition
efficiency.

The first T1 Cu-sphere transport smoke is complete. The same `2048` common
primary rows were transported through a homogeneous 1 cm radius Cu sphere in
both engines. For the 511-related rows, escaped W2-photon yields agree at smoke
statistics: Cu-64 positron rows FLUKA/MEGAlib `0.972`, mono-511 rows `0.943`,
and pair-511 rows `0.897` with the largest approximate z-score `1.21 sigma`.
The first T2 Cu+Ta absorber transport smoke is also complete. The common source
is propagated through a 1 cm radius Cu sphere plus a deliberately enlarged Ta
slab (`4.0 x 4.0 x 0.1 cm` at `z=3.0 cm`) and scored as deposited energy in Ta.
For the 511-like deposited-energy window, Cu-64 positron rows give FLUKA
`9/512` versus MEGAlib `4/512` (`2.25x`, `1.39 sigma`), mono-511 rows give
`1/512` versus `1/512`, and pair-511 rows give `3/512` versus `2/512`. This
proves the shared-source T2 machinery reaches the Ta deposited-energy observable
in both engines, but it is not final Phase-2 closure because statistics, exact
Ta/TES dimensions, ancestry/stopping observables, and deterministic W2 response
are still open.

The generated-source T2 production-statistics gate is now complete. It uses the
same Cu+Ta toy geometry with `100000` Cu-64 positron rows, `100000` mono-511
photon rows, and `100000` pair-511 photon rows. The W2 Ta deposited-energy
efficiency agrees in the 511-related channels: Cu-64 positron rows give
FLUKA/MEGAlib `1.029` (`1132` versus `1100`, `0.68 sigma`), mono-511 rows
`0.986`, and pair-511 rows `1.007`. This rules out the low-statistics T2 smoke
central value (`2.25x`) as a stable production result and removes a simple
common-source Cu+Ta W2 EM-transport/deposition mismatch as the explanation for
the full-chain delayed W2 excess.

The Phase-3 Cu-64 common source-position authority is built. It contains `6927`
source-v2 Cu-64 positions with `Z=29`, `A=64`, `isomer=0` and total Cu-64
activity weight `4.701904943 Bq`. The source is dominated by neutron production
(`6918` rows, `4.6958012557 Bq`). The position file keeps
`source_material=PENDING_REGION_AUDIT`, but the follow-on name-level material
audit and static coordinate-containment audit now pass: all rows map to
translated FLUKA regions/materials and all rows are inside their declared source
volume after applying the explicit `InstrumentFrame.Rotation 0 45 0` inverse
transform. A deterministic `1000000`-history Cu-64 parent resampling authority
is also built and covers all `6927` source rows at least once. Full transport
and raw-deposit truth remain open.

## Evidence

Manifest:

```text
engineering/crosscode_delayed_closure_20260625/00_manifest/summary.md
```

Runtime gate:

```text
engineering/crosscode_delayed_closure_20260625/00_manifest/fluka_source_identity_gate/summary.md
engineering/crosscode_delayed_closure_20260625/00_manifest/fluka_source_identity_gate/runtime_identity_validation.csv
```

FLUKA decay-kernel smoke:

```text
engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/fluka_vacuum_smoke/summary.md
engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/fluka_vacuum_smoke/gamma_line_yields.csv
engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/fluka_vacuum_smoke/particle_yields.csv
```

FLUKA decay-kernel production:

```text
engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/fluka_vacuum_production/summary.md
engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/fluka_vacuum_production/gamma_line_yields.csv
engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/fluka_vacuum_production/particle_yields.csv
```

Geant4/MEGAlib decay-kernel smoke:

```text
engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/geant4_megalib_vacuum_smoke/summary.md
engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/geant4_megalib_vacuum_smoke/gamma_line_yields.csv
engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/geant4_megalib_vacuum_smoke/particle_yields.csv
```

Cross-code line comparison:

```text
engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/crosscode_decay_kernel_line_comparison.csv
```

Phase-2 T0 common-source bookkeeping:

```text
engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t0_source_bookkeeping_smoke/summary.md
engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t0_source_bookkeeping_smoke/closure_comparison.csv
engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t0_source_bookkeeping_smoke/common_primaries.csv
```

Phase-2 T1 Cu-sphere transport smoke:

```text
engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t1_cu_sphere_transport_smoke/summary.md
engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t1_cu_sphere_transport_smoke/family_escape_summary.csv
engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t1_cu_sphere_transport_smoke/escape_yield_comparison.csv
```

Phase-2 T2 Cu+Ta absorber transport smoke:

```text
engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t2_cu_ta_absorber_transport_smoke/summary.md
engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t2_cu_ta_absorber_transport_smoke/family_ta_deposit_summary.csv
engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t2_cu_ta_absorber_transport_smoke/ta_deposit_efficiency_comparison.csv
```

Phase-2 T2 Cu+Ta absorber production-statistics gate:

```text
engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t2_cu_ta_absorber_transport_production_100k/summary.md
engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t2_cu_ta_absorber_transport_production_100k/family_ta_deposit_summary.csv
engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t2_cu_ta_absorber_transport_production_100k/ta_deposit_efficiency_comparison.csv
```

Phase-3 Cu-64 common source-position authority:

```text
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/summary.md
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/cu64_common_positions.csv
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/cu64_common_position_volume_summary.csv
```

Phase-3 Cu-64 source-region/material name audit:

```text
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/source_region_material_name_audit.md
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/source_region_material_name_audit.json
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/cu64_source_region_material_name_audit.csv
```

Phase-3 Cu-64 static coordinate-containment audit:

```text
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/source_coordinate_containment_audit.md
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/source_coordinate_containment_audit.json
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/cu64_source_coordinate_containment_audit.csv
```

Phase-3 Cu-64 parent resampling authority:

```text
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/cu64_parent_resampling_summary.md
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/cu64_parent_resampling_summary.json
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/cu64_parent_resampling_sample.csv
```

Runtime identity result:

| nuclide | event_id | expected Z/A/isomer | FLUKA runtime Z/A/isomer | result |
|---|---:|---:|---:|---|
| Cu-64 | 153 | 29/64/0 | 29/64/0 | PASS |
| Cu-62 | 7 | 29/62/0 | 29/62/0 | PASS |
| I-128 | 16 | 53/128/0 | 53/128/0 | PASS |
| Na-22 | 62 | 11/22/0 | 11/22/0 | PASS |
| Na-24 | 72 | 11/24/0 | 11/24/0 | PASS |
| Al-28 | 65 | 13/28/0 | 13/28/0 | PASS |

FLUKA decay-kernel production line result:

| nuclide | line / channel | yield or fraction |
|---|---|---:|
| Cu-64 | positron yield / parent | `0.176483` |
| Cu-64 | 1346-keV gamma yield / parent | `0.004785` |
| Na-24 | 1369-keV gamma yield / parent | `0.999939` |
| Na-24 | 2754-keV gamma yield / parent | `0.998547` |
| Na-24 | same-parent 1369+2754 coincidence | `0.998547` |
| Al-28 | 1779-keV gamma yield / parent | `1.0` |
| I-128 | photon yield / parent | `0.199216` |

Geant4/MEGAlib decay-kernel smoke line result:

| nuclide | line / channel | yield or fraction |
|---|---|---:|
| Cu-64 | positron yield / parent | `0.1767` |
| Cu-64 | 1346-keV gamma yield / parent | `0.0043` |
| Na-24 | 1369-keV gamma yield / parent | `0.99995` |
| Na-24 | 2754-keV gamma yield / parent | `0.9988` |
| Na-24 | same-parent 1369+2754 coincidence | `0.9988` |
| Al-28 | 1779-keV gamma yield / parent | `1.0` |
| I-128 | photon yield / parent | `0.20605` |

Phase-2 T0 source-bookkeeping result:

| code | observed / expected | max energy relative delta | max direction 1-dot | status |
|---|---:|---:|---:|---|
| FLUKA | `2048 / 2048` | `4.1880789907739405e-09` | `1.1102230246251565e-16` | PASS |
| MEGAlib | `2048 / 2048` | `5.2968580495807746e-05` | `3.354161393076538e-11` | PASS |

Phase-2 T1 Cu-sphere escaped-photon smoke:

| family | metric | FLUKA | MEGAlib | FLUKA/MEGAlib | z approx |
|---|---|---:|---:|---:|---:|
| `cu64_eplus_smoke` | escaped W2 photon yield | `0.957031` | `0.984375` | `0.972222` | `-0.44` |
| `mono511_gamma` | escaped W2 photon yield | `0.451172` | `0.478516` | `0.942857` | `-0.64` |
| `pair511_gamma` | escaped W2 photon yield | `0.460938` | `0.513672` | `0.897338` | `-1.21` |
| `mono1779_gamma` | total escaped photon yield | `0.984375` | `0.984375` | `1.0` | `0.00` |
| `mono2754_gamma` | total escaped photon yield | `0.992188` | `1.039062` | `0.954887` | `-0.53` |

Phase-2 T2 Cu+Ta deposited-energy smoke:

| family | metric | FLUKA | MEGAlib | FLUKA/MEGAlib | z approx |
|---|---|---:|---:|---:|---:|
| `cu64_eplus_smoke` | Ta deposit efficiency, W2 510.58-511.42 keV | `0.017578` | `0.007812` | `2.25` | `1.39` |
| `cu64_eplus_smoke` | Ta deposit efficiency, 480-550 keV | `0.019531` | `0.007812` | `2.50` | `1.60` |
| `mono511_gamma` | Ta deposit efficiency, W2 510.58-511.42 keV | `0.001953` | `0.001953` | `1.00` | `0.00` |
| `pair511_gamma` | Ta deposit efficiency, W2 510.58-511.42 keV | `0.005859` | `0.003906` | `1.50` | `0.45` |
| `mono1779_gamma` | Ta deposit efficiency, 480-550 keV | `0.003906` | `0` | `n/a` | `1.00` |
| `mono2754_gamma` | Ta deposit efficiency, all nonzero | `0.011719` | `0.023438` | `0.50` | `-1.00` |

Phase-2 T2 Cu+Ta deposited-energy production-statistics gate:

| family | metric | FLUKA | MEGAlib | FLUKA/MEGAlib | z approx |
|---|---|---:|---:|---:|---:|
| `cu64_eplus_smoke` | Ta deposit efficiency, W2 510.58-511.42 keV | `0.01132` | `0.01100` | `1.02909` | `0.68` |
| `cu64_eplus_smoke` | Ta deposit efficiency, 480-550 keV | `0.01232` | `0.01212` | `1.01650` | `0.40` |
| `mono511_gamma` | Ta deposit efficiency, W2 510.58-511.42 keV | `0.00551` | `0.00559` | `0.98569` | `-0.24` |
| `pair511_gamma` | Ta deposit efficiency, W2 510.58-511.42 keV | `0.00545` | `0.00541` | `1.00739` | `0.12` |

Phase-3 Cu-64 common positions:

| quantity | value |
|---|---:|
| rows | `6927` |
| total Cu-64 activity weight | `4.7019049431490107524463624743796 Bq` |
| neutron-produced rows / activity | `6918 / 4.695801255687516606153413823323 Bq` |
| proton-produced rows / activity | `8 / 0.0054283622268401050116675860957 Bq` |
| mu-minus-produced rows / activity | `1 / 0.0006753252346540412812810649609 Bq` |

Phase-3 Cu-64 source-region/material name audit:

| quantity | value |
|---|---:|
| audit status | `SOURCE_REGION_MATERIAL_NAME_AUDIT_PASS` |
| name-level pass rows | `6927 / 6927` |
| missing region-map rows | `0` |
| not-translated rows | `0` |
| `Copper` activity share | `93.749%` |
| `CuNi` activity share | `6.251%` |
| coordinate containment tested | `False` |

Phase-3 Cu-64 static coordinate-containment audit:

| quantity | value |
|---|---:|
| audit status | `SOURCE_COORDINATE_CONTAINMENT_STATIC_PASS` |
| static containment pass rows | `6927 / 6927` |
| failing rows | `0` |
| coordinate transform | inverse `InstrumentFrame.Rotation 0 45 0` |
| deepest `Copper` activity share | `93.749%` |
| deepest `CuNi` activity share | `6.251%` |
| minimum approximate source-boundary margin | `2.325151502e-05 cm` |
| runtime point location tested | `False` |

Phase-3 Cu-64 parent resampling authority:

| quantity | value |
|---|---:|
| audit status | `CU64_PARENT_RESAMPLING_AUTHORITY_COMPLETE` |
| histories | `1000000` |
| selected unique source rows | `6927 / 6927` |
| seed | `20260625_phase3_cu64` |
| selection stream SHA256 | `3be6695480c8b130ea9a396cbe34efdc47e97be4aa3575bcf4b2968be147a98e` |
| full local list SHA256 | `a2b5dbb883e49e16154290c0275561f41a6799f3753f4396262ad07f291a3975` |
| selected `Copper` histories | `937427` |
| selected `CuNi` histories | `62573` |
| transport run performed | `False` |

## What This Does Not Prove

This does not close the Geant4/MEGAlib versus FLUKA delayed discrepancy. It
verifies FLUKA source identity for representative source-v2 parents and gives
a smoke-statistics cross-code decay-emission sanity check. The T0 source gate
only verifies common source bookkeeping; it does not compare positron slowing,
annihilation, photon escape, material coupling, or TES deposited energy. The
T1 smoke adds escaped-particle evidence in a Cu sphere. The T2 smoke adds a
first shared Ta deposited-energy observable, but with intentionally enlarged
absorber dimensions and low event counts. The T2 production-statistics toy gate
passes W2/broad deposited-energy efficiency for generated 511-related sources,
but it still lacks exact full-geometry Ta/TES dimensions, runtime engine point
location, ancestry/stopping truth, and the final analytic W2 response. The
Phase-3 position file, name-level audit, static coordinate-containment audit,
and deterministic 1e6-parent resampling authority now show that the common
Cu-64 coordinates and parent stream are internally consistent with the
translated geometry authority after the explicit InstrumentFrame transform.
They do not yet replace a FLUKA or Geant4 runtime point-location scorer or a
full transport raw-deposit run.

Open discriminators:

1. Geant4/MEGAlib production-statistics decay-kernel run if low-yield-line precision is needed.
2. Runtime point-location audit for the built Cu-64 common positions if required before production transport.
3. Full-geometry raw deposits for the common Cu-64 parents.
4. Common external event builder and deterministic analytic W2 response.
5. Common ancestry/stopping observables for positron slowing, annihilation photons, and photon-to-Ta deposition if full geometry reopens the discrepancy.
6. FLUKA EM-cut/material scan only if a later full-geometry or ancestry gate reopens a W2 EM-transport discrepancy.

## Working Hypothesis After This Gate

The leading explanation is no longer "one decay engine completely fails to
emit the `Na-24`/`Al-28` high-energy gamma lines." Both FLUKA production and
Geant4/MEGAlib smoke emit those lines in the vacuum decay-kernel scorer. The
most decisive existing unresolved signal remains the full-chain high-energy
delayed deficit:

| final delayed band | FLUKA/G4 rate ratio |
|---|---:|
| W2 511 | 2.64 |
| 1500-3000 keV | 0.041 |
| 3000-10000 keV | 0.014 |

The next run should therefore use the built Cu-64 common positions for
full-geometry raw-deposit truth, with a runtime point-location scorer inserted
first if the engine-level locator is required as a hard gate. The toy T2 W2
result no longer justifies an immediate FLUKA EM-cut scan for the 511-related
deposited-energy gate.
