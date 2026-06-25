# fix5 W2 Prompt/Delayed Energy-Band Statistics

Date: 2026-06-23

Scope: local statistics and interpretation for the current fix5
`fix5_fullstat_v2_exactpos_m50000_s260613` Step05 detector-response output.
No geometry, source card, SIM, Step05 authority output, or promotion artifact
was modified.

## Bottom Line

The current low W2 delayed fraction is not caused by active veto/FoV cuts
preferentially suppressing delayed activation. The data show the opposite:
the delayed fraction rises after the active-veto and side/FoV selections.

The correct statement is narrower:

> In the current exact-position delayed source and Step05 detector-response
> selection, activation source strength is non-negligible, but activation
> couples inefficiently into the final TES W2 511-keV line-window sample. The
> final W2 background is dominated by prompt atmospheric/cosmic `eplus`-tagged
> 511-like events.

This must not be generalized to "activation is negligible". In wider or higher
energy bands, delayed activation can become a large or even comparable final
component.

## Inputs

Primary Step05 rates:

- `stepwise_maintenance/step05_veto_time_axis/outputs_fix5_fullstat_v2_exactpos_m50000_s260613_l1/step05_fix5_fullstat_v2_exactpos_m50000_s260613_l1_rates.csv`
- `stepwise_maintenance/step05_veto_time_axis/outputs_fix5_fullstat_v2_exactpos_m50000_s260613_l1/work/event_catalog.pkl`

Selection and parser logic:

- `old/code/tools/build_v3p5_centerfinger_step05_l1_response.py`

Delayed selected-event audit:

- `outputs/reports/fix5_fullstat_v2_exactpos_m50000_s260613/fix5_w_activation_selected_w2_audit.json`
- `outputs/reports/fix5_fullstat_v2_exactpos_m50000_s260613/fix5_w_activation_selected_w2_events.csv`

Delayed source support:

- `outputs/reports/fix5_fullstat_v2_exactpos_m50000_s260613/fix5_delayed_source_exactpos_summary.json`
- `runs/step02_delay_fix_fix5_fullstat_v2/exactpos_weighted_rpip_table_m50000_s260613.csv`

## Stage Definitions

The rates below use the Step05 event catalog and the same active-veto and
side-entry Compton/FoV routines used by the fix5 Step05 summary:

- `raw`: event has TES energy in the stated energy band.
- `active_veto`: `raw` plus `bgo_total_keV < 50 keV`.
- `final`: `active_veto` plus Step05 side-entry Compton/FoV keep.

For `all TES > 0`, the lower bound was treated as `tes_total_keV > 0`. Do not
use a literal `summarize_window(0, inf)` for this check because that also
admits `tes_total_keV == 0` events.

## Energy-Band Delayed Fraction

Fractions below are `delayed / (prompt + delayed)`.

| Energy band | Raw fraction | Final fraction | Raw delayed/prompt | Final delayed/prompt |
|---|---:|---:|---:|---:|
| all TES > 0 | `3.55%` | `5.12%` | `3.68%` | `5.39%` |
| 100-300 keV | `6.36%` | `18.31%` | `6.79%` | `22.41%` |
| 300-480 keV | `3.08%` | `4.17%` | `3.18%` | `4.35%` |
| 480-550 keV | `2.90%` | `4.79%` | `2.99%` | `5.03%` |
| W2 510.58-511.42 keV | `3.76%` | `6.57%` | `3.90%` | `7.03%` |
| 550-800 keV | `2.11%` | `3.36%` | `2.16%` | `3.48%` |
| 800-1500 keV | `2.55%` | `8.32%` | `2.62%` | `9.08%` |
| 1500-3000 keV | `13.50%` | `48.85%` | `15.60%` | `95.52%` |
| 3000-10000 keV | `3.59%` | `14.78%` | `3.72%` | `17.34%` |

The W2 line window is therefore delayed-low already at the detector-coupled
raw stage. The final selection does not explain the low W2 delayed fraction by
destroying delayed events; it increases delayed's relative share because prompt
is cut harder.

## W2 Official Step05 Rates

| Stream | Stage | Events | Rate cps | Survival vs raw |
|---|---|---:|---:|---:|
| prompt | raw | `161` | `0.118771369178` | `1.0000` |
| prompt | active_veto | `60` | `0.0407123030753` | `0.3428` |
| prompt | final | `54` | `0.0366410230297` | `0.3085` |
| delayed | raw | `54` | `0.00463536628009` | `1.0000` |
| delayed | active_veto | `33` | `0.00283272383783` | `0.6111` |
| delayed | final | `30` | `0.00257520348894` | `0.5556` |

Implication:

- raw W2 delayed/prompt = `0.0390`;
- final W2 delayed/prompt = `0.0703`;
- raw W2 delayed/(prompt+delayed) = `3.76%`;
- final W2 delayed/(prompt+delayed) = `6.57%`.

## Independent FLUKA W2 Cross-Check

The matching independent-source FLUKA statistic gives a different W2
composition even though the final total is close:

| component | TES cps | FLUKA cps | FLUKA - TES cps | FLUKA/TES |
|---|---:|---:|---:|---:|
| prompt | `0.036641023` | `0.031891161` | `-0.004749862` | `0.870` |
| delayed | `0.002575203` | `0.006787802` | `+0.004212598` | `2.636` |
| total | `0.039216227` | `0.038678963` | `-0.000537263` | `0.986` |

Conclusion: the near-unity W2 total is compensation. FLUKA prompt is lower by
about `0.00475 cps`, while FLUKA delayed is higher by about `0.00421 cps`; the
sum leaves only a `0.00054 cps` residual. Therefore this cross-check does not
validate the prompt and delayed components separately. It sharpens the original
question: the TES delayed W2 fraction may be low relative to FLUKA, but the
reason cannot be judged from the total W2 agreement.

The same cross-check also answers the "why only neutron/electron?" concern:
`eplus` and `n` are source-family tags in the final W2 prompt table, not the
local TES depositing particle. In the FLUKA raw-deposit audit, selected W2 TES
energy is dominated by `EM_BELOW_THRESHOLD`, consistent with photon/electromagnetic
cascades reaching the TES. A separate ancestry or boundary-crossing scorer is
still required to label incident photons event by event.

### Phase-3 Cu-64 cross-code check of the delayed-W2 question

The latest independent-source cross-code gate now tests the dominant delayed
W2 isotope channel more directly. FLUKA and MEGAlib were both run on the same
deterministic 1,000,000-parent Cu-64 source stream, without `.sim.gz` replay.
Full raw truth is kept locally under `/tmp/phase3prod`; only summary CSV/JSON
artifacts are committed.

Raw full-geometry TES coupling:

| band | FLUKA events / histories | MEGAlib events / histories | FLUKA/MEGAlib | z |
|---|---:|---:|---:|---:|
| all TES > 0 | `6566 / 1000000` | `2797 / 1000000` | `2.34752` | `39.1` |
| 480-550 keV | `1470 / 1000000` | `1072 / 1000000` | `1.37127` | `7.9` |
| W2 510.58-511.42 keV | `1269 / 1000000` | `1008 / 1000000` | `1.25893` | `5.47` |

Applying the same parent-history active-veto and analytic W2 Gaussian response
does not remove the difference: the analytic W2 expectation gives
FLUKA/MEGAlib `1.25946` raw (`5.48 sigma`) and `1.17707` after active veto
(`2.85 sigma`).

Therefore the current answer to "why would TES_511_BALLOON delayed W2 be this
low?" is not "the W2 response or final selection artificially removed delayed
events." The cross-code failure appears earlier: full-geometry raw-deposit or
source-material coupling for Cu-64 already differs before the common detector
response is applied. The remaining open task is to isolate which full-geometry
coupling detail causes that raw Cu-64 difference.

The first raw-coupling decomposition narrows that open task. The W2 raw
excess is not isolated to `CuNi` or to a non-neutron source class: Copper
contributes `1210` FLUKA versus `989` MEGAlib W2 histories, CuNi contributes
`59` versus `19`, and the neutron-produced rollup is `1267` versus `1002`.
At source-volume level, `ColdPlate_MXC_50mK_SD_anchor` is the largest positive
contributor (`438` versus `227`), while `Cu_SubstrateSupport_SolidDisk_L0_deepest`
pulls in the opposite direction (`74` versus `164`). That points to distributed
geometry/raw-coupling behavior, not a single source-class bookkeeping mistake.

## Stream Classification Check

The Step05 parser assigns `stream` by SIM file/mode, not by secondary particle
type:

- `mode == "prompt"` returns `stream="prompt"` plus the prompt tag parsed from
  the prompt SIM file name.
- `mode == "delayed"` returns `stream="delayed", tag="activation"`.
- `mode == "science"` returns `stream="science"`.

Therefore a positron emitted inside a delayed radioactive decay is not
reclassified as prompt `eplus`. A delayed beta-plus decay in the delayed SIM
remains in `stream="delayed"`.

Relevant implementation location:

- `old/code/tools/build_v3p5_centerfinger_step05_l1_response.py`, function
  `configure_parser`, `event_rate_for_mode`.

## W2 Prompt Tag Decomposition

### Raw W2 prompt

| Prompt tag | Events | Rate cps | Fraction of prompt raw |
|---|---:|---:|---:|
| `n` | `94` | `0.0638028681425` | `53.72%` |
| `eplus` | `57` | `0.0386747978733` | `32.56%` |
| `gamma` | `2` | `0.0108555238333` | `9.14%` |
| `muplus` | `7` | `0.00476285409269` | `4.01%` |
| `muminus` | `1` | `0.000675325236634` | `0.57%` |

### Active-veto W2 prompt

| Prompt tag | Events | Rate cps | Fraction of prompt active-veto |
|---|---:|---:|---:|
| `eplus` | `52` | `0.0352822717441` | `86.66%` |
| `n` | `8` | `0.00543003133128` | `13.34%` |

### Final W2 prompt

| Prompt tag | Events | Rate cps | Fraction of prompt final |
|---|---:|---:|---:|
| `eplus` | `47` | `0.0318897456148` | `87.03%` |
| `n` | `7` | `0.00475127741487` | `12.97%` |

Prompt survival from raw to final:

| Prompt tag | Final/raw survival |
|---|---:|
| `eplus` | `82.46%` |
| `n` | `7.45%` |
| `gamma` | `0%` |
| `muplus` | `0%` |
| `muminus` | `0%` |

This is the strongest local evidence that the final W2 prompt background is an
`eplus`-tagged 511-like component that survives the active veto well.

## W2 Prompt eplus Survivor Diagnostics

For final W2 prompt `eplus` events:

| Quantity | Value |
|---|---:|
| selected events | `47` |
| selected rate | `0.0318897456148 cps` |
| BGO energy min / max / mean | `0 / 0 / 0 keV` |
| events with nonzero BGO energy | `0` |
| single-pixel TES events | `33` |
| two-pixel TES events | `12` |
| three-pixel TES events | `2` |
| Step05 side class `single` | `33` |
| Step05 side class `keep` | `14` |

Interpretation: these surviving events are not obviously charged particles
that deposited visible energy in the BGO veto. They look more like prompt
`eplus`-stream 511-keV photon events that reach the TES without BGO energy.
This points to prompt 511 photon acceptance/source normalization/side-aperture
coupling, not simply to delayed activation underestimation.

## W2 Delayed Selected-Event Audit

The final W2 delayed sample contains `30` selected events at
`0.00257520348894 cps`.

By isotope:

| ZA | Nuclide | Events | Rate cps | Fraction of delayed final |
|---|---|---:|---:|---:|
| `29064` | Cu-64 | `24` | `0.00206016279115` | `80.0%` |
| `29062` | Cu-62 | `6` | `0.000515040697788` | `20.0%` |

By source volume:

| Source volume | Events | Rate cps |
|---|---:|---:|
| `ColdPlate_MXC_50mK_SD_anchor` | `13` | `0.00111592151187` |
| `Cu_SubstrateSupport_SolidDisk_L0_deepest` | `6` | `0.000515040697788` |
| `Cu_50mK_StillLike_Can_bottom_cap_2mm` | `3` | `0.000257520348894` |
| `ColdPlate_CP_100mK_intercept` | `2` | `0.000171680232596` |
| `Window` | `2` | `0.000171680232596` |
| `Cu_50mK_StillLike_Can_side_wall_above_side_port` | `2` | `0.000171680232596` |
| `DR_MixingChamber_Cu` | `1` | `0.0000858401162980` |
| `ColdPlate_Still_0p7K` | `1` | `0.0000858401162980` |

W/collimator contribution in selected W2 delayed:

| Quantity | Value |
|---|---:|
| W/collimator selected events | `0` |
| W/collimator selected rate | `0 cps` |

This supports the statement that the selected W2 activation component is mostly
nearby Cu activation, not W/collimator activation and not the dominant CsI/I-128
inventory component.

## Delayed Source Inventory Context

The fixed exact-position delayed source has total weight/activity:
`85.4492025355 Bq` from the weighted RP/IP table, consistent with the manifest
value `85.4492025388 Bq`.

Top isotope weights in the exact-position delayed source:

| ZA | Nuclide | Weight/activity Bq | Fraction |
|---|---|---:|---:|
| `53128` | I-128 | `65.5333948` | `76.69%` |
| `13028` | Al-28 | `6.88689962` | `8.06%` |
| `29064` | Cu-64 | `4.66864495` | `5.46%` |
| `12027` | Mg-27 | `2.23714939` | `2.62%` |
| `55134` | Cs-134 | `1.12971224` | `1.32%` |
| `29066` | Cu-66 | `1.11319604` | `1.30%` |
| `74187` | W-187 | `0.931938783` | `1.09%` |
| `11024` | Na-24 | `0.469041579` | `0.55%` |
| `47110` | Ag-110 | `0.435776874` | `0.51%` |
| `55132` | Cs-132 | `0.421892059` | `0.49%` |
| `29062` | Cu-62 | `0.0977313209` | `0.11%` |

This is why the correct language is "activation source strength is not small,
but W2 final coupling is small." The total activation inventory is dominated by
I-128/CsI activity, while the selected W2 delayed events come from a much
smaller near-detector Cu subset.

## Interpretation

1. W2 delayed is already low before the final cuts. In raw detector-coupled W2,
   delayed/prompt is only `3.90%`.
2. Active veto and side/FoV do not preferentially suppress delayed in W2.
   They reduce prompt more strongly, raising delayed/(prompt+delayed) from
   `3.76%` raw to `6.57%` final.
3. Delayed beta-plus events are not being counted as prompt `eplus`; stream
   classification is mode/SIM based.
4. Final W2 prompt is dominated by prompt `eplus` tag events, and those events
   have zero BGO energy in the current catalog.
5. Broader energy bands do not support a global "activation negligible" claim.
   In `1500-3000 keV`, final delayed/(prompt+delayed) is `48.85%`.

## Manuscript-Safe Wording

Do not write:

> Activation is negligible in the balloon background.

Do not write:

> The active veto suppresses activation so strongly that delayed becomes small.

Write instead:

> Activation is included with audited build-up, half-life handling, and
> exact-position decay sampling. In the current fix5 TES `W2` 511-keV final
> selection, the selected delayed component is small
> (`0.002575 cps`, `6.57%` of prompt+delayed), while the selected prompt
> component is dominated by prompt `eplus`-tagged 511-like events. This is a
> selection-conditional W2 result, not a claim that activation is negligible in
> all balloon energy bands or all event selections.

## Independent Decay-Kernel Cross-Check

The follow-up FLUKA cross-check was intentionally kept on the independent
source path, not on `.sim.gz` replay. It now includes:

- FLUKA runtime source identity gate for representative delayed parents:
  `FLUKA_SOURCE_IDENTITY_GATE_PASS`.
- FLUKA vacuum decay-kernel production for `Cu-64`, `Na-24`, `Al-28`,
  and `I-128`: `1000000` parents per isotope.
- Geant4/MEGAlib independent EventList decay-kernel smoke for the same four
  isotopes: `20000` parents per isotope, parsed from fresh `IA DECA`
  emission records.
- Phase-2 T0 common-source bookkeeping: one explicit photon/positron source
  table was read by both FLUKA and MEGAlib without source-level resampling.

Key cross-code line/yield comparison:

| nuclide | metric | G4/MEGAlib smoke | FLUKA production |
|---|---|---:|---:|
| `Cu-64` | positron yield / parent | `0.1767` | `0.176483` |
| `Cu-64` | 1346-keV gamma yield / parent | `0.0043` | `0.004785` |
| `Na-24` | 1369-keV gamma yield / parent | `0.99995` | `0.999939` |
| `Na-24` | 2754-keV gamma yield / parent | `0.9988` | `0.998547` |
| `Na-24` | same-parent 1369+2754 fraction | `0.9988` | `0.998547` |
| `Al-28` | 1779-keV gamma yield / parent | `1.0` | `1.0` |
| `I-128` | aggregate photon yield / parent | `0.20605` | `0.199216` |

Conclusion from this gate: both installed decay engines emit the high-energy
`Na-24` and `Al-28` gamma lines that dominate the 1.5-10 MeV delayed-band
question. Therefore the FLUKA/TES high-energy delayed deficit is **not**
explained by either code completely failing to emit those photons in the
decay kernel.

This also narrows the W2 question. The FLUKA W2 delayed excess relative to the
TES Step05 result is unlikely to be a simple Cu-64 beta-plus branching
bookkeeping error: G4/MEGAlib smoke gives `0.1767` positrons per Cu-64 parent,
and FLUKA production gives `0.176483`.

What remains open is downstream of this emission sanity check: common
emitted-particle transport, exact source-position/material coupling,
detector-response/event-building differences, and production-stat G4 checks
for low-yield lines such as the `Cu-64` 1346-keV gamma.

## Phase-2 T0 Common-Source Bookkeeping

The first common-transport gate now passes. The common source table has `2048`
explicit primary rows:

| family | particle | count |
|---|---|---:|
| `mono511_gamma` | gamma | `512` |
| `pair511_gamma` | gamma | `512` |
| `mono1779_gamma` | gamma | `256` |
| `mono2754_gamma` | gamma | `256` |
| `cu64_eplus_smoke` | eplus | `512` |

Both engines started the same row count, particle code, kinetic energy,
direction, and weight:

| code | observed / expected | max energy relative delta | max direction 1-dot | status |
|---|---:|---:|---:|---|
| FLUKA | `2048 / 2048` | `4.1880789907739405e-09` | `1.1102230246251565e-16` | PASS |
| MEGAlib | `2048 / 2048` | `5.2968580495807746e-05` | `3.354161393076538e-11` | PASS |

This is deliberately only a T0 source-bookkeeping result. It rules out the
immediate concern that the next comparison is already biased by source
resampling or source-adapter unit drift, but it does **not** yet test positron
slowing, annihilation, photon escape, Cu/Ta transport, or W2/TES deposition
efficiency. That remains the next discriminator for the delayed-composition
residual.

## Phase-2 T1 Cu-Sphere Transport Smoke

The next smoke gate runs the same `2048` explicit primary rows through a
homogeneous 1 cm radius Cu sphere in vacuum. The output is escaped-particle
response, not final detector deposited energy. FLUKA escape is scored at the
Cu-to-vacuum boundary; MEGAlib escape is parsed from fresh `IA ESCP` records
after vacuum flight.

Key smoke-statistics escape yields:

| family | metric | FLUKA | MEGAlib | FLUKA/MEGAlib | z approx |
|---|---|---:|---:|---:|---:|
| `cu64_eplus_smoke` | escaped W2 photon yield | `0.957031` | `0.984375` | `0.972222` | `-0.44` |
| `mono511_gamma` | escaped W2 photon yield | `0.451172` | `0.478516` | `0.942857` | `-0.64` |
| `pair511_gamma` | escaped W2 photon yield | `0.460938` | `0.513672` | `0.897338` | `-1.21` |
| `mono1779_gamma` | total escaped photon yield | `0.984375` | `0.984375` | `1.0` | `0.00` |
| `mono2754_gamma` | total escaped photon yield | `0.992188` | `1.039062` | `0.954887` | `-0.53` |

Interpretation: the smoke does not show a large 511-like source/escape
mismatch in a simple Cu sphere. It is not sufficient to close the delayed
residual, because common deposit-level truth, annihilation/stopping
observables, T2 Ta/TES deposition, and deterministic W2 response remain open.

## Phase-2 T2 Cu+Ta Absorber Smoke

The T2 smoke moves one step closer to the actual W2 observable: a 1 cm radius
Cu sphere plus one Ta absorber slab (`4.0 x 4.0 x 0.1 cm`) at `z = 3.0 cm`.
The Ta slab is deliberately larger than a physical TES pixel to get nonzero
smoke statistics from the `2048` common source rows. MEGAlib uses
`EnergyResolution Ideal`; FLUKA records raw Ta deposited energy.

Key Ta deposited-energy efficiencies:

| family | metric | FLUKA | MEGAlib | FLUKA/MEGAlib | z approx |
|---|---|---:|---:|---:|---:|
| `cu64_eplus_smoke` | W2 Ta deposit efficiency | `0.017578` | `0.0078125` | `2.25` | `1.39` |
| `cu64_eplus_smoke` | 480-550 keV Ta deposit efficiency | `0.019531` | `0.0078125` | `2.5` | `1.60` |
| `mono511_gamma` | W2 Ta deposit efficiency | `0.001953` | `0.001953` | `1.0` | `0.00` |
| `pair511_gamma` | W2 Ta deposit efficiency | `0.005859` | `0.003906` | `1.5` | `0.45` |

Interpretation: both engines now produce the same type of Ta deposited-energy
observable from the common source list. The low event counts mean this is not a
Phase-2 acceptance pass. Production T2 still needs agreed Ta/TES dimensions,
higher statistics, common ancestry/stopping observables, and deterministic
analytic W2 response.

## Phase-2 T2 Cu+Ta Production-Statistics Gate

The production-statistics generated-source T2 run repeats the same Cu+Ta toy
observable with `300000` common primaries: `100000` Cu-64 positron rows,
`100000` mono-511 photon rows, and `100000` back-to-back-pair photon rows.
Full input tables were dropped after hashing to avoid committing large
reproducible tables; the retained artifact keeps the source hash, bounded
sample, geometry/input decks, and compact summaries.

Key result: the low-statistics `2.25x` Cu-64 W2 smoke ratio does **not** persist.

| family | metric | FLUKA | MEGAlib | FLUKA/MEGAlib | z approx |
|---|---|---:|---:|---:|---:|
| `cu64_eplus_smoke` | W2 Ta deposit efficiency | `0.01132` (`1132/100000`) | `0.01100` (`1100/100000`) | `1.02909` | `0.68` |
| `cu64_eplus_smoke` | 480-550 keV Ta deposit efficiency | `0.01232` | `0.01212` | `1.01650` | `0.40` |
| `mono511_gamma` | W2 Ta deposit efficiency | `0.00551` | `0.00559` | `0.98569` | `-0.24` |
| `pair511_gamma` | W2 Ta deposit efficiency | `0.00545` | `0.00541` | `1.00739` | `0.12` |

Interpretation: the toy Cu+Ta W2 deposited-energy efficiency is closed at
production statistics for the 511-related generated sources. This rules out a
simple common-source Cu/Ta W2 EM transport or Ta-deposition mismatch as the
reason FLUKA's full-chain delayed W2 fraction is high. The remaining decisive
route is full-geometry common Cu-64 source positions, region/material audit,
raw deposits, common event building, and deterministic analytic W2 response.

## Phase-3 Cu-64 Common Positions

The Phase-3 source-position authority now exists at:

```text
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/cu64_common_positions.csv
```

It contains `6927` source-v2 Cu-64 positions (`Z=29`, `A=64`, `isomer=0`) with
total Cu-64 activity weight `4.701904943 Bq`. The source is almost entirely
neutron-produced (`6918` rows, `4.6958012557 Bq`), with small proton and
mu-minus tails. `source_material` is deliberately `PENDING_REGION_AUDIT`; this
file is the position/weight authority, not the geometry-material verdict.

The first Phase-3 source-region/material audit layer now passes at name level.
All `6927` Cu-64 `source_volume` rows map to translated FLUKA region/material
names in the geometry-translation table. The mapped activity is `93.75%`
`Copper` and `6.25%` `CuNi`. This removes the simple failure mode where the
Cu-64 source table points to unmapped FLUKA regions, but it does not yet prove
coordinate containment, nearest-boundary distance, or runtime point location in
Geant4/FLUKA. Those coordinate-level checks remain the next full-geometry gate.

The static coordinate-containment audit now also passes. The audit inverse-rotates
source-v2 coordinates by `InstrumentFrame.Rotation 0 45 0` into the
local frame used by the MEGAlib geometry parser and FLUKA translator; after that
transform, `6927/6927` Cu-64 points lie inside their declared `source_volume`,
and that source volume is the deepest translated object containing the point.
The deepest resolved material split is `6494` rows in `Copper` (`93.75%`
activity) and `433` rows in `CuNi` (`6.25%`). This is still a static translator
audit, not a runtime FLUKA/Geant4 point-location scorer.

The deterministic `1,000,000`-history Cu-64 parent resampling authority is also
built from the same `cu64_common_positions.csv`. It uses seed
`20260625_phase3_cu64`; the selected-index stream SHA256 is
`3be6695480c8b130ea9a396cbe34efdc47e97be4aa3575bcf4b2968be147a98e`, and the
full local list SHA256 is
`a2b5dbb883e49e16154290c0275561f41a6799f3753f4396262ad07f291a3975`. All
`6927` source rows are represented at least once; selected histories split into
`937427` `Copper` and `62573` `CuNi` parents. The full list is intentionally
ignored under `full_untracked/`; the repo keeps only compact summaries and a
bounded sample. Production-statistics transport has not yet been run from this
list.

## Phase-3 FLUKA Common Raw-Deposit Smoke

The first full-geometry raw-deposit plumbing smoke now runs on the FLUKA side
from the deterministic Cu-64 parent list, without `.sim.gz` replay:

```text
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/fluka_cu64_common_raw_smoke_1k/summary.md
```

It uses the first `1000` resampled Cu-64 parent histories and records raw
deposits plus event totals. The raw dump agrees with the FLUKA score output to
`1.337e-10` relative difference for TES energy and `2.282e-10` for shield
energy.

| band | events / histories | efficiency |
|---|---:|---:|
| all TES > 0 | `5 / 1000` | `0.005` |
| 480-550 keV | `2 / 1000` | `0.002` |
| W2 510.58-511.42 keV | `2 / 1000` | `0.002` |
| 1500-3000 keV | `0 / 1000` | `0.0` |
| 3000-10000 keV | `0 / 1000` | `0.0` |

Boundary: this is a FLUKA-only smoke-statistics check. It confirms the full
geometry can be driven by the independent Phase-3 Cu-64 parent stream and that
the raw-deposit scorer is internally closed. It does not yet answer the
FLUKA/TES delayed-W2 discrepancy; that still requires MEGAlib detector/readout
semantic calibration, production statistics, common event building, and
analytic W2 response.

## Phase-3 MEGAlib Common Raw-Hit Smoke

The MEGAlib side now also runs from the same deterministic Cu-64 parent list,
again without `.sim.gz` replay:

```text
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/megalib_cu64_common_raw_smoke_1k/summary.md
```

The corrected source uses `Run.Events 1000` and `PreTriggerMode Everything`,
so the denominator is simulated events, not requested triggered events. The
important parser correction is that native `HTsim` first field is the MEGAlib
detector type (`4 = Scintillator`, `2 = Calorimeter`), not the `.det`
detector-instance id. The previous `D4/TES_L3` interpretation was therefore a
semantic error. For FLUKA comparison, use the patched `CC HIT <volume>
edep_keV=...` volume-deposit truth.

| band | events / histories | efficiency |
|---|---:|---:|
| all TES > 0 | `3 / 1000` | `0.003` |
| 480-550 keV | `1 / 1000` | `0.001` |
| W2 510.58-511.42 keV | `1 / 1000` | `0.001` |
| 1500-3000 keV | `0 / 1000` | `0.0` |
| 3000-10000 keV | `0 / 1000` | `0.0` |

`CC HIT` TES particle/ancestry summary:

| TES local secondary | parent | creator/step process | histories | hit_rows | deposit_keV_sum |
|---|---|---|---:|---:|---:|
| `e-` | `gamma` | `phot -> eIoni` | `2` | `5` | `605.294` |
| `e-` | `gamma` | `compt -> eIoni` | `1` | `1` | `76.360` |
| `gamma` | `gamma` | `phot -> phot` | `2` | `2` | `23.312` |
| `gamma` | `e+` | `annihil -> phot` | `2` | `2` | `22.326` |
| `gamma` | `e+` | `annihil -> compt` | `1` | `1` | `0.0419` |

This answers the photon/electron concern. The dominant TES energy is deposited
locally by electrons, but those electrons are created by gamma photoelectric or
Compton interactions in the TES. Thus "electron" is a local carrier label, not a
statement that photon backgrounds are absent. The corrected MEGAlib `CC HIT`
volume-truth smoke is also qualitatively close to the FLUKA smoke at this
statistics level: FLUKA has `5/1000` any-TES and `2/1000` W2, while MEGAlib has
`3/1000` any-TES and `1/1000` W2. These counts are too small for a production
ratio, but they remove the false contradiction created by the old `1000/1000`
HTsim reading.

Boundary: this is still a smoke-statistics raw-deposit plumbing result, not a
delayed-W2 closure. Production-statistics full-geometry transport, common event
building, and deterministic analytic W2 response remain open.

Audit artifacts:

- `engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/geant4_megalib_vacuum_smoke/summary.md`
- `engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/fluka_vacuum_production/summary.md`
- `engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/crosscode_decay_kernel_line_comparison.csv`
- `engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t0_source_bookkeeping_smoke/summary.md`
- `engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t1_cu_sphere_transport_smoke/summary.md`
- `engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t2_cu_ta_absorber_transport_smoke/summary.md`
- `engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t2_cu_ta_absorber_transport_production_100k/summary.md`
- `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/summary.md`
- `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/source_region_material_name_audit.md`
- `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/source_coordinate_containment_audit.md`
- `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/cu64_parent_resampling_summary.md`
- `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/fluka_cu64_common_raw_smoke_1k/summary.md`
- `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/megalib_cu64_common_raw_smoke_1k/summary.md`

## Follow-Up Checks

The next targeted checks should focus on the remaining detector-coupled
composition questions:

1. Trace the `47` final W2 prompt `eplus` events back through SIM CC/IA records
   to determine where the 511-keV photons are produced and how they enter the
   TES/FoV.
2. Audit whether the prompt fullsphere/source-surface normalization and side
   acceptance are directly comparable to old `new_geo_re`.
3. Test a stricter multi-site/Compton-only variant separately from the current
   W2 final selection, since many public Compton-instrument conclusions depend
   on rejecting single-site events.
4. Keep reporting energy-band-specific activation fractions; do not quote the
   W2 `6.57%` delayed fraction as a global activation fraction.
5. Promote the now-passing T2 toy result into full-geometry common raw-deposit
   truth using the built Cu-64 common positions, region/material audit, MEGAlib
   detector/readout semantic calibration, common event builder, exact Ta/TES
   dimensions, and deterministic analytic W2 response.
