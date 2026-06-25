# Independent Source Prompt Coverage - 2026-06-25

## Scope

This is the prompt-only independent-source coverage artifact for TES_511_BALLOON
cross-code validation. It uses `sampled_source_authority` for FLUKA primary
generation. The old Geant4 `.sim.gz` IA INIT source-truth diagnostic has been
removed from the reduced handoff and is not used as final evidence.

Delayed activation/source construction is reported separately in `work_fluka_harness/delayed_final_same_stat_isotope_source_full254704/summary.md`.

## Source Authority

The retained prompt evidence is the independent-source FLUKA same-statistic
transport result below. The temporary `.sim.gz` IA INIT source-truth comparison
used during debugging was removed because it is replay-derived side evidence.

Energy policy for the legacy source CDFs:
`LEGACY_CDF_ENERGY_MEV_COLUMN_USED_AS_KEV_TO_MATCH_TES_COSIMA_SOURCE`.

## Full-Stat Runs

| particle | histories | valid chunks | comparison artifact | status |
|---|---:|---:|---|---|
| eplus | `1,949,816` | `24/24` | `work_fluka_harness/eplus_crosscode_comparison_independent_fixed_1949816_chunks24_parallel/summary.md` | `EQUAL_STAT_EPLUS_FULL_PRESENT` |
| muplus | `92,840` | `8/8` | `work_fluka_harness/muplus_crosscode_comparison_independent_fixed_92840_chunks8_parallel/summary.md` | `EQUAL_STAT_MUPLUS_FULL_PRESENT` |
| muminus | `82,824` | `8/8` | `work_fluka_harness/muminus_crosscode_comparison_independent_fixed_82824_chunks8_parallel/summary.md` | `EQUAL_STAT_MUMINUS_FULL_PRESENT` |
| alpha | `191,464` | `8/8` | `work_fluka_harness/alpha_crosscode_comparison_independent_fixed_191464_chunks8_parallel/summary.md` | `EQUAL_STAT_ALPHA_FULL_PRESENT` |
| p | `1,871,808` | `24/24` | `work_fluka_harness/p_crosscode_comparison_independent_fixed_1871808_chunks24_parallel/summary.md` | `EQUAL_STAT_P_FULL_PRESENT` |
| eminus | `3,316,936` | `32/32` | `work_fluka_harness/eminus_crosscode_comparison_independent_fixed_3316936_chunks32_parallel/summary.md` | `EQUAL_STAT_EMINUS_FULL_PRESENT` |
| gamma | `10,000,000` | `40/40` | `work_fluka_harness/gamma_crosscode_comparison_independent_fixed_10000000_chunks40_parallel/summary.md` | `EQUAL_STAT_GAMMA_FULL_PRESENT` |
| n | `7,704,528` | `32/32` | `work_fluka_harness/n_crosscode_comparison_independent_fixed_7704528_chunks32_parallel/summary.md` | `EQUAL_STAT_N_FULL_PRESENT` |
| total | `25,210,216` | `176/176` | prompt independent-source full set | complete |

## W2 Prompt Comparison

Window: `510.58-511.42 keV`. The active-veto stage applies the same scalar BGO/shield total-energy threshold (`<50 keV`) used by Step05. The final side-Compton/FoV stage is evaluated by `build_prompt_final_same_stat_comparison.py` using FLUKA TES deposits aggregated by TES pixel region, with the G4 side validated against the official Step05 prompt CSV before comparison.

| particle | W2 raw G4 events / cps | W2 raw FLUKA events / cps | W2 active G4 events / cps | W2 active FLUKA events / cps |
|---|---:|---:|---:|---:|
| eplus | `57 / 0.0386748` | `47 / 0.0318912` | `52 / 0.0352823` | `46 / 0.0312126` |
| muplus | `7 / 0.00476285` | `6 / 0.00407122` | `0 / 0` | `0 / 0` |
| muminus | `1 / 0.000675325` | `1 / 0.000678514` | `0 / 0` | `0 / 0` |
| alpha | `0 / 0` | `0 / 0` | `0 / 0` | `0 / 0` |
| p | `0 / 0` | `0 / 0` | `0 / 0` | `0 / 0` |
| eminus | `0 / 0` | `0 / 0` | `0 / 0` | `0 / 0` |
| gamma | `2 / 0.0108555` | `1 / 0.00542829` | `0 / 0` | `0 / 0` |
| n | `94 / 0.0638029` | `126 / 0.0854956` | `8 / 0.00543003` | `8 / 0.00542829` |
| total | `161 / 0.118771375` | `181 / 0.127564824` | `60 / 0.040712330` | `54 / 0.036640890` |

## Aggregate Windows

| window | stage | G4 events / cps | FLUKA events / cps | FLUKA/G4 |
|---|---|---:|---:|---:|
| W2 | raw | `161 / 0.118771375` | `181 / 0.127564824` | `1.074` |
| W2 | active veto | `60 / 0.040712330` | `54 / 0.036640890` | `0.900` |
| W2 | side-Compton/FoV | `54 / 0.036641023` | `47 / 0.031891161` | `0.870` |
| 480-550 | raw | `343 / 0.247041600` | `396 / 0.292448500` | `1.184` |
| 480-550 | active veto | `101 / 0.073285560` | `103 / 0.084138437` | `1.148` |
| 480-550 | side-Compton/FoV | `86 / 0.063105929` | `90 / 0.075317454` | `1.194` |
| 50-8000 | raw | `4,257 / 3.117307900` | `4,263 / 3.054089640` | `0.980` |
| 50-8000 | active veto | `850 / 0.738339448` | `686 / 0.565220710` | `0.766` |

## Interpretation

The W2 Step05 same-stat prompt comparison is now independently sourced and normalized at full TES statistics. Raw W2 is high by `7.4%`, active-veto W2 is low by `10.0%`, and side-Compton/FoV final W2 is low by `13.0%` (`z=-0.697`). The final surviving prompt composition remains eplus plus neutron.

The broad prompt spectrum still has residual physics/selection differences outside W2. The largest flagged residuals are full-spectrum active-veto neutron and full-spectrum raw proton. Those should not be hidden by the good W2 prompt result.

The Step05 side-Compton/FoV classifier is validated against the official TES Step05 prompt CSV before FLUKA comparison. Artifact: `work_fluka_harness/prompt_final_same_stat_independent_source_20260625/summary.md`.

The full prompt+delayed background composition is closed in `work_fluka_harness/final_background_composition_independent_source_20260625.md`; this file remains the prompt-only coverage artifact.
