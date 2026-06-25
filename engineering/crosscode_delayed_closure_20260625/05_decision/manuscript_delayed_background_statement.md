# Manuscript Delayed-Background Statement

Date: 2026-06-25

## Recommended Manuscript Wording

The independent FLUKA reproduction gives a W2 final total rate consistent with
the TES_511_BALLOON/Geant4 reference, but the agreement is not component-level
closure. In the 510.58-511.42 keV W2 final selection, TES_511_BALLOON gives
`0.036641023 cps` prompt and `0.002575203 cps` delayed, while the independent
FLUKA run gives `0.031891161 cps` prompt and `0.006787802 cps` delayed. The
total W2 rates therefore agree at FLUKA/TES `0.986`, but this is a cancellation
between a prompt deficit (`0.870x`) and a delayed excess (`2.636x`). We treat
the delayed activation component as an unresolved cross-code model systematic
for the present analysis rather than using the total W2 agreement as validation
of the delayed component.

The current cross-code closure study does not support a post-processing
explanation for the delayed W2 difference. A deterministic `1,000,000`-parent
Cu-64 stream was transported independently in FLUKA and MEGAlib without
`.sim.gz` replay. The W2 raw full-geometry coupling differs before detector
response: FLUKA `1269/1000000`, MEGAlib `1008/1000000`,
FLUKA/MEGAlib `1.25893` (`5.47 sigma`). Applying an identical analytic W2
Gaussian response gives the same raw ratio within statistics (`1.25946`), and
common 1 microsecond and 1 nanosecond event clustering do not remove the
active-veto excess. The remaining open issue is therefore a full-geometry
raw-coupling mechanism in the dominant Cu source volumes, not the W2 response
window or event grouping.

## Numbers To Quote

| quantity | TES_511_BALLOON / MEGAlib | FLUKA independent source | FLUKA/TES or FLUKA/MEGAlib |
|---|---:|---:|---:|
| W2 final prompt cps | `0.036641023` | `0.031891161` | `0.870` |
| W2 final delayed cps | `0.002575203` | `0.006787802` | `2.636` |
| W2 final total cps | `0.039216227` | `0.038678963` | `0.986` |
| Phase-3 Cu-64 W2 raw histories | `1008 / 1000000` | `1269 / 1000000` | `1.25893` |
| Phase-3 Cu-64 W2 active-veto histories | `563 / 1000000` | `662 / 1000000` | `1.17584` |
| Phase-3 Cu-64 W2 active-veto, 1 ns split | `568 / 1000000` | `662 / 1000000` | `1.16549` |

## Claim Boundary

- Use the W2 total agreement only as a total-rate cross-check, not as delayed
  component validation.
- State that the delayed activation component is currently an unresolved
  cross-code model systematic.
- State that the leading resolved failure layer is full-geometry raw coupling
  before common detector response.
- Do not claim that photons are absent from TES deposits: local FLUKA carrier
  labels such as `EM_BELOW_THRESHOLD` are local deposit labels, and MEGAlib
  smoke truth shows TES-local electrons with gamma `phot`/`compt` ancestry.
- Do not average the TES/MEGAlib and FLUKA delayed central values.
- Do not tune FLUKA cuts to match the W2 total unless a later ancestry or
  runtime point-location gate identifies an EM-cut/material dependence.

## Remaining Work Before Stronger Paper Claim

The next decisive diagnostic is runtime point-location, positron
stopping/annihilation location, and incident TES ancestry inside the dominant
Phase-3 Cu-64 source volumes. Final side-Compton/FoV reconstruction should be
added to the common external event builder only if the manuscript needs a
final-selection-level cross-code statement rather than the current raw-coupling
systematic statement.
