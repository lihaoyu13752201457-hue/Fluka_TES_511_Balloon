# Prompt Independent-Source Step05 Same-Statistic Comparison

- created_utc: 2026-06-25T04:22:38.290800+00:00
- status: PROMPT_FINAL_SAME_STAT_PRESENT
- fluka_histories: 25210216
- fluka_valid_chunks: 176
- g4_step05_validation: PASS
- source_mode: sampled_source_authority; no .sim.gz replay
- active_veto_threshold_keV: 50
- reject_policy: keep

## Aggregate Prompt

| window | stage | G4 events/rate | FLUKA events/rate | FLUKA/G4 | z |
|---|---|---:|---:|---:|---:|
| broad_480_550 | raw | 343 / 0.2470421+/-0.0157 | 396 / 0.292449+/-0.0181 | 1.184 | 1.9 |
| broad_480_550 | active_veto_pass | 101 / 0.0732855+/-0.00869 | 103 / 0.08413842+/-0.0116 | 1.148 | 0.749 |
| broad_480_550 | side_compton_fov_pass | 86 / 0.06310593+/-0.00828 | 90 / 0.07531745+/-0.0113 | 1.194 | 0.87 |
| w2_510p58_511p42 | raw | 161 / 0.1187714+/-0.0115 | 181 / 0.1275648+/-0.0106 | 1.074 | 0.562 |
| w2_510p58_511p42 | active_veto_pass | 60 / 0.0407123+/-0.00526 | 54 / 0.03664091+/-0.00499 | 0.9 | -0.562 |
| w2_510p58_511p42 | side_compton_fov_pass | 54 / 0.03664102+/-0.00499 | 47 / 0.03189116+/-0.00465 | 0.8704 | -0.697 |

## W2 By Prompt Particle

| particle | stage | G4 events/rate | FLUKA events/rate | FLUKA/G4 | z |
|---|---|---:|---:|---:|---:|
| alpha | raw | 0 / 0+/-0 | 0 / 0+/-0 |  |  |
| alpha | active_veto_pass | 0 / 0+/-0 | 0 / 0+/-0 |  |  |
| alpha | side_compton_fov_pass | 0 / 0+/-0 | 0 / 0+/-0 |  |  |
| eminus | raw | 0 / 0+/-0 | 0 / 0+/-0 |  |  |
| eminus | active_veto_pass | 0 / 0+/-0 | 0 / 0+/-0 |  |  |
| eminus | side_compton_fov_pass | 0 / 0+/-0 | 0 / 0+/-0 |  |  |
| eplus | raw | 57 / 0.0386748+/-0.00512 | 47 / 0.03189115+/-0.00465 | 0.8246 | -0.98 |
| eplus | active_veto_pass | 52 / 0.03528227+/-0.00489 | 46 / 0.03121262+/-0.0046 | 0.8847 | -0.606 |
| eplus | side_compton_fov_pass | 47 / 0.03188975+/-0.00465 | 41 / 0.02781994+/-0.00434 | 0.8724 | -0.639 |
| gamma | raw | 2 / 0.01085552+/-0.00768 | 1 / 0.005428289+/-0.00543 | 0.5 | -0.577 |
| gamma | active_veto_pass | 0 / 0+/-0 | 0 / 0+/-0 |  |  |
| gamma | side_compton_fov_pass | 0 / 0+/-0 | 0 / 0+/-0 |  |  |
| muminus | raw | 1 / 0.0006753252+/-0.000675 | 1 / 0.0006785144+/-0.000679 | 1.005 | 0.00333 |
| muminus | active_veto_pass | 0 / 0+/-0 | 0 / 0+/-0 |  |  |
| muminus | side_compton_fov_pass | 0 / 0+/-0 | 0 / 0+/-0 |  |  |
| muplus | raw | 7 / 0.004762854+/-0.0018 | 6 / 0.00407122+/-0.00166 | 0.8548 | -0.282 |
| muplus | active_veto_pass | 0 / 0+/-0 | 0 / 0+/-0 |  |  |
| muplus | side_compton_fov_pass | 0 / 0+/-0 | 0 / 0+/-0 |  |  |
| n | raw | 94 / 0.06380287+/-0.00658 | 126 / 0.08549557+/-0.00762 | 1.34 | 2.16 |
| n | active_veto_pass | 8 / 0.005430031+/-0.00192 | 8 / 0.00542829+/-0.00192 | 0.9997 | -0.000641 |
| n | side_compton_fov_pass | 7 / 0.004751277+/-0.0018 | 6 / 0.004071218+/-0.00166 | 0.8569 | -0.278 |
| p | raw | 0 / 0+/-0 | 0 / 0+/-0 |  |  |
| p | active_veto_pass | 0 / 0+/-0 | 0 / 0+/-0 |  |  |
| p | side_compton_fov_pass | 0 / 0+/-0 | 0 / 0+/-0 |  |  |

## Notes

- `side_compton_fov_pass` uses the TES Step05 side-entry Compton/FoV classifier ported from `build_v3p5_centerfinger_step05_l1_response.py`.
- The Geant4 side is validated against the official Step05 prompt CSV before FLUKA comparison.
- FLUKA TES deposits are aggregated by FLUKA TES pixel region name and energy-weighted deposit position before classification.
- This remains prompt-only; delayed activation/source construction is not included.
