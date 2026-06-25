# Phase-2 T2 Cu+Ta Absorber Transport Smoke

- status: `T2_CU_TA_ABSORBER_TRANSPORT_SMOKE_COMPLETE`
- primary_count: `2048`
- geometry: `Cu sphere radius 1.0 cm + Ta slab 4.0 x 4.0 x 0.1 cm at z=3.0 cm`
- family_summary_csv: `engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t2_cu_ta_absorber_transport_smoke/family_ta_deposit_summary.csv`
- comparison_csv: `engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t2_cu_ta_absorber_transport_smoke/ta_deposit_efficiency_comparison.csv`

## Key Ta Deposit Efficiencies

| family | metric | FLUKA | MEGAlib | FLUKA/MEGAlib | z approx |
|---|---|---:|---:|---:|---:|
| cu64_eplus_smoke | eff_480_550 | `0.0195312` | `0.0078125` | `2.5` | `1.6` |
| cu64_eplus_smoke | eff_w2_510p58_511p42 | `0.0175781` | `0.0078125` | `2.25` | `1.39` |
| mono1779_gamma | eff_480_550 | `0.00390625` | `0` | `n/a` | `1` |
| mono1779_gamma | eff_w2_510p58_511p42 | `0` | `0` | `0` | `0` |
| mono2754_gamma | eff_480_550 | `0` | `0` | `0` | `0` |
| mono2754_gamma | eff_w2_510p58_511p42 | `0` | `0` | `0` | `0` |
| mono511_gamma | eff_480_550 | `0.00195312` | `0.00195312` | `1` | `0` |
| mono511_gamma | eff_w2_510p58_511p42 | `0.00195312` | `0.00195312` | `1` | `0` |
| pair511_gamma | eff_480_550 | `0.00585938` | `0.00390625` | `1.5` | `0.447` |
| pair511_gamma | eff_w2_510p58_511p42 | `0.00585938` | `0.00390625` | `1.5` | `0.447` |

## Boundary

- This is a T2 smoke, not the final production T2 closure.
- The Ta slab is intentionally larger than a physical TES pixel to get smoke statistics from the 2048-row common source.
- Detector smearing is disabled on the MEGAlib side with `EnergyResolution Ideal`; FLUKA records raw deposited energy.
- The final production gate still needs higher statistics, exact agreed Ta/TES dimensions, common ancestry/stopping observables, and deterministic analytic W2 response.
