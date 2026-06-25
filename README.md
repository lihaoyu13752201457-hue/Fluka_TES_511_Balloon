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
- `work_fluka_harness/source_truth_validation/`
  - Source-truth gate summaries for the eight prompt species.

## Important Interpretation Detail

`eplus` and `n` in the final W2 prompt decomposition are source tags, not the
identity of the particle locally depositing energy in the TES. The FLUKA local
TES deposit carrier table is dominated by `EM_BELOW_THRESHOLD`, consistent
with electromagnetic/photon-induced local deposits. The current raw-deposit CSV
does not retain full parent/track ancestry, so a dedicated boundary-crossing or
ancestry scorer would be needed to count incident photons at the TES surface
event by event.

## Excluded Data

Raw FLUKA chunks, replay runs, smoke runs, local temporary FLUKA outputs, and
old `.sim.gz` replay comparison artifacts were removed from this reduced
handoff. Replay is transport-only side evidence and is not used for the final
independent-source conclusion.
