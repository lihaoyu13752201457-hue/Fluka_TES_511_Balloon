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

## Follow-Up Checks

The next targeted checks should focus on the prompt `eplus` W2 survivors:

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
