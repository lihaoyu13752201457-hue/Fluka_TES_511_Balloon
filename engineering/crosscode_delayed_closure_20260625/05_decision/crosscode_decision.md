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

## What This Does Not Prove

This does not close the Geant4/MEGAlib versus FLUKA delayed discrepancy. It
verifies FLUKA source identity for representative source-v2 parents and gives
a smoke-statistics cross-code decay-emission sanity check.

Open discriminators:

1. Geant4/MEGAlib production-statistics decay-kernel run if low-yield-line precision is needed.
2. Common emitted-particle list through a common toy geometry.
3. Common full-geometry source positions and common external postprocessor.

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

The next run should therefore move to common emitted-particle transport, unless
we first want a Geant4/MEGAlib production-statistics repeat to sharpen
low-yield channels such as the `Cu-64` 1346-keV line.
