# FLUKA TES511 Cross-Check Handoff

This repository is a reduced public handoff for the TES_511_BALLOON FLUKA
cross-code check. It keeps the final post-processing code and conclusion
artifacts, while excluding bulky raw FLUKA/Cosima simulation outputs.

## Main Conclusion

The W2 final total background rate agrees closely between TES_511_BALLOON and
FLUKA independent-source transport, but the agreement is partly a cancellation:

| component | TES cps | FLUKA cps | FLUKA/TES |
|---|---:|---:|---:|
| prompt | `0.036641023` | `0.031891161` | `0.870` |
| delayed | `0.002575203` | `0.006787802` | `2.636` |
| total | `0.039216227` | `0.038678963` | `0.986` |

The prompt deficit (`-0.004749862 cps`) and delayed excess
(`+0.004212598 cps`) mostly cancel in the total. Therefore the total W2 rate
is not yet evidence that the prompt and activation components are each correct.

## Latest Cross-Code Gate

The Phase-3 Cu-64 independent-source gate now runs the same deterministic
`1,000,000`-parent Cu-64 stream in FLUKA and MEGAlib without `.sim.gz` replay.
Raw W2 full-geometry TES coupling is already different before detector response:
FLUKA `1269 / 1000000`, MEGAlib `1008 / 1000000`, FLUKA/MEGAlib `1.25893`
(`5.47 sigma`). Applying the same parent-history active veto and analytic W2
Gaussian response gives FLUKA/MEGAlib `1.25946` raw and `1.17707` after active
veto, so the first failed phase is full-geometry raw-deposit/source-material
coupling, not the common W2 response.

The first raw-coupling decomposition shows this is not a single CuNi or
non-neutron source-class problem. The largest positive W2 source-volume
contributor is `ColdPlate_MXC_50mK_SD_anchor` (`438` FLUKA versus `227`
MEGAlib), while `Cu_SubstrateSupport_SolidDisk_L0_deepest` pulls the opposite
way (`74` versus `164`). The next discriminator is boundary/point-location,
positron stopping/annihilation, and incident TES ancestry inside those source
volumes.

A static source-boundary margin audit weakens a pure near-boundary explanation:
positions with margin `< 0.01 cm` contribute only `0.13` of the net W2 raw
difference. Runtime point-location and stopping/annihilation location are still
separate open tests.

The common external time/topology builder now also runs on the independent raw
deposits. Parent-history and 1 microsecond clustering are identical for W2; 1
nanosecond clustering only shifts MEGAlib active-veto W2 from `563` to `568`
and leaves FLUKA at `662`. Event grouping is therefore not the source of the
delayed-W2 difference. Final side-Compton/FoV reconstruction remains open.

A manuscript-facing delayed-background statement is included under
`engineering/crosscode_delayed_closure_20260625/05_decision/`. The recommended
treatment is to report delayed activation as an unresolved cross-code model
systematic, not to use the W2 total agreement as delayed-component validation.

The remaining conditional gates in `engineering.md` are dispositioned in
`engineering/crosscode_delayed_closure_20260625/05_decision/engineering_completion_audit.md`.
Runtime point-location, positron stopping/annihilation, incident TES ancestry,
and final FoV reconstruction remain future mechanism diagnostics rather than
blockers for the current raw-coupling/systematic conclusion.

Mechanism focus audit: the observed W2 excess is source-volume specific, not a
global distance or boundary effect. `ColdPlate_MXC_50mK_SD_anchor` is
FLUKA-high (`438` versus `227`), while
`Cu_SubstrateSupport_SolidDisk_L0_deepest` is MEGAlib-high (`74` versus `164`).
MEGAlib shows gamma `phot`/`compt` ancestry feeding TES-local electron
deposits; FLUKA currently records only local deposit proxies, so a
TES-boundary/ancestry scorer is the next required mechanism diagnostic.

## Key Artifacts

- `work_fluka_harness/fluka_11_like_energy_band_stats_20260625/summary.md`
  - 11_fix5-like energy-band comparison.
  - Prompt/delayed fractions by energy band.
  - TES deposit carrier check.
- `work_fluka_harness/final_background_composition_independent_source_20260625.md`
  - Compact final W2 background composition summary.
- `work_fluka_harness/prompt_final_same_stat_independent_source_20260625/`
  - Prompt same-statistic comparison artifacts.
- `work_fluka_harness/delayed_final_same_stat_isotope_source_full254704/`
  - Delayed isotope-source same-statistic comparison artifacts.
- `engineering/crosscode_delayed_closure_20260625/`
  - Current delayed closure engineering status.
  - FLUKA runtime source-identity gate showing that checked delayed parents
    are not silently replaced by the dummy `HI-PROPE 53 128` card.
  - Phase-3 Cu-64 production raw-deposit and parent-history event-builder
    summaries.
  - Manuscript delayed-background statement and claim boundary.
  - Engineering completion audit and conditional gate disposition.
  - Mechanism-focus audit over source volume, source-to-TES distance,
    topology, and available ancestry/proxy labels.

## Important Interpretation Detail

`eplus` and `n` in the final W2 prompt decomposition are source tags, not the
identity of the particle locally depositing energy in the TES. The FLUKA local
TES deposit carrier table is dominated by `EM_BELOW_THRESHOLD`, consistent
with electromagnetic/photon-induced local deposits. The MEGAlib `CC HIT`
cross-check makes this explicit at smoke statistics: most TES-local `e-`
deposits carry `gamma phot/compt` ancestry, with smaller direct `gamma` rows.
So "electron" in a local-deposit table is a carrier label, not evidence that
photons are absent from the TES background.

## Excluded Data

Raw FLUKA chunks, replay runs, local temporary FLUKA/Cosima outputs, and old
`.sim.gz` replay/source-truth validation artifacts were removed from this
reduced handoff. Replay-derived checks are not used for the final
independent-source conclusion.
