# Engineering Completion Audit

Date: 2026-06-25

## Scope

This audit maps the remaining `engineering.md` checklist items to current
evidence. It does not claim that the physical raw-coupling mechanism is fully
identified. It only decides which checklist gates are complete, which
conditional gates are not triggered for the current manuscript/systematics
statement, and which diagnostics remain future work.

## Completed Evidence Gates

| gate | evidence | status |
|---|---|---|
| FLUKA runtime isotope identity | `00_manifest/fluka_source_identity_gate/summary.md` | complete |
| FLUKA vacuum decay-kernel production | `01_cu64_decay_kernel/fluka_vacuum_production/summary.md` | complete |
| Geant4/MEGAlib vacuum decay-kernel smoke | `01_cu64_decay_kernel/geant4_megalib_vacuum_smoke/summary.md` | complete |
| Phase-2 common-source EM toy transport | `02_common_em_transport/t2_cu_ta_absorber_transport_production_100k/summary.md` | complete |
| Phase-3 common Cu-64 positions/resampling | `03_full_geometry_same_source/summary.md` | complete |
| Phase-3 1e6 parent raw production | `03_full_geometry_same_source/phase3_cu64_common_raw_production_1e6/summary.md` | complete |
| Common parent-history response | `03_full_geometry_same_source/phase3_cu64_common_event_builder_parent_1e6/summary.md` | complete |
| Raw-coupling decomposition | `03_full_geometry_same_source/phase3_cu64_raw_coupling_decomposition_1e6/summary.md` | complete |
| Static boundary-margin audit | `03_full_geometry_same_source/phase3_cu64_boundary_margin_audit_1e6/summary.md` | complete |
| Common 1 us / 1 ns time-topology builder | `03_full_geometry_same_source/phase3_cu64_common_event_builder_time_topology_1e6/summary.md` | complete |
| Manuscript delayed-background statement | `05_decision/manuscript_delayed_background_statement.md` | complete |

## Conditional Gate Disposition

| checklist item | disposition | reason |
|---|---|---|
| Build Geant4/MEGAlib `1e6`/isotope production decay-kernel outputs if low-yield-line precision is needed | not triggered for current conclusion | The current W2 conclusion is limited by full-geometry raw coupling. The Geant4/MEGAlib smoke and FLUKA production gates already rule out total absence of the high-energy lines, and low-yield-line precision is not needed to support the current delayed-W2 raw-coupling/systematic statement. |
| Scan FLUKA effective EM cuts if full-geometry or ancestry observables reopen a W2 EM-transport discrepancy | not triggered | The Phase-2 generated-source Cu+Ta production gate closes the simple W2 EM-deposition toy benchmark. The full-geometry Phase-3 difference appears before common detector response, but no ancestry gate has yet pointed to an EM-cut/material threshold as the mechanism. |
| Runtime engine point-location audit in Geant4/FLUKA, if required before production transport | no longer required before production transport | Production transport has already run with a shared deterministic Cu-64 parent stream. Static name/coordinate containment and boundary-margin audits are complete; runtime point-location remains a future mechanism diagnostic, not a blocker for the current raw-coupling/systematic conclusion. |
| Add final side-Compton/FoV reconstruction cut if manuscript-level final selection is required | not triggered for current manuscript statement | The manuscript statement is explicitly a raw-coupling/systematic statement. Parent, 1 us, and 1 ns event grouping are complete, and the first failed phase is already before final FoV reconstruction. Final side-Compton/FoV reconstruction remains future work only for a final-selection-level cross-code claim. |

## Remaining Future Diagnostics

These are still useful for explaining the physical mechanism, but they are not
required to support the current repository conclusion:

- Runtime point-location inside dominant source volumes.
- Positron stopping/annihilation location.
- Incident TES ancestry.
- Final side-Compton/FoV reconstruction if a final-selection-level cross-code
  statement is later required.

## Completion Decision

For the current objective, the actionable `engineering.md` run has produced the
required independent-source cross-code evidence, removed the obsolete
`.sim.gz` replay path from the conclusion, documented the TES_511_BALLOON
comparison, and produced a manuscript-safe delayed-background statement. The
remaining mechanism diagnostics are explicitly future work rather than
blocking gates for the current systematic conclusion.
