# TES511 Independent-Source Background Composition - 2026-06-25

## Conclusion

The mainline comparison is now back on independent source reproduction, not `.sim.gz` replay.

- Prompt FLUKA: `25,210,216` histories, all eight prompt species, `176/176` valid chunks, `sampled_source_authority`.
- Delayed FLUKA: `254,704` isotope-source histories from TES delayed source-v2 EventList/weights, total represented activity `86.999842067 Bq`, no `.sim.gz` replay.
- Total FLUKA histories run for the closed prompt+delayed evidence: `25,464,920`.
- TES/G4 Step05 validation: prompt official CSV `PASS`; delayed official CSV `PASS`.

W2 final side-Compton/FoV total is close:

| code | prompt cps | delayed cps | total cps | prompt % | delayed % |
|---|---:|---:|---:|---:|---:|
| TES_511_BALLOON | `0.036641023` | `0.002575203` | `0.039216227` | `93.43%` | `6.57%` |
| FLUKA independent source | `0.031891161` | `0.006787802` | `0.038678963` | `82.45%` | `17.55%` |

Final W2 total ratio: `FLUKA/TES = 0.9863`.

Interpretation: the final W2 total agrees because two residuals partially
cancel. Prompt final is low (`0.870x` TES prompt), while delayed final is high
(`2.636x` TES delayed). Numerically, FLUKA prompt is lower than TES by
`0.004749862 cps`, while FLUKA delayed is higher than TES by
`0.004212598 cps`; only `0.000537263 cps` remains after summing. Do not claim
delayed composition agreement yet.

Manuscript treatment: report delayed activation as an unresolved cross-code
model systematic for this analysis. The W2 total agreement is useful as a
total-rate cross-check, but it should not be used as delayed-component
validation or as a reason to average the TES/MEGAlib and FLUKA delayed central
values. The full statement and claim boundary are in
`engineering/crosscode_delayed_closure_20260625/05_decision/manuscript_delayed_background_statement.md`.

## W2 Final Background Constituents

These constituents are source/stream tags. They are not the local particle
identity carrying the final TES energy deposit. The follow-up energy-band
audit shows W2 final FLUKA TES deposits are dominated by local electromagnetic
`EM_BELOW_THRESHOLD` deposit rows: see
`work_fluka_harness/fluka_11_like_energy_band_stats_20260625/summary.md`.

| source | TES events / cps / fraction | FLUKA events / cps / fraction |
|---|---:|---:|
| prompt eplus | `47 / 0.031889746 / 81.32%` | `41 / 0.027819943 / 71.93%` |
| prompt neutron | `7 / 0.004751277 / 12.12%` | `6 / 0.004071218 / 10.53%` |
| delayed activation | `30 / 0.002575203 / 6.57%` | `10 / 0.006787802 / 17.55%` |
| total | `84 / 0.039216227 / 100%` | `57 / 0.038678963 / 100%` |

FLUKA delayed W2 final survivors are all `Cu-64` in this run: `10` events, `0.006787802 cps`.

## Same-Statistic TES Comparison

Window: `510.58-511.42 keV`.

| stage | TES prompt cps | FLUKA prompt cps | prompt FL/TES | TES delayed cps | FLUKA delayed cps | delayed FL/TES | total FL/TES |
|---|---:|---:|---:|---:|---:|---:|---:|
| raw | `0.118771369` | `0.127564754` | `1.074` | `0.004635366` | `0.012227336` | `2.638` | `1.133` |
| active veto | `0.040712303` | `0.036640910` | `0.900` | `0.002832724` | `0.008145362` | `2.875` | `1.029` |
| side-Compton/FoV final | `0.036641023` | `0.031891161` | `0.870` | `0.002575203` | `0.006787802` | `2.636` | `0.986` |

## Artifacts

- Prompt final same-stat: `work_fluka_harness/prompt_final_same_stat_independent_source_20260625/summary.md`
- Delayed isotope source full run: `work_fluka_harness/delayed_isotope_source_full254704/summary.md`
- Delayed final same-stat: `work_fluka_harness/delayed_final_same_stat_isotope_source_full254704/summary.md`
- Particle coverage audit: `work_fluka_harness/particle_coverage_audit_20260625.md`
- Delayed source runner: `work_fluka_harness/run_delayed_isotope_raw_mvp.py`
- Delayed Step05 summarizer: `work_fluka_harness/build_delayed_final_same_stat_comparison.py`
- Terminal/process fix: `work_fluka_harness/run_eplus_equal_stat_chunks.py`
