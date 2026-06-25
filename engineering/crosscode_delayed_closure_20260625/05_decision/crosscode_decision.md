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

Runtime identity result:

| nuclide | event_id | expected Z/A/isomer | FLUKA runtime Z/A/isomer | result |
|---|---:|---:|---:|---|
| Cu-64 | 153 | 29/64/0 | 29/64/0 | PASS |
| Cu-62 | 7 | 29/62/0 | 29/62/0 | PASS |
| I-128 | 16 | 53/128/0 | 53/128/0 | PASS |
| Na-22 | 62 | 11/22/0 | 11/22/0 | PASS |
| Na-24 | 72 | 11/24/0 | 11/24/0 | PASS |
| Al-28 | 65 | 13/28/0 | 13/28/0 | PASS |

## What This Does Not Prove

This does not close the Geant4/MEGAlib versus FLUKA delayed discrepancy. It
only verifies source identity on the FLUKA side for representative source-v2
parents.

Open discriminators:

1. Vacuum decay-kernel comparison for `Cu-64`, `Na-24`, `Al-28`, and `I-128`.
2. Common emitted-particle list through a common toy geometry.
3. Common full-geometry source positions and common external postprocessor.

## Working Hypothesis After This Gate

The leading explanation remains a decay-kernel / emitted-particle-spectrum
difference, not a source-identity replay error. The most decisive existing
signal is the high-energy delayed deficit:

| final delayed band | FLUKA/G4 rate ratio |
|---|---:|
| W2 511 | 2.64 |
| 1500-3000 keV | 0.041 |
| 3000-10000 keV | 0.014 |

The next run should therefore test whether FLUKA `RADDECAY` emits the expected
correlated high-energy gamma cascades for `Na-24` and `Al-28`, while also
checking `Cu-64` for the W2 beta-plus channel and `I-128` because it dominates
the total delayed activity inventory.
