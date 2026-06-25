# Independent Source Rebaseline - 2026-06-25

## Mainline Correction

The cross-code mainline is now constrained back to independent source
reproduction. Geant4 `.sim.gz` IA INIT replay/source-truth checks are not used
as evidence that the FLUKA source adapter is correct, and the old replay-derived
validation artifacts have been removed from the reduced public handoff.

## Code Changes

- `work_fluka_harness/build_source_authority.py`: future source authority builds now treat the TES/Cosima spectrum DP energy axis as keV and derive `energy_MeV = energy_keV / 1000`.
- `work_fluka_harness/run_eplus_raw_mvp.py`: legacy source CDFs with the old `energy_MeV` label are interpreted as the source-axis keV values when running `sampled_source_authority`.

## Source Authority Status

The retained evidence is the independent-source FLUKA same-statistic transport
path, not replay of TES/Cosima generated primaries. The previous
`validate_independent_source_against_sim.py` gate and
`work_fluka_harness/source_truth_validation/` outputs were useful temporary
diagnostics for the prompt 1000x energy-axis bug, but they depended on TES
`.sim.gz` IA INIT truth and are not part of the final mainline handoff.

## Independent-Source Prompt Full Statistics

Artifact: `work_fluka_harness/independent_source_prompt_coverage_20260625.md`

- Source mode: `sampled_source_authority`, not `.sim.gz` replay.
- FLUKA histories: `25,210,216`.
- G4 generated: `25,210,216`.
- Chunks: `176/176` valid.
- Parallelization: one driver per long run, internal `--max-parallel 8`.
- Normalization histories: full particle total for every species.
- Status: prompt full-stat independent-source complete.

W2 same-observable prompt total:

| stage | G4 events / cps | FLUKA events / cps | FLUKA/G4 |
|---|---:|---:|---:|
| raw | `161 / 0.118771375` | `181 / 0.127564824` | `1.074` |
| active veto | `60 / 0.040712330` | `54 / 0.036640890` | `0.900` |
| side-Compton/FoV | `54 / 0.036641023` | `47 / 0.031891161` | `0.870` |

The W2 final prompt rate is now evaluated with the same Step05 side-Compton/FoV statistic. Its composition is still eplus plus neutron. The larger remaining prompt discrepancies are outside W2: full-spectrum active-veto neutron (`FLUKA/G4=0.6966`, `z=-5.53`) and full-spectrum raw proton (`FLUKA/G4=0.0303`, `z=-5.49`).

## Updated Mainline Status

Full prompt+delayed W2 final composition is now present with independent FLUKA sources. Delayed activation/source construction is implemented as `delayed_source_v2_weighted_exact_position_isotope_eventlist`, run for `254,704` isotope histories with represented activity `86.999842067 Bq`; no `.sim.gz` replay is used. The remaining issue is delayed physics/composition residual, not missing source construction.
