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

## What This Does Not Prove

This does not close the Geant4/MEGAlib versus FLUKA delayed discrepancy. It
verifies FLUKA source identity for representative source-v2 parents and gives
a smoke-statistics cross-code decay-emission sanity check. The T0 source gate
only verifies common source bookkeeping; it does not compare positron slowing,
annihilation, photon escape, material coupling, or TES deposited energy. The
T1 smoke adds escaped-particle evidence in a Cu sphere. The T2 smoke adds a
first shared Ta deposited-energy observable, but with intentionally enlarged
absorber dimensions and low event counts; it still lacks production statistics,
exact Ta/TES geometry, common ancestry/stopping truth, and the final analytic
W2 response.

Open discriminators:

1. Geant4/MEGAlib production-statistics decay-kernel run if low-yield-line precision is needed.
2. Production common T1/T2 raw-deposit transport through agreed Cu/Ta/TES toy geometries.
3. Common ancestry/stopping observables for positron slowing, annihilation photons, and photon-to-Ta deposition.
4. FLUKA EM-cut/material scan if the production T2 W2 deposited-energy efficiency remains high.
5. Common full-geometry source positions and common external postprocessor.

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

The next run should therefore promote T1 from smoke to common raw-deposit truth
and promote T2 from enlarged-absorber smoke to production Ta/TES W2-efficiency
transport with agreed dimensions and enough statistics. If that preserves a
large FLUKA excess in W2 deposited energy, the next most useful discriminator is
a FLUKA EM-cut/material scan before returning to full-geometry differences.
