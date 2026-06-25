# FLUKA Independent-Source fix5 W2 Prompt/Delayed Energy-Band Statistics

Date: 2026-06-25

Scope: same-statistic post-processing of completed independent-source FLUKA runs, using the TES Step05 event catalog only as the comparison authority. No transport run, geometry, source card, or Step05 artifact was modified.

## Bottom Line

The FLUKA mainline is now the intended independent-source reproduction: prompt uses `sampled_source_authority`, delayed uses the weighted exact-position isotope EventList. No `.sim.gz` replay is used for the FLUKA prompt/delayed rates in this note.

The important correction to the earlier shorthand is that `eplus`/`n` are W2 final **source tags**, not the identity of the local particle depositing energy in the TES. The FLUKA TES deposit carrier for selected W2 events is dominated by `EM_BELOW_THRESHOLD`, i.e. local electromagnetic energy deposition below the transport threshold. This is consistent with photon/electromagnetic cascades reaching the TES, but the current raw-deposit CSV does not preserve enough ancestry to label the incident particle as photon event-by-event.

| code | W2 final prompt cps | W2 final delayed cps | delayed fraction |
|---|---:|---:|---:|
| TES_511_BALLOON | `0.036641023` | `0.00257520349` | `6.57%` |
| FLUKA independent source | `0.0318911613` | `0.00678780176` | `17.55%` |

Interpretation: W2 final total remains close, but the composition is not
closed. FLUKA prompt is low relative to TES while delayed activation is high,
so agreement in the total is partly compensating residuals.

## Why The Total Agreement Is Not Yet Composition Agreement

The W2 final total looks excellent only after summing prompt and delayed:

| component | TES cps | FLUKA cps | FLUKA - TES cps | FLUKA/TES |
|---|---:|---:|---:|---:|
| prompt | `0.036641023` | `0.031891161` | `-0.004749862` | `0.870` |
| delayed | `0.002575203` | `0.006787802` | `+0.004212598` | `2.636` |
| total | `0.039216227` | `0.038678963` | `-0.000537263` | `0.986` |

This is the key cross-check result. The prompt residual and delayed residual
have opposite signs and similar magnitudes. The prompt deficit is about
`0.00475 cps`; the delayed excess is about `0.00421 cps`; after summing, only
`0.00054 cps` remains. Therefore the near-unity total rate does **not** prove
that the prompt and activation background components are each correct.

This directly addresses the original suspicion that the TES_511_BALLOON delayed
component might be accidentally too low. The cross-code result does not show a
missing-delayed problem that can be hidden by total-rate agreement; instead it
shows a composition residual: under the independent FLUKA source, delayed W2
final is higher than TES by `2.636x`, while prompt W2 final is lower by
`0.870x`. The next physics question is why the delayed isotope coupling, mostly
`Cu-64` in FLUKA W2 final, is high relative to the TES Step05 delayed sample,
not whether the total W2 background number alone agrees.

## Inputs

- TES Step05 event catalog: `/home/ubuntu/TES_511_Balloon/stepwise_maintenance/step05_veto_time_axis/outputs_fix5_fullstat_v2_exactpos_m50000_s260613_l1/work/event_catalog.pkl`
- TES official rates CSV: `/home/ubuntu/TES_511_Balloon/stepwise_maintenance/step05_veto_time_axis/outputs_fix5_fullstat_v2_exactpos_m50000_s260613_l1/step05_fix5_fullstat_v2_exactpos_m50000_s260613_l1_rates.csv`
- FLUKA prompt histories: `25210216` across `176` valid chunks
- FLUKA delayed histories: `254704` isotope histories; represented activity `86.999842067 Bq`
- G4 Step05 W2/broad validation: `PASS`

## Stage Definitions

- `raw`: event has TES energy in the stated band.
- `active-veto`: `raw` plus shield/BGO total energy `< 50 keV`.
- `final`: `active-veto` plus the Step05 side-entry Compton/FoV keep rule.
- For `all TES > 0`, the lower bound is strictly `tes_total_keV > 0`.

## TES vs FLUKA Energy-Band Delayed Fraction

Fractions are `delayed / (prompt + delayed)`.

| Energy band | TES raw | TES final | FLUKA raw | FLUKA final | FLUKA/TES final delayed cps |
|---|---:|---:|---:|---:|---:|
| all TES > 0 | `3.55%` | `5.12%` | `2.70%` | `3.56%` | `0.5729` |
| 100-300 keV | `6.36%` | `18.31%` | `3.60%` | `10.12%` | `0.4487` |
| 300-480 keV | `3.08%` | `4.17%` | `3.96%` | `6.62%` | `1.682` |
| 480-550 keV | `2.90%` | `4.79%` | `5.71%` | `8.51%` | `2.204` |
| W2 510.58-511.42 keV | `3.76%` | `6.57%` | `8.75%` | `17.55%` | `2.636` |
| 550-800 keV | `2.11%` | `3.36%` | `1.77%` | `4.60%` | `0.5201` |
| 800-1500 keV | `2.55%` | `8.32%` | `2.84%` | `11.23%` | `0.6391` |
| 1500-3000 keV | `13.50%` | `48.85%` | `2.34%` | `11.04%` | `0.04073` |
| 3000-10000 keV | `3.59%` | `14.78%` | `0.17%` | `0.27%` | `0.01427` |

## W2 Same-Statistic Rates

| code | stream | stage | events | rate cps | survival vs raw |
|---|---|---|---:|---:|---:|
| TES_511_BALLOON | prompt | raw | `161` | `0.118771369` | `1` |
| TES_511_BALLOON | prompt | active-veto | `60` | `0.0407123031` | `0.3428` |
| TES_511_BALLOON | prompt | final | `54` | `0.036641023` | `0.3085` |
| TES_511_BALLOON | delayed | raw | `54` | `0.00463536628` | `1` |
| TES_511_BALLOON | delayed | active-veto | `33` | `0.00283272384` | `0.6111` |
| TES_511_BALLOON | delayed | final | `30` | `0.00257520349` | `0.5556` |
| FLUKA | prompt | raw | `181` | `0.127564754` | `1` |
| FLUKA | prompt | active-veto | `54` | `0.03664091` | `0.2872` |
| FLUKA | prompt | final | `47` | `0.0318911613` | `0.25` |
| FLUKA | delayed | raw | `20` | `0.012227336` | `1` |
| FLUKA | delayed | active-veto | `12` | `0.00814536211` | `0.6662` |
| FLUKA | delayed | final | `10` | `0.00678780176` | `0.5551` |

## W2 Prompt Source-Tag Decomposition

These rows are source tags, not TES local deposit carriers.

### raw W2 prompt

| source tag | TES events/rate/fraction | FLUKA events/rate/fraction |
|---|---:|---:|
| `eplus` | `57 / 0.0386747979 / 32.56%` | `47 / 0.0318911547 / 25.00%` |
| `gamma` | `2 / 0.0108555238 / 9.14%` | `1 / 0.00542828936 / 4.26%` |
| `muminus` | `1 / 0.000675325237 / 0.57%` | `1 / 0.000678514375 / 0.53%` |
| `muplus` | `7 / 0.00476285409 / 4.01%` | `6 / 0.00407122031 / 3.19%` |
| `n` | `94 / 0.0638028681 / 53.72%` | `126 / 0.0854955749 / 67.02%` |

### active-veto W2 prompt

| source tag | TES events/rate/fraction | FLUKA events/rate/fraction |
|---|---:|---:|
| `eplus` | `52 / 0.0352822717 / 86.66%` | `46 / 0.0312126195 / 85.19%` |
| `n` | `8 / 0.00543003133 / 13.34%` | `8 / 0.00542829047 / 14.81%` |

### final W2 prompt

| source tag | TES events/rate/fraction | FLUKA events/rate/fraction |
|---|---:|---:|
| `eplus` | `47 / 0.0318897456 / 87.03%` | `41 / 0.0278199435 / 87.23%` |
| `n` | `7 / 0.00475127741 / 12.97%` | `6 / 0.00407121785 / 12.77%` |

## W2 Delayed Isotope Check

| nuclide | TES final events/rate | FLUKA final events/rate |
|---|---:|---:|
| `Cu-62` | `6 / 0.000515040698` | `0 / 0` |
| `Cu-64` | `24 / 0.00206016279` | `10 / 0.00678780176` |

## FLUKA TES Deposit Carrier Check

This is the check for the photon/electron concern. `deposit_carrier` is the local FLUKA particle code attached to TES energy-deposit rows, not the source tag and not a complete ancestry label.

| selection | deposit carrier | dominant events/rate | fractional event-rate share | energy-rate share |
|---|---|---:|---:|---:|
| prompt W2 final | `EM_BELOW_THRESHOLD` | `46 / 0.0312126261` | `98.17%` | `98.17%` |
| prompt W2 final | `ELECTRON` | `1 / 0.000678535207` | `1.83%` | `1.83%` |
| delayed W2 final | `EM_BELOW_THRESHOLD` | `10 / 0.00678780176` | `100.00%` | `100.00%` |
| prompt 480-550 final | `EM_BELOW_THRESHOLD` | `89 / 0.074638919` | `99.23%` | `99.22%` |
| prompt 480-550 final | `ELECTRON` | `1 / 0.000678535207` | `0.77%` | `0.78%` |
| delayed 480-550 final | `EM_BELOW_THRESHOLD` | `15 / 0.00682497382` | `97.48%` | `97.48%` |
| delayed 480-550 final | `ELECTRON` | `3 / 0.000176410316` | `2.52%` | `2.52%` |

## Interpretation

1. The TES_511_BALLOON reference conclusion still holds for the TES side: low W2 delayed fraction is selection-conditional and must not be generalized to all energy bands.
2. FLUKA reproduces the prompt/delayed total W2 final rate closely, but its delayed fraction is higher than TES (`17.55%` vs `6.57%`). The delayed-composition residual remains open.
3. The final W2 prompt source-tag composition is narrow in both codes: `eplus` plus neutron. That statement is about the external prompt source family, not about local TES deposit physics.
4. The FLUKA local TES deposit carrier table is overwhelmingly electromagnetic (`EM_BELOW_THRESHOLD`) for W2 final selections. The current scoring does not retain parent/track ancestry, so a separate boundary-crossing or ancestry scorer would be needed to count incident photons at the TES surface directly.
5. The independent decay-kernel cross-check does not support the hypothesis that one code simply omits the important delayed photons. In fresh independent-source runs, Geant4/MEGAlib smoke and FLUKA production both emit `Na-24` 1369/2754-keV cascades and `Al-28` 1779-keV photons at approximately unit yield; Cu-64 beta-plus yield is also consistent (`0.1767` vs `0.176483`).
6. The first Phase-2 common-source gate now also passes: FLUKA and MEGAlib both start the same `2048` explicit photon/positron primary rows with closed count, energy, direction, particle-code, and weight bookkeeping. This removes source-adapter resampling as the immediate explanation, but it does not yet test Cu/Ta transport or W2 deposition efficiency.
7. The first T1 Cu-sphere transport smoke is complete. For 1 cm Cu sphere escape, the 511-related W2 photon yields are close at smoke statistics: Cu-64 positron rows FLUKA/MEGAlib `0.972`, mono-511 rows `0.943`, and pair-511 rows `0.897`; the largest of these approximate Poisson z-scores is `1.21 sigma`. T2/Ta deposition and common raw-deposit truth remain open.

## Decay-Kernel Cross-Code Check

| nuclide | metric | G4/MEGAlib smoke | FLUKA production |
|---|---|---:|---:|
| `Cu-64` | positron yield / parent | `0.1767` | `0.176483` |
| `Na-24` | 1369-keV gamma yield / parent | `0.99995` | `0.999939` |
| `Na-24` | 2754-keV gamma yield / parent | `0.9988` | `0.998547` |
| `Na-24` | same-parent 1369+2754 fraction | `0.9988` | `0.998547` |
| `Al-28` | 1779-keV gamma yield / parent | `1.0` | `1.0` |

Implication: the remaining high-energy delayed deficit is downstream of this
emission sanity check unless a later production-stat Geant4 run reveals a
smaller low-yield difference. The next discriminators are common
emitted-particle transport, exact source-position/material coupling, and common
postprocessing.

## Phase-2 T0 Common-Source Bookkeeping

One explicit common primary table was generated and read by both engines:

| family | particle | count |
|---|---|---:|
| `mono511_gamma` | gamma | `512` |
| `pair511_gamma` | gamma | `512` |
| `mono1779_gamma` | gamma | `256` |
| `mono2754_gamma` | gamma | `256` |
| `cu64_eplus_smoke` | eplus | `512` |

Source-closure result:

| code | observed / expected | max energy relative delta | max direction 1-dot | status |
|---|---:|---:|---:|---|
| FLUKA | `2048 / 2048` | `4.1880789907739405e-09` | `1.1102230246251565e-16` | PASS |
| MEGAlib | `2048 / 2048` | `5.2968580495807746e-05` | `3.354161393076538e-11` | PASS |

Implication: the next cross-code discriminator should be the T1/T2 Cu/Ta toy
transport and W2/TES energy-deposition efficiency, not another source-list
bookkeeping check. The positron rows here are smoke-statistics source rows; a
production T1/T2 run should replace them with the evaluated/reference Cu-64
beta-plus generator if the positron spectrum itself becomes a precision input.

## Phase-2 T1 Cu-Sphere Transport Smoke

The T1 smoke reuses the same `2048` common primary rows in a homogeneous 1 cm
radius Cu sphere in vacuum. It compares escaped-particle response, not final
detector deposited energy.

| family | metric | FLUKA | MEGAlib | FLUKA/MEGAlib | z approx |
|---|---|---:|---:|---:|---:|
| `cu64_eplus_smoke` | escaped W2 photon yield | `0.957031` | `0.984375` | `0.972222` | `-0.44` |
| `mono511_gamma` | escaped W2 photon yield | `0.451172` | `0.478516` | `0.942857` | `-0.64` |
| `pair511_gamma` | escaped W2 photon yield | `0.460938` | `0.513672` | `0.897338` | `-1.21` |
| `mono1779_gamma` | total escaped photon yield | `0.984375` | `0.984375` | `1.0` | `0.00` |
| `mono2754_gamma` | total escaped photon yield | `0.992188` | `1.039062` | `0.954887` | `-0.53` |

Interpretation: this smoke does not show a large source/escape mismatch for
the 511-like Cu-sphere response. It also does not close the delayed discrepancy:
MEGAlib deposit-level truth, annihilation/stopping observables, T2 Ta/TES
deposition, and deterministic W2 response are still required.

## Artifacts

- source rows CSV: `work_fluka_harness/fluka_11_like_energy_band_stats_20260625/source_stage_rows.csv`
- deposit carrier CSV: `work_fluka_harness/fluka_11_like_energy_band_stats_20260625/tes_deposit_carrier_rows.csv`
- delayed fraction CSV: `work_fluka_harness/fluka_11_like_energy_band_stats_20260625/delayed_fraction_rows.csv`
- machine-readable summary: `work_fluka_harness/fluka_11_like_energy_band_stats_20260625/summary.json`
- decay-kernel cross-code comparison: `engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/crosscode_decay_kernel_line_comparison.csv`
- Phase-2 T0 common-source gate: `engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t0_source_bookkeeping_smoke/summary.md`
- Phase-2 T1 Cu-sphere smoke: `engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t1_cu_sphere_transport_smoke/summary.md`
