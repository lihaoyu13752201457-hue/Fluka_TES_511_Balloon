# Phase-2 T1 Cu-Sphere Transport Smoke

- status: `T1_CU_SPHERE_TRANSPORT_SMOKE_COMPLETE`
- primary_count: `2048`
- geometry: `Copper sphere, radius 1.0 cm, in vacuum`
- family_summary_csv: `engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t1_cu_sphere_transport_smoke/family_escape_summary.csv`
- comparison_csv: `engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t1_cu_sphere_transport_smoke/escape_yield_comparison.csv`

## Key Escape Yields

| family | metric | FLUKA | MEGAlib | FLUKA/MEGAlib |
|---|---|---:|---:|---:|
| cu64_eplus_smoke | escaped_photon_yield | `1.71289` | `1.6875` | `1.01505` |
| cu64_eplus_smoke | escaped_w2_photon_yield | `0.957031` | `0.984375` | `0.972222` |
| mono1779_gamma | escaped_photon_yield | `0.984375` | `0.984375` | `1` |
| mono1779_gamma | escaped_w2_photon_yield | `0.0195312` | `0.0117188` | `1.66667` |
| mono2754_gamma | escaped_photon_yield | `0.992188` | `1.03906` | `0.954887` |
| mono2754_gamma | escaped_w2_photon_yield | `0.015625` | `0.0507812` | `0.307692` |
| mono511_gamma | escaped_photon_yield | `0.857422` | `0.869141` | `0.986517` |
| mono511_gamma | escaped_w2_photon_yield | `0.451172` | `0.478516` | `0.942857` |
| pair511_gamma | escaped_photon_yield | `0.849609` | `0.875` | `0.970982` |
| pair511_gamma | escaped_w2_photon_yield | `0.460938` | `0.513672` | `0.897338` |

Approximate Poisson z-scores are included in `escape_yield_comparison.csv`; low-count 511-like secondaries from the 1779/2754-keV photon rows should not be overinterpreted from ratios alone.

## Boundary

- This is a T1 smoke, not the final Phase-2 transport closure.
- The common T0 source table is reused; neither code resamples the source.
- FLUKA escape is scored at the Cu-to-vacuum boundary; MEGAlib escape is parsed from `IA ESCP` at world escape after vacuum flight.
- FLUKA copper deposit totals are included, but MEGAlib deposit-level truth is not yet part of this smoke output.
- T1/T2 production closure still needs a common raw-deposit schema, annihilation-vertex/stopping observables, and deterministic W2 response.
