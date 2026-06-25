# Particle Coverage Audit - 2026-06-25

## Verdict

The prompt run is not limited to neutron/electron. All eight TES prompt primary species were run with independent FLUKA source sampling:

`alpha`, `eminus`, `eplus`, `gamma`, `muminus`, `muplus`, `n`, `p`.

The W2 final background composition is narrower because most species produce zero surviving W2 final events after the Step05 active-veto and side-Compton/FoV selection. That is a selection result, not missing transport.

## Prompt Coverage Evidence

Source mode: `sampled_source_authority`; no `.sim.gz` replay.

Artifact: `work_fluka_harness/prompt_final_same_stat_independent_source_20260625/summary.json`

| prompt species | FLUKA histories | valid chunks | source truth gate | W2 raw events | W2 final events | W2 final cps |
|---|---:|---:|---|---:|---:|---:|
| alpha | `191,464` | `8` | `PASS` | `0` | `0` | `0` |
| eminus | `3,316,936` | `32` | `PASS` | `0` | `0` | `0` |
| eplus | `1,949,816` | `24` | `PASS` | `47` | `41` | `0.027819943` |
| gamma | `10,000,000` | `40` | `PASS` | `1` | `0` | `0` |
| muminus | `82,824` | `8` | `PASS` | `1` | `0` | `0` |
| muplus | `92,840` | `8` | `PASS` | `6` | `0` | `0` |
| n | `7,704,528` | `32` | `PASS` | `126` | `6` | `0.004071218` |
| p | `1,871,808` | `24` | `PASS` | `0` | `0` | `0` |
| total | `25,210,216` | `176` | `8/8 PASS` | `181` | `47` | `0.031891161` |

Interpretation:

- `eplus` and `n` are the only nonzero FLUKA prompt contributors after W2 final selection.
- `gamma`, `muplus`, and `muminus` have W2 raw entries but are removed by later cuts.
- `alpha`, `eminus`, and `p` were still transported at full planned statistics; they simply have zero W2 entries in this final window/statistic.

## Delayed Coverage Evidence

Delayed source mode: `delayed_source_v2_weighted_exact_position_isotope_eventlist`; no `.sim.gz` replay.

Artifacts:

- `work_fluka_harness/delayed_isotope_source_full254704/summary.json`
- `work_fluka_harness/delayed_final_same_stat_isotope_source_full254704/summary.json`

Delayed source-v2 coverage:

| item | value |
|---|---:|
| isotope EventList rows run | `254,704` |
| represented activity | `86.999842067 Bq` |
| isotope-state species | `222` |
| isotope-volume keys | `1,456` |
| raw event rows | `209,200` |
| Step05 G4 validation | `PASS` |

Delayed production-tag rows in the source-v2 ledger:

| production tag | rows |
|---|---:|
| alpha | `142` |
| eplus | `4` |
| muminus | `4,404` |
| muplus | `12` |
| n | `248,506` |
| p | `1,636` |

Top delayed isotope rows by count:

| isotope | rows |
|---|---:|
| Cs-134 | `121,569` |
| I-128 | `96,546` |
| Al-28 | `10,150` |
| Cu-64 | `6,927` |
| Mg-27 | `3,328` |
| Cu-66 | `1,677` |
| W-187 | `1,450` |
| Al-26 | `1,379` |
| Nb-94 | `1,338` |
| Ta-182 | `1,318` |

W2 final delayed survivors in FLUKA are all `Cu-64`: `10` events, `0.006787802 cps`.
