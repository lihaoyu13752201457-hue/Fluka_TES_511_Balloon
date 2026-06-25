# Phase-3 Cu-64 Common Time/Topology Event Builder

- status: `PHASE3_CU64_COMMON_TIME_TOPOLOGY_BUILDER_PASS`
- work_root: `/tmp/phase3prod`
- histories_per_code: `FLUKA 1000000; MEGAlib 1000000`
- active_veto_threshold_keV: `50.0`
- w2_sigma_keV: `0.14`

## Event Definitions

| event definition | rule |
|---|---|
| `parent` | `whole parent history; window=whole parent` |
| `within_1us` | `cluster from first deposit within 1 microsecond; window=1e-06 s` |
| `within_1ns` | `cluster from first deposit within 1 nanosecond; window=1e-09 s` |

## W2 Focus Comparison

| event definition | metric | stage | FLUKA sum_w / histories | MEGAlib sum_w / histories | FLUKA/MEGAlib | z |
|---|---|---|---:|---:|---:|---:|
| `parent` | `W2 510.58-511.42 keV` | `raw` | `1269 / 1000000` | `1008 / 1000000` | `1.25893` | `5.47` |
| `parent` | `W2 510.58-511.42 keV` | `active_veto` | `662 / 1000000` | `563 / 1000000` | `1.17584` | `2.83` |
| `parent` | `W2 analytic Gaussian expectation` | `raw` | `1265.99 / 1000000` | `1005.19 / 1000000` | `1.25946` | `5.48` |
| `parent` | `W2 analytic Gaussian expectation` | `active_veto` | `660.692 / 1000000` | `561.302 / 1000000` | `1.17707` | `2.85` |
| `within_1us` | `W2 510.58-511.42 keV` | `raw` | `1269 / 1000000` | `1008 / 1000000` | `1.25893` | `5.47` |
| `within_1us` | `W2 510.58-511.42 keV` | `active_veto` | `662 / 1000000` | `563 / 1000000` | `1.17584` | `2.83` |
| `within_1us` | `W2 analytic Gaussian expectation` | `raw` | `1265.99 / 1000000` | `1005.19 / 1000000` | `1.25946` | `5.48` |
| `within_1us` | `W2 analytic Gaussian expectation` | `active_veto` | `660.692 / 1000000` | `561.302 / 1000000` | `1.17707` | `2.85` |
| `within_1ns` | `W2 510.58-511.42 keV` | `raw` | `1269 / 1000000` | `1008 / 1000000` | `1.25893` | `5.47` |
| `within_1ns` | `W2 510.58-511.42 keV` | `active_veto` | `662 / 1000000` | `568 / 1000000` | `1.16549` | `2.68` |
| `within_1ns` | `W2 analytic Gaussian expectation` | `raw` | `1265.99 / 1000000` | `1005.19 / 1000000` | `1.25946` | `5.48` |
| `within_1ns` | `W2 analytic Gaussian expectation` | `active_veto` | `660.692 / 1000000` | `566.289 / 1000000` | `1.16671` | `2.7` |

## Time Split Summary

| code | event definition | detector parents | split parents | subevents | max subevents/parent |
|---|---|---:|---:|---:|---:|
| `fluka` | `parent` | `86695` | `0` | `86695` | `1` |
| `fluka` | `within_1us` | `86695` | `0` | `86695` | `1` |
| `fluka` | `within_1ns` | `86695` | `0` | `86695` | `1` |
| `megalib` | `parent` | `68643` | `0` | `68643` | `1` |
| `megalib` | `within_1us` | `68643` | `0` | `68643` | `1` |
| `megalib` | `within_1ns` | `68643` | `301` | `68944` | `2` |

## W2 TES/Shield Topology

| code | event definition | stage | selected events | single TES pixel | multi TES pixel | active shield touched | side shield touched |
|---|---|---|---:|---:|---:|---:|---:|
| `fluka` | `parent` | `active_veto` | `662` | `412` | `250` | `17` | `14` |
| `fluka` | `parent` | `raw` | `1269` | `767` | `502` | `624` | `434` |
| `fluka` | `within_1ns` | `active_veto` | `662` | `412` | `250` | `17` | `14` |
| `fluka` | `within_1ns` | `raw` | `1269` | `767` | `502` | `624` | `434` |
| `fluka` | `within_1us` | `active_veto` | `662` | `412` | `250` | `17` | `14` |
| `fluka` | `within_1us` | `raw` | `1269` | `767` | `502` | `624` | `434` |
| `megalib` | `parent` | `active_veto` | `563` | `342` | `221` | `10` | `8` |
| `megalib` | `parent` | `raw` | `1008` | `625` | `383` | `455` | `312` |
| `megalib` | `within_1ns` | `active_veto` | `568` | `344` | `224` | `11` | `9` |
| `megalib` | `within_1ns` | `raw` | `1008` | `625` | `383` | `451` | `308` |
| `megalib` | `within_1us` | `active_veto` | `563` | `342` | `221` | `10` | `8` |
| `megalib` | `within_1us` | `raw` | `1008` | `625` | `383` | `455` | `312` |

## Interpretation

- The common parent-history result is reproduced from raw detector rows, not from `.sim.gz` replay.
- The 1 microsecond clustering is effectively identical to whole-parent grouping for this Cu-64 delayed sample.
- The 1 nanosecond clustering changes only the MEGAlib side at a small level and does not remove the W2 raw excess.
- The output adds identical single/multi TES-pixel and active-shield-touch bookkeeping. It is not a FoV/reconstruction implementation.

## Output Files

- event_definition_stage_rows_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_common_event_builder_time_topology_1e6/event_definition_stage_rows.csv`
- comparison_stage_ratios_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_common_event_builder_time_topology_1e6/comparison_stage_ratios.csv`
- topology_summary_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_common_event_builder_time_topology_1e6/topology_summary.csv`
- time_split_summary_csv: `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_common_event_builder_time_topology_1e6/time_split_summary.csv`

## Boundary

- This is a common external event builder over existing raw detector deposits from the independent Cu-64 common-parent production.
- It does not replay Geant4 `.sim.gz` files.
- It does not implement the final side-Compton/FoV reconstruction cut; that remains an open final-selection layer.
