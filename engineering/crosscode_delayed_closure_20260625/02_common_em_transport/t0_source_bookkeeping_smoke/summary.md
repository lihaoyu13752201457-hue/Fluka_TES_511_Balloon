# Phase-2 T0 Common-Source Bookkeeping Gate

- status: `T0_COMMON_SOURCE_GATE_PASS`
- primary_count: `2048`
- seed: `24066501`
- common_primaries_csv: `engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t0_source_bookkeeping_smoke/common_primaries.csv`
- closure_comparison_csv: `engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t0_source_bookkeeping_smoke/closure_comparison.csv`

## Source Mix

| family | particle | count |
|---|---|---:|
| cu64_eplus_smoke | eplus | `512` |
| mono1779_gamma | gamma | `256` |
| mono2754_gamma | gamma | `256` |
| mono511_gamma | gamma | `512` |
| pair511_gamma | gamma | `512` |

## Engine Closure

| code | status | observed / expected | max energy rel delta | max direction 1-dot |
|---|---|---:|---:|---:|
| FLUKA | `PASS` | `2048 / 2048` | `4.1880789907739405e-09` | `1.1102230246251565e-16` |
| MEGAlib | `PASS` | `2048 / 2048` | `5.2968580495807746e-05` | `3.354161393076538e-11` |

## Boundary

- This is not a detector-rate or W2-efficiency result.
- Every primary row is explicit in the common CSV; neither code resamples source energy or direction.
- Back-to-back 511 rows retain a `pair_id`, but T0 transports rows independently to test bookkeeping.
- The Cu-64 positron rows use a frozen allowed-spectrum smoke sampler only; T1/T2 production should replace it with the evaluated/reference beta-plus generator.
- Raw FLUKA and Cosima run products are ignored and deleted by default; tracked outputs are compact source and closure tables.
