# Phase-2 T2 Cu+Ta Absorber Transport Production-Statistics

- status: `T2_CU_TA_ABSORBER_TRANSPORT_PRODUCTION_COMPLETE`
- primary_count: `300000`
- source_mode: `generated`
- geometry: `Cu sphere radius 1.0 cm + Ta slab 4.0 x 4.0 x 0.1 cm at z=3.0 cm`
- large_input_tables_retained: `False`
- common_primaries_sha256: `276bf6b64aac96669d6379866e85d05a9a34795fb0cff1c472970f5ffc6ed548`
- common_primaries_sample_csv: `engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t2_cu_ta_absorber_transport_production_100k/common_primaries_sample.csv`
- family_summary_csv: `engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t2_cu_ta_absorber_transport_production_100k/family_ta_deposit_summary.csv`
- comparison_csv: `engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t2_cu_ta_absorber_transport_production_100k/ta_deposit_efficiency_comparison.csv`

## Source Mix

| family | particle | count |
|---|---|---:|
| cu64_eplus_smoke | eplus | `100000` |
| mono511_gamma | gamma | `100000` |
| pair511_gamma | gamma | `100000` |

## Key Ta Deposit Efficiencies

| family | metric | FLUKA | MEGAlib | FLUKA/MEGAlib | z approx |
|---|---|---:|---:|---:|---:|
| cu64_eplus_smoke | eff_480_550 | `0.01232` | `0.01212` | `1.0165` | `0.405` |
| cu64_eplus_smoke | eff_w2_510p58_511p42 | `0.01132` | `0.011` | `1.02909` | `0.677` |
| mono511_gamma | eff_480_550 | `0.00592` | `0.00599` | `0.988314` | `-0.203` |
| mono511_gamma | eff_w2_510p58_511p42 | `0.00551` | `0.00559` | `0.985689` | `-0.24` |
| pair511_gamma | eff_480_550 | `0.00583` | `0.00578` | `1.00865` | `0.147` |
| pair511_gamma | eff_w2_510p58_511p42 | `0.00545` | `0.00541` | `1.00739` | `0.121` |

## Boundary

- This is a production-statistics T2 generated-source transport gate, but still a toy geometry rather than full TES geometry.
- The Ta slab is intentionally larger than a physical TES pixel to get stable deposited-energy statistics.
- Detector smearing is disabled on the MEGAlib side with `EnergyResolution Ideal`; FLUKA records raw deposited energy.
- Full input tables are allowed to be dropped after hashing; both engines still receive the same in-memory primary list in the same run.
- The final closure still needs exact full-geometry source positions, material/region audit, common ancestry/stopping observables, and deterministic analytic W2 response.
