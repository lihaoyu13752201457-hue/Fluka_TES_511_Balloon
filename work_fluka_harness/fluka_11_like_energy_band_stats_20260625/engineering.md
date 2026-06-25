# Geant4/MEGAlib–FLUKA Delayed-Background Closure Engineering Plan

**Project:** TES_511_BALLOON / Fluka_TES_511_Balloon  
**Date:** 2026-06-25  
**Status:** ACTIONABLE — designed to reach a discriminating conclusion quickly  
**Primary question:** Why is the FLUKA final delayed W2 rate higher than the Geant4/MEGAlib result?

---

## 0.0 Review amendments (2026-06-25 — read before §0)

This block records review corrections to the plan below. Where the plan names **`Cu-64`** as the Phase-1 / decay-kernel probe (§0, §5, §23, §26, §29), read it as the isotope set **`{Cu-64, Na-24, Al-28, I-128}`** unless a step is explicitly W2-only.

**A1 — Broaden the decay-kernel probe; Cu-64 alone cannot test the dominant discrepancy.**
The plan centers on Cu-64 because W2 delayed is Cu-64-dominated. But Cu-64 is gamma-poor (β⁺ 17.6% / EC 43.1% / β⁻ 39.0%; only a 1.346 MeV γ at 0.48%), so its decay kernel tests β⁺/EC branching and annihilation, **not** the γ cascade. The most statistically decisive cross-code discrepancy is **not** the W2 511 line but the **high-energy γ deficit**:

| band (final delayed) | G4 events | FLUKA/G4 rate |
|---|---:|---:|
| W2 511 | 30 | 2.64 (≈2σ, low stat) |
| 1500–3000 keV | **506** | **0.041** |
| 3000–10000 keV | **48** | **0.014** |

The 1.5–10 MeV bands are driven by **Na-24 (1.369+2.754 MeV coincident) and Al-28 (1.779 MeV)** — exactly the correlated cascades that the "FLUKA semi-analogue `RADDECAY` does not preserve correlated γ cascades" hypothesis predicts. A Cu-64-only Phase 1 will likely PASS and mis-route to Phase 2/3, missing the real cause. **Add Na-24 and Al-28 (cascade test) and I-128 (77% of the inventory).** Highest-value first run: a vacuum decay-kernel of **Na-24 / Al-28** asking *does each decay emit both high-energy γ lines?* — no geometry, directly confirms/refutes the leading hypothesis.

**A2 — Judge on the full spectrum, not W2 alone.** The W2 number is the least robust part (10 FLUKA / 30 G4 events, ≈2σ). The decision metric (§22, §24) must be the **per-band delayed spectrum and the high-energy deficit**, not the W2 rate in isolation. A clean Cu-64 W2 closure can stay statistically inconclusive while the real, high-significance signal sits at >1.5 MeV.

**A3 — Data trap in the current CSVs (dedup before re-quoting).** `source_stage_rows.csv` carries, per band/stage, **both** per-isotope rows **and** an `activation` aggregate equal to their sum (e.g. W2 final: `Cu-64 10` + `activation 10`). Summing all delayed tags double-counts the FLUKA side by ~2×. The §1 baseline (`10` events, `2.636×`) already uses the de-duplicated headline value and is correct; the common post-processor (§20) and any re-quote must use per-isotope **or** `activation`, never both. Corrected picture: FLUKA total delayed is **lower** overall (all-TES>0 ratio ≈ `0.573`), with relative weight tilted into 511 and the high-energy bands collapsed — i.e. "lower total + spectral tilt", not "same total, redistributed".

**A4 — Operational: parallelize Phase 3.** The `10⁶ × full-geometry` runs must use the parallel chunk driver, not the `--max-parallel 1` serial mode that previously serialized this project onto 1 of 24 cores and stalled. See `work_fluka_harness/NOTE_crosscode_independent_source_and_parallel_20260625.md`.

**A5 — Optional / framing.** (i) In Phase 2, add 1.779 and 2.754 MeV mono-γ to the common list, as insurance that high-energy γ *transport* (not just emission) agrees. (ii) Per harness §19.3, a cleanly-isolated ~1.5–2× decay-model difference may be an **irreducible model systematic, not a bug** — Outcomes A and F already allow this; do not tune it away.

---

## 0.1 Execution status (2026-06-25)

The first non-statistical gate has been run on the FLUKA side:

- Manifest freeze exists at `engineering/crosscode_delayed_closure_20260625/00_manifest/`.
- Source authority has `254704` heavy-isotope rows and `86.9998420669 Bq` total heavy delayed activity.
- FLUKA runtime source identity gate: `FLUKA_SOURCE_IDENTITY_GATE_PASS`.
- Gate histories: `Cu-64`, `Cu-62`, `I-128`, `Na-22`, `Na-24`, `Al-28` from the source-v2 EventList.
- FLUKA vacuum decay-kernel smoke: `FLUKA_DECAY_KERNEL_SMOKE_PASS` for `Cu-64`, `Na-24`, `Al-28`, `I-128` with `20000` parents per isotope.
- FLUKA vacuum decay-kernel production: `FLUKA_DECAY_KERNEL_PRODUCTION_PASS` for `Cu-64`, `Na-24`, `Al-28`, `I-128` with `1000000` parents per isotope.
- Geant4/MEGAlib independent EventList vacuum decay-kernel smoke:
  `GEANT4_MEGALIB_DECAY_KERNEL_SMOKE_PASS` for `Cu-64`, `Na-24`,
  `Al-28`, `I-128` with `20000` parents per isotope.
- Phase-3 FLUKA-only common Cu-64 raw-deposit smoke:
  `PHASE3_CU64_COMMON_FLUKA_RAW_PASS` for `1000` histories from the
  deterministic parent list, without `.sim.gz` replay.
- Phase-3 MEGAlib-only common Cu-64 raw-hit smoke:
  `PHASE3_CU64_COMMON_MEGALIB_RAW_PASS` for `1000` simulated events from the
  same deterministic parent list, without `.sim.gz` replay. HTsim semantic
  calibration shows the first HTsim field is a MEGAlib detector type, not a
  `.det` detector-instance id; comparable TES/W2 counts now come from `CC HIT`
  volume-deposit truth.

Runtime identity table:

| nuclide | event_id | expected Z/A/isomer | runtime Z/A/isomer | result |
|---|---:|---:|---:|---|
| Cu-64 | 153 | 29/64/0 | 29/64/0 | PASS |
| Cu-62 | 7 | 29/62/0 | 29/62/0 | PASS |
| I-128 | 16 | 53/128/0 | 53/128/0 | PASS |
| Na-22 | 62 | 11/22/0 | 11/22/0 | PASS |
| Na-24 | 72 | 11/24/0 | 11/24/0 | PASS |
| Al-28 | 65 | 13/28/0 | 13/28/0 | PASS |

Interpretation: the production-style dummy `HI-PROPE 53 128` card is not the cause of the delayed discrepancy for these checked histories. The source routine overrides the dummy isotope before `set_primary`, and FLUKA receives the source-v2 Z/A/isomer. Therefore the next discriminating target remains the decay-kernel / emitted-particle spectrum, especially the `Na-24` and `Al-28` high-energy correlated gamma cascades.

FLUKA-side Phase-1 smoke result:

| nuclide | FLUKA smoke metric | value |
|---|---|---:|
| Cu-64 | positron yield / parent | `0.1778` |
| Cu-64 | 1346-keV gamma yield / parent | `0.0047` |
| Na-24 | 1369-keV gamma yield / parent | `0.9999` |
| Na-24 | 2754-keV gamma yield / parent | `0.99855` |
| Na-24 | same-parent 1369+2754 coincidence fraction | `0.99855` |
| Al-28 | 1779-keV gamma yield / parent | `1.0` |
| I-128 | photon yield / parent | `0.2038` |

FLUKA-side Phase-1 production result (`1e6` parents/isotope):

| nuclide | FLUKA production metric | value |
|---|---|---:|
| Cu-64 | positron yield / parent | `0.176483` |
| Cu-64 | 1346-keV gamma yield / parent | `0.004785` |
| Na-24 | 1369-keV gamma yield / parent | `0.999939` |
| Na-24 | 2754-keV gamma yield / parent | `0.998547` |
| Na-24 | same-parent 1369+2754 coincidence fraction | `0.998547` |
| Al-28 | 1779-keV gamma yield / parent | `1.0` |
| I-128 | photon yield / parent | `0.199216` |

Interpretation of the FLUKA-side result: FLUKA `RADDECAY` does emit the high-energy `Na-24` and `Al-28` gamma lines in this vacuum scorer, and the `Na-24` two-line coincidence appears in essentially every decay. Therefore the earlier high-energy FLUKA/TES deficit is **not explained by total absence of these FLUKA gamma lines**. The remaining possibilities include Geant4-side decay-kernel differences, common emitted-particle transport, geometry/source-position coupling, or common-postprocessing effects.

Geant4/MEGAlib-side Phase-1 smoke result (`2e4` parents/isotope):

| nuclide | G4/MEGAlib smoke metric | value |
|---|---|---:|
| Cu-64 | positron yield / parent | `0.1767` |
| Cu-64 | 1346-keV gamma yield / parent | `0.0043` |
| Na-24 | 1369-keV gamma yield / parent | `0.99995` |
| Na-24 | 2754-keV gamma yield / parent | `0.9988` |
| Na-24 | same-parent 1369+2754 coincidence fraction | `0.9988` |
| Al-28 | 1779-keV gamma yield / parent | `1.0` |
| I-128 | photon yield / parent | `0.20605` |

Cross-code interpretation after the G4/MEGAlib smoke: both installed decay
engines emit the high-energy `Na-24` and `Al-28` gamma lines at approximately
unit yield, and Cu-64 beta-plus yield is consistent (`0.1767` G4/MEGAlib smoke
vs `0.176483` FLUKA production). Therefore the leading full-chain discrepancy
is **not** explained by either code completely omitting those decay photons.

This does **not** complete the cross-code closure. The Geant4/MEGAlib side is
smoke-statistics only, and the common emitted-particle list, common EM
transport test, full-geometry source/material coupling, and common
postprocessor are still open.

Detailed artifacts:

```text
engineering/crosscode_delayed_closure_20260625/00_manifest/summary.md
engineering/crosscode_delayed_closure_20260625/00_manifest/fluka_source_identity_gate/summary.md
engineering/crosscode_delayed_closure_20260625/00_manifest/fluka_source_identity_gate/runtime_identity_validation.csv
engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/fluka_vacuum_smoke/summary.md
engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/fluka_vacuum_smoke/gamma_line_yields.csv
engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/fluka_vacuum_smoke/particle_yields.csv
engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/fluka_vacuum_production/summary.md
engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/fluka_vacuum_production/gamma_line_yields.csv
engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/fluka_vacuum_production/particle_yields.csv
engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/geant4_megalib_vacuum_smoke/summary.md
engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/geant4_megalib_vacuum_smoke/gamma_line_yields.csv
engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/geant4_megalib_vacuum_smoke/particle_yields.csv
engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/crosscode_decay_kernel_line_comparison.csv
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/fluka_cu64_common_raw_smoke_1k/summary.md
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/megalib_cu64_common_raw_smoke_1k/summary.md
engineering/crosscode_delayed_closure_20260625/05_decision/crosscode_decision.md
```

---

## 0. Executive answer: the fastest path

Do **not** rerun the complete prompt + activation chain first. The discrepancy is already localized to delayed Cu activation near 511 keV, especially `Cu-64`.

The fastest discriminating sequence is:

1. **Run a Cu-64 decay-kernel benchmark in both codes** with no detector geometry.
2. **Run an identical externally generated positron/photon list through a tiny common Cu/TES toy geometry.**
3. **Run the exact same Cu-64 position list through the full geometry in both codes**, with detector response and event construction moved to one common Python post-processor.

Each stage has a stop rule. The first stage where the codes diverge identifies the problem class:

| First stage showing a significant discrepancy | Most likely cause |
|---|---|
| Cu-64 decay kernel | decay database, decay branching, isomer handling, RDM/RADDECAY implementation |
| Toy positron/511 transport | positron slowing, annihilation model, atomic de-excitation, EM cuts |
| Full-geometry raw deposits | coordinate mapping, materials, regions, geometry, production-position source |
| Raw deposits agree but veto differs | shield scorer, threshold, hit retention, timing |
| Veto agrees but final W2 differs | event grouping, TES response, smearing, topology/FoV post-processing |
| All per-decay efficiencies agree but physical rates differ | activity/source weights and source authority |

**Recommended first production run:** `10^6` Cu-64 decays per code. Based on the presently observed coupling, this should produce hundreds to more than one thousand W2 events and reduce the present 10-event FLUKA ambiguity. **(See §0.0-A1: the decay kernel must also run `Na-24`, `Al-28` and `I-128`. Cu-64 is gamma-poor and cannot test the high-energy γ-cascade deficit, which is the most statistically significant discrepancy.)**

---

## 1. Current numerical authority

Use the following as the immutable pre-test baseline:

| Quantity | Geant4/MEGAlib | FLUKA |
|---|---:|---:|
| Final prompt W2 rate | `0.036641023 s^-1` | `0.031891161 s^-1` |
| Final delayed W2 rate | `0.00257520349 s^-1` | `0.00678780176 s^-1` |
| Delayed fraction | `6.57%` | `17.55%` |
| Final delayed W2 events | `30` | `10` |
| Final Cu-64 contribution | `24 events / 0.00206016279 s^-1` | `10 events / 0.00678780176 s^-1` |

The total W2 rates agree only because the prompt and delayed residuals compensate. Do not use total-rate agreement as a validation gate.

### Current evidence paths

TES repository:

```text
core_md/fix5_benchmarks.json
outputs/reports/fix5_fullstat_v2_exactpos_m50000_s260613/
stepwise_maintenance/step05_veto_time_axis/
engineering/delayed_source_authority_v2_20260624/
```

FLUKA repository:

```text
work_fluka_harness/run_delayed_isotope_raw_mvp.py
work_fluka_harness/fluka_11_like_energy_band_stats_20260625/summary.md
work_fluka_harness/fluka_11_like_energy_band_stats_20260625/summary.json
work_fluka_harness/fluka_11_like_energy_band_stats_20260625/source_stage_rows.csv
work_fluka_harness/fluka_11_like_energy_band_stats_20260625/tes_deposit_carrier_rows.csv
```

---

## 2. Definition of done

A conclusion is considered closed when all of the following are true:

- both codes use the **same isotope, state, positions, and statistical weights**;
- detector smearing and event construction are applied by the **same external post-processor**;
- each code has at least `300` final Cu-64 W2 events, or weighted relative MC uncertainty below `10%`;
- the result is repeated with at least three seeds or deterministic source partitions;
- all rates include `sum_w`, `sum_w2`, and effective sample size;
- software versions and nuclear/EM data packages are fingerprinted;
- the conclusion is assigned to one of the six problem classes in the decision table above.

For publication-grade closure, target at least `1000` final W2 events per code or a ratio uncertainty below `5%`.

---

## 3. Work directory and provenance freeze

Create one new tracked directory in each repository:

```text
engineering/crosscode_delayed_closure_20260625/
├── 00_manifest/
├── 01_cu64_decay_kernel/
├── 02_common_em_transport/
├── 03_full_geometry_same_source/
├── 04_common_postprocess/
└── 05_decision/
```

Before running anything, write:

```text
00_manifest/environment_g4.json
00_manifest/environment_fluka.json
00_manifest/source_authority.json
00_manifest/file_hashes.sha256
```

### Required Geant4/MEGAlib fingerprint

Record at minimum:

```text
Geant4 version and patch
MEGAlib/Cosima commit
physics list
G4RADIOACTIVEDATA path/version/hash
G4LEVELGAMMADATA path/version/hash
G4ENSDFSTATEDATA path/version/hash
G4LEDATA or G4EMLOW path/version/hash
production cuts
atomic de-excitation settings
fluorescence/Auger/PIXE settings
radioactive-decay settings
custom isotope/position hook commit
compiler and build flags
```

### Required FLUKA fingerprint

Record at minimum:

```text
FLUKA version shown in the output header
executable hash
source_delayed_isotope.f hash
mgdraw_raw.f hash
DEFAULTS card
RADDECAY card
EMFCUT cards and effective cutoffs from the .out file
PRECISIO/EM-CASCA choice
isotope Z/A/isomer values seen by the source routine
compiler/linker command
```

### Immediate source-identity gate

The current FLUKA input contains a dummy `HI-PROPE 53 128` entry that should be overridden by the source routine. Add a diagnostic line after source assignment and verify actual `Z`, `A`, and `isomer` for at least:

```text
Cu-64
Cu-62
I-128
Na-22
```

**Stop immediately** if the kernel identity does not match the ledger identity.

---

# Phase 1 — Cu-64 decay-kernel benchmark

## 4. Purpose

Determine whether the codes disagree before geometry or electromagnetic transport matters.

This is the quickest way to distinguish a nuclear-decay/database problem from a geometry/transport problem.

## 5. Configuration

Run `10^6` parents at rest in a vacuum world, **per isotope, for `{Cu-64, Na-24, Al-28, I-128}`** (see §0.0-A1). Cu-64 fixes the 511/β⁺ channel; **Na-24 (1.369+2.754 MeV) and Al-28 (1.779 MeV) test the high-energy correlated γ cascade that drives the most significant discrepancy**; I-128 is 77% of the inventory. Do not use detector smearing, veto, or event selection.

Record every emitted particle crossing a small scoring sphere around the source, before it interacts with detector material.

### Required output schema

```text
event_id
parent_Z
parent_A
parent_isomer
particle_id
kinetic_energy_keV
time_s
direction_x
direction_y
direction_z
creator_process
parent_track_id
track_id
```

If full ancestry is inconvenient in FLUKA, the minimum acceptable output is per-parent emitted-particle multiplicity and energy spectrum.

## 6. Metrics

Calculate per parent decay:

```text
P(beta+)
P(beta-)
P(EC)
mean positrons per parent
positron kinetic-energy spectrum
mean prompt photons per parent
nuclear gamma line yields
X-ray/Auger yields
mean emitted electromagnetic energy
fraction of events with correlated gamma emission
emission-time distribution
```

Do not start with the W2 window here. This stage is about source physics, not detector response.

## 7. Acceptance criteria

Use both statistical and practical thresholds:

```text
branching/yield relative difference <= 3%: PASS
3%–10%: WARN and inspect data versions
>10% or >5 sigma: FAIL — decay-engine/database discrepancy
```

For the Cu-64 beta-plus branch, `10^6` parents makes statistical uncertainty much smaller than the present cross-code W2 discrepancy.

## 8. Decision after Phase 1

### If Phase 1 fails

Do not run the full geometry yet. Inspect:

Geant4 side:

```text
G4RadioactiveDecay
G4BetaPlusDecay
G4ECDecay
G4PhotonEvaporation
G4UAtomicDeexcitation
ENSDF-derived radioactive-decay files
nuclear-level data files
```

FLUKA side:

```text
RADDECAY mode
isotope/source identity
semi-analogue decay treatment
decay database bundled with the installed FLUKA release
isomer state handling
```

Also compare against an external evaluated Cu-64 decay table. The goal is not to choose a winner by reputation; it is to determine which code reproduces the evaluated branch and gamma yields.

### If Phase 1 passes

Proceed immediately to Phase 2. The discrepancy is not primarily the Cu-64 decay branching/database.

---

# Phase 2 — Common electromagnetic transport benchmark

## 9. Purpose

Isolate positron slowing, annihilation, photon escape, atomic relaxation, and EM cutoff behavior.

## 10. Use an external code-neutral primary list

Generate one shared CSV or HDF5 file outside both transport codes. Use a fixed seed and store every primary explicitly.

Recommended samples:

```text
A. 1e6 monoenergetic 511 keV photons
B. 1e6 back-to-back 511 keV photon pairs
C. 1e6 positrons sampled from one frozen Cu-64 beta-plus spectrum
D. optional: Cu-64 decay products exported from the Phase-1 evaluated/reference generator
```

Both codes must read the same rows. No independent random resampling is allowed at source level.

## 11. Toy geometries

Run in this order:

### Geometry T0 — vacuum sphere

Purpose: verify source direction, energy, count, and weight bookkeeping.

### Geometry T1 — homogeneous Cu stopping sphere/slab

Purpose: compare positron range, annihilation location, annihilation-in-flight fraction, and escaped 511 photons.

### Geometry T2 — minimal Cu support + one Ta TES absorber

Purpose: compare the probability that escaped annihilation photons deposit 480–550 keV and W2 energy in Ta.

Keep geometry dimensions and material compositions explicitly identical.

## 12. Required observables

```text
positron stopping-distance distribution
annihilation position distribution
annihilation-in-flight fraction
escaped 511-photon yield per positron
escaped photon energy and angle
TES raw deposited-energy spectrum
single-pixel and multi-pixel multiplicity
shield-free W2 efficiency
```

## 13. FLUKA-specific scan

Because the current W2 deposits are dominated by `EM_BELOW_THRESHOLD`, run at least:

```text
EM-CASCA + current effective cuts
PRECISIO + current effective cuts
PRECISIO + 1 keV electron/photon cuts
PRECISIO + 10 keV electron/photon cuts
PRECISIO + 100 keV diagnostic cuts
```

Read the actual effective cuts from the FLUKA output file; do not infer them only from the input card.

## 14. Acceptance criteria

For T0:

```text
source count, direction, and energy closure: < 0.1%
```

For T1/T2:

```text
broad spectral integral difference <= 5%: PASS
W2 efficiency difference <= 10%: provisional PASS
>20% and >5 sigma: FAIL — EM transport/cut discrepancy
```

### 14.1 T0 source-bookkeeping status, 2026-06-25

The first Phase-2 gate is complete:

```text
engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t0_source_bookkeeping_smoke/summary.md
```

It uses one explicit common primary table with `2048` rows: `512` mono
511-keV photons, `256` back-to-back 511-keV pairs represented as `512`
primary rows with retained `pair_id`, `256` 1779-keV photons, `256`
2754-keV photons, and `512` Cu-64 positron smoke rows. Both FLUKA and
MEGAlib read this same list without source-level resampling.

Result:

| code | observed / expected | max energy relative delta | max direction 1-dot | status |
|---|---:|---:|---:|---|
| FLUKA | `2048 / 2048` | `4.1880789907739405e-09` | `1.1102230246251565e-16` | PASS |
| MEGAlib | `2048 / 2048` | `5.2968580495807746e-05` | `3.354161393076538e-11` | PASS |

This only closes source bookkeeping for count, particle code, kinetic energy,
direction, and weight. It does **not** yet close positron slowing,
annihilation, photon escape, Cu/Ta transport, or W2/TES deposition efficiency.

### 14.2 T1 Cu-sphere transport smoke status, 2026-06-25

The first T1 smoke is complete:

```text
engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t1_cu_sphere_transport_smoke/summary.md
```

It reuses the T0 `2048`-row common primary table in a homogeneous 1 cm radius
Cu sphere in vacuum. The smoke compares escaped-particle response, especially
511-like photons. FLUKA escape is scored at the Cu-to-vacuum boundary; MEGAlib
escape is parsed from fresh `IA ESCP` records after vacuum flight.

Key escaped-photon yields:

| family | metric | FLUKA | MEGAlib | FLUKA/MEGAlib | z approx |
|---|---|---:|---:|---:|---:|
| `cu64_eplus_smoke` | escaped W2 photon yield | `0.957031` | `0.984375` | `0.972222` | `-0.44` |
| `mono511_gamma` | escaped W2 photon yield | `0.451172` | `0.478516` | `0.942857` | `-0.64` |
| `pair511_gamma` | escaped W2 photon yield | `0.460938` | `0.513672` | `0.897338` | `-1.21` |
| `mono1779_gamma` | total escaped photon yield | `0.984375` | `0.984375` | `1.0` | `0.00` |
| `mono2754_gamma` | total escaped photon yield | `0.992188` | `1.039062` | `0.954887` | `-0.53` |

This is still a smoke, not final Phase-2 closure. MEGAlib deposit-level truth,
annihilation/stopping observables, T2 Ta/TES deposition, and deterministic W2
response remain open.

### 14.3 T2 Cu+Ta absorber smoke status, 2026-06-25

The first T2 smoke is complete:

```text
engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t2_cu_ta_absorber_transport_smoke/summary.md
```

It reuses the T0 `2048`-row common primary table in a smoke geometry:
1 cm radius Cu sphere plus a single Ta slab (`4.0 x 4.0 x 0.1 cm`) at
`z = 3.0 cm`. The Ta slab is intentionally larger than a physical TES pixel
to get nonzero hit statistics. MEGAlib uses `EnergyResolution Ideal`; FLUKA
records raw Ta deposited energy.

Key Ta deposited-energy efficiencies:

| family | metric | FLUKA | MEGAlib | FLUKA/MEGAlib | z approx |
|---|---|---:|---:|---:|---:|
| `cu64_eplus_smoke` | W2 Ta deposit efficiency | `0.017578` | `0.0078125` | `2.25` | `1.39` |
| `cu64_eplus_smoke` | 480-550 keV Ta deposit efficiency | `0.019531` | `0.0078125` | `2.5` | `1.60` |
| `mono511_gamma` | W2 Ta deposit efficiency | `0.001953` | `0.001953` | `1.0` | `0.00` |
| `pair511_gamma` | W2 Ta deposit efficiency | `0.005859` | `0.003906` | `1.5` | `0.45` |

This is still a low-statistics smoke. It proves the shared T2 machinery runs
and produces Ta deposit truth in both engines, but it does not yet satisfy the
Phase-2 acceptance criteria for W2 efficiency.

### 14.4 T2 Cu+Ta production-statistics status, 2026-06-25

The generated-source T2 production-statistics gate is complete:

```text
engineering/crosscode_delayed_closure_20260625/02_common_em_transport/t2_cu_ta_absorber_transport_production_100k/summary.md
```

It uses the same 1 cm radius Cu sphere plus deliberately enlarged Ta slab
(`4.0 x 4.0 x 0.1 cm` at `z = 3.0 cm`), but raises the 511-related common
source list to `300000` rows: `100000` Cu-64 positrons, `100000` mono-511
photons, and `100000` pair-511 photon rows. Full input tables were dropped
after hashing to avoid retaining large reproducible tables; the retained
artifact keeps the hash, bounded source sample, input decks, and compact
summaries.

Key Ta deposited-energy efficiencies:

| family | metric | FLUKA | MEGAlib | FLUKA/MEGAlib | z approx |
|---|---|---:|---:|---:|---:|
| `cu64_eplus_smoke` | W2 Ta deposit efficiency | `0.01132` | `0.01100` | `1.02909` | `0.68` |
| `cu64_eplus_smoke` | 480-550 keV Ta deposit efficiency | `0.01232` | `0.01212` | `1.01650` | `0.40` |
| `mono511_gamma` | W2 Ta deposit efficiency | `0.00551` | `0.00559` | `0.98569` | `-0.24` |
| `pair511_gamma` | W2 Ta deposit efficiency | `0.00545` | `0.00541` | `1.00739` | `0.12` |

This passes the Phase-2 toy W2/broad deposited-energy acceptance threshold for
the 511-related generated sources. The low-statistics T2 smoke's `2.25x`
Cu-64 W2 central value was a count fluctuation, not a stable production result.
The full-chain delayed W2 excess is therefore not explained by a simple
common-source Cu+Ta W2 EM transport/deposition mismatch in this toy geometry.

Remaining Phase-2 caveat: this is still a toy geometry with an enlarged Ta
absorber and without common annihilation/stopping ancestry. The next decisive
step is Phase 3: common full-geometry Cu-64 source positions, source
region/material audit, raw deposits, common event builder, and analytic W2
response.

## 15. Decision after Phase 2

- Phase 1 passes, Phase 2 fails: focus on positron transport, annihilation, atomic de-excitation, and EM thresholds.
- Both phases pass: proceed to full-geometry source/region mapping.

---

# Phase 3 — Full geometry with exactly the same Cu-64 source

## 16. Purpose

Remove the current ambiguity caused by comparing a legacy sampled MEGAlib source with a deterministic FLUKA EventList.

## 17. Build one common Cu-64 position authority

From the source-v2 production-position table, select only Cu-64 rows and create:

```text
03_full_geometry_same_source/cu64_common_positions.csv
```

Schema:

```text
common_event_id
Z
A
isomer
x_cm
y_cm
z_cm
source_volume
source_material
original_activity_weight_Bq
sampling_probability
```

Generate a deterministic diagnostic list of `10^6` Cu-64 parents by weighted resampling from this table. Save the actual selected source-row index for every history.

### 17.1 Cu-64 common position authority status, 2026-06-25

The Phase-3 Cu-64 source-position authority is built:

```text
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/cu64_common_positions.csv
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/summary.md
```

It filters the source-v2 delayed position-weight table to Cu-64 and produces
`6927` common position rows with `Z=29`, `A=64`, `isomer=0`. The total Cu-64
activity weight represented by these rows is:

```text
4.7019049431490107524463624743796 Bq
```

The Cu-64 source is dominated by neutron production:

| production_tag | rows | activity weight |
|---|---:|---:|
| `n` | `6918` | `4.695801255687516606153413823323 Bq` |
| `p` | `8` | `0.0054283622268401050116675860957 Bq` |
| `muminus` | `1` | `0.0006753252346540412812810649609 Bq` |

The largest source volumes by Cu-64 activity are `ColdPlate_4K` (`39.14%`),
`ColdPlate_Still_0p7K` (`18.97%`), `ColdPlate_CP_100mK_intercept` (`9.60%`),
and `ColdPlate_MXC_50mK_SD_anchor` (`8.43%`). `source_material` is deliberately
set to `PENDING_REGION_AUDIT`, because material must be resolved separately in
both full geometries rather than inferred from source-v2 reporting names.

Phase-3 source mapping now has two completed layers: name-level region/material
translation and static coordinate containment against the MEGAlib-authority
geometry as parsed by the FLUKA translator. The remaining pre-transport locator
gap is runtime point location inside the engines.

### Two required modes

1. **Unit-weight diagnostic mode**  
   Every generated Cu-64 parent has equal diagnostic weight. Use this for comparing per-decay efficiency.

2. **Physical-weight mode**  
   Apply the original activity weights only after per-decay closure is established.

The first comparison must be an efficiency comparison, not a physical-rate comparison:


display math block:

P(W2 | Cu-64 decay, common source positions)

### 17.2 Deterministic Cu-64 parent resampling status, 2026-06-25

The Phase-3 diagnostic parent list is built reproducibly:

```text
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/cu64_parent_resampling_summary.md
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/cu64_parent_resampling_summary.json
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/cu64_parent_resampling_sample.csv
```

It draws `1,000,000` Cu-64 parent histories from `cu64_common_positions.csv`
using the normalized `sampling_probability` column and a counter-based SHA256
random stream:

```text
seed: 20260625_phase3_cu64
selection_stream_sha256: 3be6695480c8b130ea9a396cbe34efdc47e97be4aa3575bcf4b2968be147a98e
full_list_csv_sha256: a2b5dbb883e49e16154290c0275561f41a6799f3753f4396262ad07f291a3975
```

The full selected-index list exists locally at:

```text
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/full_untracked/cu64_parent_resampling_1e6.csv
```

That file is intentionally ignored by git (`268 MB` locally); the repository
keeps only the hash, bounded sample, and summaries. All `6927` source-position
rows are represented at least once in the 1e6 parent list. The selected-history
material split is `937427` `Copper` parents and `62573` `CuNi` parents. No
production-statistics FLUKA/MEGAlib transport has been run by this resampling
gate.

### 17.3 FLUKA common raw-deposit smoke status, 2026-06-25

The first Phase-3 full-geometry raw-deposit plumbing smoke has run on the FLUKA
side from the deterministic Cu-64 parent list:

```text
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/fluka_cu64_common_raw_smoke_1k/summary.md
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/fluka_cu64_common_raw_smoke_1k/band_summary.csv
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/fluka_cu64_common_raw_smoke_1k/scoring_closure.json
```

It uses the first `1000` resampled Cu-64 parent histories and does not replay a
Geant4 `.sim.gz` file. The raw dump closes against the FLUKA score output:
TES relative delta `1.337e-10`, shield relative delta `2.282e-10`.

Smoke-statistics band counts:

| band | events / histories | efficiency |
|---|---:|---:|
| all TES > 0 | `5 / 1000` | `0.005` |
| 480-550 keV | `2 / 1000` | `0.002` |
| W2 510.58-511.42 keV | `2 / 1000` | `0.002` |
| 1500-3000 keV | `0 / 1000` | `0.0` |
| 3000-10000 keV | `0 / 1000` | `0.0` |

This is a FLUKA-side runner/scorer closure only. It does not replace the
required production-statistics FLUKA/MEGAlib raw-deposit comparison, common
event builder, or analytic W2 response.

### 17.4 MEGAlib common raw-hit smoke status, 2026-06-25

The matching Phase-3 MEGAlib raw-hit plumbing smoke now also runs directly
from the deterministic Cu-64 parent list:

```text
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/megalib_cu64_common_raw_smoke_1k/summary.md
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/megalib_cu64_common_raw_smoke_1k/cc_band_summary.csv
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/megalib_cu64_common_raw_smoke_1k/cc_tes_hit_sample.csv
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/megalib_cu64_common_raw_smoke_1k/cc_tes_particle_summary.csv
```

It uses `Run.Events 1000` and `PreTriggerMode Everything`, so the denominator
is simulated events rather than requested triggered events. The source is the
same parent-resampling authority and is not a `.sim.gz` replay.

The important semantic correction is now closed: MEGAlib `HTsim` first field is
the detector type written by `MSimHT::ToSimString` (`4 = Scintillator`,
`2 = Calorimeter`), not the `.det` detector-instance id. The previous
`D4/TES_L3` interpretation was therefore a parser mistake. The comparable
raw-deposit schema for this smoke is the patched `CC HIT <volume>
edep_keV=...` comment stream.

Smoke-statistics `CC HIT` volume-truth band counts:

| band | events / histories | efficiency |
|---|---:|---:|
| all TES > 0 | `3 / 1000` | `0.003` |
| 480-550 keV | `1 / 1000` | `0.001` |
| W2 510.58-511.42 keV | `1 / 1000` | `0.001` |
| 1500-3000 keV | `0 / 1000` | `0.0` |
| 3000-10000 keV | `0 / 1000` | `0.0` |

The same run records `6477` `CC HIT` rows, of which only `11` are in
`TES_PIXEL` volumes. Those `11` TES rows belong to three histories. Their
particle/ancestry split answers the photon-carrier concern directly: most TES
energy is deposited locally by `e-` secondaries, but those electrons are produced
by gamma `phot`/`compt` interactions in the TES; smaller rows are direct gamma
photoelectric/Compton deposits. In other words, "electron" is the local
depositing carrier, not evidence that photons are absent from the TES ancestry.

Native HTsim is retained only as a MEGAlib detector-type/readout diagnostic:
detector type `4` (`Scintillator`) has `1000` histories and `1349` rows, and
detector type `2` (`Calorimeter`) has `3` histories and `3` rows. These are not
`.det` detector ids and must not be ratioed against FLUKA raw-deposit counts.
At smoke statistics, the comparable FLUKA and MEGAlib raw-deposit counts are
close but far too small to interpret as a production efficiency result:
FLUKA `5/1000` any-TES and `2/1000` W2 versus MEGAlib `3/1000` any-TES and
`1/1000` W2.

### 17.5 Phase-3 Cu-64 production raw-deposit gate, 2026-06-25

The Phase-3 common Cu-64 parent stream has now been run at production
statistics in both codes:

```text
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_common_raw_production_1e6/summary.md
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_common_event_builder_parent_1e6/summary.md
```

This is still an independent-source run. It does not replay a Geant4
`.sim.gz`; both codes consume the same deterministic 1,000,000-parent Cu-64
selected-index authority, with full raw truth retained locally under
`/tmp/phase3prod` and only bounded summaries committed.

Raw parent-history TES coupling:

| band | FLUKA events / histories | MEGAlib events / histories | FLUKA/MEGAlib | z |
|---|---:|---:|---:|---:|
| all TES > 0 | `6566 / 1000000` | `2797 / 1000000` | `2.34752` | `39.1` |
| 480-550 keV | `1470 / 1000000` | `1072 / 1000000` | `1.37127` | `7.9` |
| W2 510.58-511.42 keV | `1269 / 1000000` | `1008 / 1000000` | `1.25893` | `5.47` |
| 1500-3000 keV | `1 / 1000000` | `0 / 1000000` | `n/a` | `1` |
| 3000-10000 keV | `0 / 1000000` | `0 / 1000000` | `n/a` | `n/a` |

The common parent-history event builder then applies the same active-veto
threshold and the same deterministic analytic W2 Gaussian response
(`sigma = 0.14 keV`) to both codes:

| metric | stage | FLUKA sum_w / histories | MEGAlib sum_w / histories | FLUKA/MEGAlib | z |
|---|---|---:|---:|---:|---:|
| W2 exact window | raw | `1269 / 1000000` | `1008 / 1000000` | `1.25893` | `5.47` |
| W2 analytic Gaussian expectation | raw | `1265.99 / 1000000` | `1005.19 / 1000000` | `1.25946` | `5.48` |
| W2 exact window | active-veto | `662 / 1000000` | `563 / 1000000` | `1.17584` | `2.83` |
| W2 analytic Gaussian expectation | active-veto | `660.692 / 1000000` | `561.302 / 1000000` | `1.17707` | `2.85` |

This answers the earlier concern that the TES_511_BALLOON delayed W2 fraction
might be accidentally low because of a post-processing or W2-response artifact.
The discrepancy is already present before the detector response: FLUKA
full-geometry raw TES coupling is higher than MEGAlib for the same Cu-64 parent
stream, and the analytic W2 response preserves the raw W2 ratio. The first
failed phase is therefore full-geometry raw-deposit/source-material coupling,
not the common W2 detector response.

Two operational fixes were needed for this production run: the FLUKA and
MEGAlib runners now stream the parent-list slice instead of loading the full
280 MB selected-index CSV per chunk, and the production work root was shortened
to `/tmp/phase3prod` because long FLUKA run paths truncated the generated
`-echo.inp` filename.

Boundary: the parent-history event builder is not yet the full external event
builder requested in Section 22. It does not perform 1 microsecond / 1
nanosecond sub-event splitting or side-Compton/FoV topology. Those remain open
if the next manuscript statement needs final Step05-equivalent selection.

### 17.6 Phase-3 Cu-64 raw-coupling decomposition, 2026-06-25

The first decomposition of the Phase-3 raw-coupling difference is now complete:

```text
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_raw_coupling_decomposition_1e6/summary.md
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_raw_coupling_decomposition_1e6/dimension_comparison.csv
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_raw_coupling_decomposition_1e6/local_tes_carrier_summary.csv
```

It joins the existing `/tmp/phase3prod` raw truth back to the shared
`1,000,000`-parent Cu-64 authority and decomposes the W2 raw difference by
source volume, static material, and original production tag.

Top W2 raw source-volume contributions:

| source volume | source histories | FLUKA W2 | MEGAlib W2 | diff / parent | share of total diff | conditional FLUKA/MEGAlib |
|---|---:|---:|---:|---:|---:|---:|
| `ColdPlate_MXC_50mK_SD_anchor` | `84445` | `438` | `227` | `+0.000211` | `0.808` | `1.9295` |
| `Cu_SubstrateSupport_SolidDisk_L0_deepest` | `4708` | `74` | `164` | `-0.000090` | `-0.345` | `0.4512` |
| `Cu_50mK_StillLike_Can_side_wall_above_side_port` | `26299` | `132` | `77` | `+0.000055` | `0.211` | `1.7143` |
| `ColdPlate_CP_100mK_intercept` | `95876` | `88` | `42` | `+0.000046` | `0.176` | `2.0952` |
| `Cu_50mK_StillLike_Can_side_wall_rectcut_window_band` | `31280` | `150` | `107` | `+0.000043` | `0.165` | `1.4019` |

Material and production-tag rollups show the same thing:

| dimension | key | histories | FLUKA W2 | MEGAlib W2 | diff / parent | share of total diff |
|---|---|---:|---:|---:|---:|---:|
| material | `Copper` | `937427` | `1210` | `989` | `+0.000221` | `0.847` |
| material | `CuNi` | `62573` | `59` | `19` | `+0.000040` | `0.153` |
| production tag | `n` | `998695` | `1267` | `1002` | `+0.000265` | `1.015` |
| production tag | `p` | `1140` | `2` | `6` | `-0.000004` | `-0.015` |

Interpretation: the W2 raw excess is not isolated to `CuNi`, not isolated to a
non-neutron production tag, and not a single-source-volume monotonic effect.
The largest positive contributor is `ColdPlate_MXC_50mK_SD_anchor`, but several
volumes pull in opposite directions: `Cu_SubstrateSupport_SolidDisk_L0_deepest`
and `Cu_50mK_StillLike_Can_bottom_cap_2mm` are MEGAlib-high. The remaining
physics question is therefore a distributed full-geometry coupling problem:
source-volume geometry, local containment/boundary behavior, positron stopping
and annihilation location, or incident TES ancestry.

The local TES carrier check is also consistent with the earlier photon concern.
FLUKA W2 raw TES rows are mostly local `EM_BELOW_THRESHOLD` deposits
(`1269` histories, `640735 keV` summed deposit) with a small `ELECTRON` tail.
MEGAlib W2 raw TES energy is mostly `e-` secondaries with gamma
`phot`/`compt` ancestry, plus smaller direct gamma rows. So the local carrier
label still must not be read as absence of photon-driven TES deposition.

Boundary: this decomposition reuses existing raw truth only. It does not add a
runtime point-location scorer, a positron stopping/annihilation locator, or the
complete Step05-equivalent 1 microsecond / 1 nanosecond plus side-Compton/FoV
event builder.

### 17.7 Phase-3 static boundary-margin audit, 2026-06-25

The first boundary-proximity discriminator is now complete:

```text
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_boundary_margin_audit_1e6/summary.md
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_boundary_margin_audit_1e6/margin_bin_comparison.csv
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_boundary_margin_audit_1e6/selected_margin_summary.csv
```

It joins the W2 raw selected histories back to the static coordinate-containment
audit and bins them by `expected_min_boundary_margin_cm_approx`.

W2 raw by static source-boundary margin:

| margin bin | source histories | FLUKA W2 | MEGAlib W2 | diff / parent | share of total diff | conditional FLUKA/MEGAlib |
|---|---:|---:|---:|---:|---:|---:|
| `< 1e-4 cm` | `298` | `5` | `2` | `+0.000003` | `0.0115` | `2.50` |
| `1e-4-1e-3 cm` | `3627` | `0` | `2` | `-0.000002` | `-0.0077` | `0` |
| `1e-3-1e-2 cm` | `56235` | `89` | `56` | `+0.000033` | `0.126` | `1.589` |
| `1e-2-5e-2 cm` | `218430` | `377` | `351` | `+0.000026` | `0.0996` | `1.074` |
| `5e-2-1e-1 cm` | `225167` | `370` | `316` | `+0.000054` | `0.207` | `1.171` |
| `1e-1-5e-1 cm` | `487576` | `422` | `278` | `+0.000144` | `0.552` | `1.518` |
| `>= 5e-1 cm` | `8667` | `6` | `3` | `+0.000003` | `0.0115` | `2.00` |

The W2 raw selected-event margin distributions are also not extreme:

| code | events | min margin cm | p10 cm | median cm | p90 cm | events < 0.01 cm |
|---|---:|---:|---:|---:|---:|---:|
| FLUKA | `1269` | `2.97e-05` | `0.01377` | `0.07178` | `0.2463` | `94` |
| MEGAlib | `1008` | `2.97e-05` | `0.01357` | `0.06295` | `0.2089` | `60` |

Interpretation: the net W2 raw FLUKA excess is not dominated by very
near-boundary source positions. Static margins `< 0.01 cm` contribute only
about `13%` of the net W2 raw difference. This weakens a pure
boundary-proximity explanation, although it does not replace a true runtime
point-location scorer or positron stopping/annihilation locator.

### 17.8 Phase-3 common time/topology event builder, 2026-06-25

The common external event builder now includes the two requested time-split
definitions and a bounded TES/active-shield topology summary:

```text
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_common_event_builder_time_topology_1e6/summary.md
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_common_event_builder_time_topology_1e6/comparison_stage_ratios.csv
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_common_event_builder_time_topology_1e6/topology_summary.csv
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_common_event_builder_time_topology_1e6/time_split_summary.csv
```

It consumes the independent Cu-64 common-parent raw deposits under
`/tmp/phase3prod`; it does not replay `.sim.gz` files. Within each parent it
clusters detector deposits by:

```text
parent: whole parent history
within_1us: cluster from first detector deposit within 1 microsecond
within_1ns: cluster from first detector deposit within 1 nanosecond
```

W2 focus comparison:

| event definition | stage | FLUKA W2 | MEGAlib W2 | FLUKA/MEGAlib | z |
|---|---|---:|---:|---:|---:|
| parent | raw | `1269` | `1008` | `1.25893` | `5.47` |
| parent | active-veto | `662` | `563` | `1.17584` | `2.83` |
| within 1 us | raw | `1269` | `1008` | `1.25893` | `5.47` |
| within 1 us | active-veto | `662` | `563` | `1.17584` | `2.83` |
| within 1 ns | raw | `1269` | `1008` | `1.25893` | `5.47` |
| within 1 ns | active-veto | `662` | `568` | `1.16549` | `2.68` |

Time split summary:

| code | event definition | detector parents | split parents | subevents | max subevents/parent |
|---|---|---:|---:|---:|---:|
| FLUKA | parent | `86695` | `0` | `86695` | `1` |
| FLUKA | within 1 us | `86695` | `0` | `86695` | `1` |
| FLUKA | within 1 ns | `86695` | `0` | `86695` | `1` |
| MEGAlib | parent | `68643` | `0` | `68643` | `1` |
| MEGAlib | within 1 us | `68643` | `0` | `68643` | `1` |
| MEGAlib | within 1 ns | `68643` | `301` | `68944` | `2` |

Interpretation: common event grouping is not the first failed phase. The
1 microsecond split is identical to parent-history grouping for this sample.
The 1 nanosecond split only moves a small MEGAlib active-veto tail and does not
remove the W2 excess. The builder adds single/multi TES-pixel and
active-shield-touch bookkeeping, but it does not implement the final
side-Compton/FoV reconstruction cut.

### 17.9 Manuscript delayed-background statement, 2026-06-25

The manuscript-facing delayed-background statement is now drafted as a bounded
artifact:

```text
engineering/crosscode_delayed_closure_20260625/05_decision/manuscript_delayed_background_statement.md
engineering/crosscode_delayed_closure_20260625/05_decision/manuscript_delayed_background_statement.json
```

Recommended treatment: report delayed activation as an unresolved cross-code
model systematic for the current analysis. Keep the W2 total agreement as a
total-rate cross-check only; do not use it as delayed-component validation and
do not average the TES/MEGAlib and FLUKA delayed central values.

The statement quotes the current W2 final rates:

| component | TES cps | FLUKA cps | FLUKA/TES |
|---|---:|---:|---:|
| prompt | `0.036641023` | `0.031891161` | `0.870` |
| delayed | `0.002575203` | `0.006787802` | `2.636` |
| total | `0.039216227` | `0.038678963` | `0.986` |

It also quotes the Phase-3 Cu-64 raw-coupling evidence:

| gate | FLUKA W2 | MEGAlib W2 | FLUKA/MEGAlib |
|---|---:|---:|---:|
| raw parent-history | `1269 / 1000000` | `1008 / 1000000` | `1.25893` |
| active-veto parent-history | `662 / 1000000` | `563 / 1000000` | `1.17584` |
| active-veto 1 ns split | `662 / 1000000` | `568 / 1000000` | `1.16549` |

Boundary: this is a manuscript-support statement, not closure of the remaining
physical mechanism. Runtime point-location, positron stopping/annihilation
location, and incident TES ancestry remain the next physics diagnostics.

### 17.10 Conditional gate disposition and completion audit, 2026-06-25

The remaining checklist items that were written as conditional gates are now
dispositioned in:

```text
engineering/crosscode_delayed_closure_20260625/05_decision/engineering_completion_audit.md
engineering/crosscode_delayed_closure_20260625/05_decision/engineering_completion_audit.json
```

The audit does not claim that runtime point-location, stopping/annihilation, or
incident TES ancestry have been measured. It states that they are future
mechanism diagnostics, not blockers for the current independent-source
raw-coupling/systematic conclusion. The conditional gates are closed as follows:

| conditional gate | disposition |
|---|---|
| Geant4/MEGAlib `1e6`/isotope decay-kernel production if low-yield precision is needed | not triggered for current conclusion |
| FLUKA EM-cut scan if ancestry/full-geometry observables reopen EM-cut dependence | not triggered |
| Runtime point-location audit if required before production transport | no longer required before production transport; future mechanism diagnostic |
| Final side-Compton/FoV if manuscript-level final selection is required | not triggered for current manuscript statement |

## 18. Source-region audit

For every unique source position, record in both codes:

```text
input x/y/z
resolved region or logical volume
resolved material
distance to nearest boundary
inside/outside status
expected source volume
```

Fail the run if any of the following occurs:

```text
position is in vacuum when expected in Cu
material differs between codes
coordinate differs by more than 0.01 mm
source lies within numerical tolerance of a boundary without an explicit policy
isomer or isotope identity differs
```

Pay special attention to the Cu volumes already seen in the MEGAlib W2 sample:

```text
ColdPlate_MXC_50mK_SD_anchor
Cu_SubstrateSupport_SolidDisk_L0_deepest
Cu_50mK_StillLike_Can_bottom_cap_2mm
ColdPlate_CP_100mK_intercept
Window
Cu_50mK_StillLike_Can_side_wall_above_side_port
DR_MixingChamber_Cu
ColdPlate_Still_0p7K
```

### 18.1 Source-volume/material name audit status, 2026-06-25

The first source-region/material audit layer is complete:

```text
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/source_region_material_name_audit.md
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/cu64_source_region_material_name_audit.csv
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/source_region_material_name_audit.json
```

It checks the `source_volume` names from `cu64_common_positions.csv` against
the FLUKA geometry-translation `region_map.csv`. All `6927` Cu-64 rows pass
this name-level translation audit:

| audit status | rows | activity weight |
|---|---:|---:|
| `PASS_NAME_LEVEL` | `6927` | `4.7019049431490107524463624743796 Bq` |

The translated material split is:

| material | rows | activity fraction |
|---|---:|---:|
| `Copper` | `6494` | `93.749%` |
| `CuNi` | `433` | `6.251%` |

This removes one simple failure mode: the built Cu-64 source rows are not
pointing at unmapped or untranslated FLUKA region names. It does **not** prove
coordinate containment. The audit did not test nearest-boundary distance or
runtime Geant4/FLUKA point location. `217` rows (`3.13%` by activity) have a
canonical reporting name that differs from `source_volume`; that field is
reporting-only and is not used as the geometry authority.

### 18.2 Static coordinate-containment audit status, 2026-06-25

The second audit layer is complete:

```text
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/source_coordinate_containment_audit.md
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/cu64_source_coordinate_containment_audit.csv
engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/source_coordinate_containment_audit.json
```

It inverse-rotates source-v2 coordinates by `InstrumentFrame.Rotation 0 45 0`
into the local coordinate frame used by `build_geometry_translation.py`, then
checks each point against the same MEGAlib geometry authority parsed by the
FLUKA translator. All Cu-64 rows pass:

| audit status | rows | activity weight |
|---|---:|---:|
| `PASS_STATIC_CONTAINMENT` | `6927` | `4.7019049431490107524463624743796 Bq` |

The deepest resolved static material split is unchanged from the name-level
audit:

| resolved material | rows | activity fraction |
|---|---:|---:|
| `Copper` | `6494` | `93.749%` |
| `CuNi` | `433` | `6.251%` |

This removes a stronger failure mode: the common Cu-64 coordinates are not just
mapped by name; after applying the explicit InstrumentFrame transform, each
coordinate lies inside its declared `source_volume`, and that source volume is
the deepest translated object containing the point. Minimum approximate margin
to the expected source boundary is `2.325151502e-05 cm`. This is still a static
translator audit, not a FLUKA runtime or Geant4 runtime point-location scorer.

## 19. Raw outputs required from both codes

Do not compare only final event tables. Save deposit-level truth:

```text
common_event_id
track_id
parent_id
particle_id
creator_process
global_time_s
x_cm
y_cm
z_cm
volume_or_region
material
TES_pixel_id
shield_segment_id
energy_deposit_keV
incident_boundary_particle_id
```

If FLUKA cannot provide all ancestry immediately, add at least a TES-boundary crossing scorer and an annihilation-vertex scorer.

## 20. Common external event builder

Do not use different internal event grouping during the comparison. Feed both raw deposit files into one Python program.

Calculate three event definitions:

```text
A. whole parent history
B. deposits grouped within 1 microsecond
C. deposits grouped within 1 nanosecond
```

For each definition, aggregate deposits by TES pixel and shield segment using identical code.

## 21. Common detector response

Turn off code-specific detector smearing. Keep raw deposited energy.

For the comparison, avoid random Gaussian smearing. Compute the expected W2 acceptance analytically for every event:

```text
p_W2(E) = Phi((511.42 - E)/sigma) - Phi((510.58 - E)/sigma)
sigma = 0.14 keV
```

Then calculate:

```text
R_W2_expected = sum(weight_i * p_W2(E_i))
```

This removes random smearing noise and makes the comparison deterministic.

After closure, a sampled detector-response realization can be restored for paper figures.

## 22. Stage-by-stage comparison

For Cu-64 only, report:

| Stage | Quantity |
|---|---|
| source | parents, sum_w, sum_w2 |
| TES raw | any TES energy, broad-band spectrum |
| 480–550 | broad annihilation-peak rate |
| W2 unsmeared | exact raw energy in W2 |
| W2 expected | analytic Gaussian response expectation |
| active-veto | shield energy below 50 keV |
| topology | single/multi-pixel fractions |
| final | common topology/FoV rule |

Also report conditional efficiencies:

```text
P(TES > 0 | decay)
P(480–550 | TES > 0)
P(W2 | 480–550)
P(veto pass | W2)
P(final | veto pass)
```

The first conditional efficiency that diverges identifies the responsible layer.

---

# Phase 4 — Statistical gate

## 23. Minimum statistics

Current FLUKA delayed W2 contains only 10 final events. That is insufficient for a factor-level software conclusion.

Use these stop targets:

```text
Smoke: 1e5 Cu-64 parents per code
Decision run: 1e6 Cu-64 parents per code
Final validation: enough histories for >=1000 W2 events per code
```

If runtime is high, stop adaptively when either condition is met:

```text
N_W2 >= 300 per code
or weighted relative sigma <= 10%
```

## 24. Weighted uncertainty

Always report:

```text
sum_w
sum_w2
sigma_rate = sqrt(sum_w2)
N_eff = (sum_w)^2 / sum_w2
```

For a ratio `r = R_FLUKA / R_G4`, use propagated uncertainty or a bootstrap over source positions/histories.

### Decision thresholds

```text
0.80 <= r <= 1.25 and discrepancy < 3 sigma:
    cross-code closure for current paper scope

r outside [0.80, 1.25] and discrepancy >= 3 sigma:
    real cross-code discrepancy; assign to first failing phase

relative uncertainty > 15%:
    inconclusive; add statistics, do not interpret central ratio
```

---

# Phase 5 — Automated decision report

## 25. Required final artifacts

```text
05_decision/decay_kernel_metrics.json
05_decision/em_transport_metrics.json
05_decision/full_geometry_metrics.json
05_decision/crosscode_stage_ratios.csv
05_decision/crosscode_decision.md
05_decision/crosscode_decision.json
```

The machine-readable decision JSON should contain:

```json
{
  "status": "PASS | FAIL_DECAY | FAIL_EM | FAIL_GEOMETRY | FAIL_EVENT_BUILDING | FAIL_SOURCE_NORMALIZATION | INCONCLUSIVE",
  "first_failed_phase": "...",
  "g4_commit": "...",
  "fluka_commit": "...",
  "g4_environment_hash": "...",
  "fluka_environment_hash": "...",
  "common_source_hash": "...",
  "n_parent_g4": 0,
  "n_parent_fluka": 0,
  "n_w2_g4": 0,
  "n_w2_fluka": 0,
  "w2_efficiency_g4": 0.0,
  "w2_efficiency_fluka": 0.0,
  "ratio": 0.0,
  "ratio_uncertainty": 0.0,
  "significance_sigma": 0.0,
  "notes": []
}
```

---

# 26. Concrete 24-hour run order

## First 30 minutes

- Freeze commits, versions, data directories, input hashes.
- Verify FLUKA source routine actually launches Cu-64, not the dummy I-128 isotope.
- Create the new engineering directory.

## Hours 1–3

- Implement/run the Cu-64 vacuum decay-kernel benchmark.
- Compare beta-plus branch, positron spectrum, gamma yields and event timing.

### Stop rule

If the Cu-64 branch or emitted spectrum differs by more than 10%, stop. The conclusion is already “decay engine/database/configuration difference.”

## Hours 3–6

- Run code-neutral positron and 511-photon lists through toy Cu/Ta geometries.
- Run FLUKA cutoff/default scan only if toy transport differs.

### Stop rule

If toy transport differs by more than 20% with adequate statistics, stop. The conclusion is “EM transport/cut/annihilation difference.”

## Hours 6–18

- Generate one `cu64_common_positions.csv`.
- Run `10^6` common Cu-64 parents through both full geometries.
- Save raw deposits and source-region audits.

## Hours 18–22

- Process both outputs with the same external event builder.
- Evaluate whole-history, 1 microsecond and 1 nanosecond grouping.
- Apply analytic Gaussian W2 acceptance.

## Hours 22–24

- Generate the decision matrix and `crosscode_decision.md`.
- Only then decide whether the manuscript should use:
  - the MEGAlib value;
  - the FLUKA value;
  - a cross-code interval;
  - or a stated unresolved systematic.

---

# 27. What not to do next

Do not spend the next cycle on:

- rerunning all eight atmospheric species;
- rebuilding the complete gondola;
- averaging the two delayed rates;
- tuning cuts until the total W2 rates match;
- comparing only final W2 counts;
- treating `EM_BELOW_THRESHOLD` as incident-particle identity;
- interpreting the current 10 FLUKA events as a settled factor-2.6 discrepancy;
- mixing legacy sampled MEGAlib source positions with source-v2 FLUKA positions in the decisive test.

These actions add cost without identifying the first layer where the codes diverge.

---

# 28. Likely conclusions and manuscript action

## Outcome A — decay kernel differs

Paper treatment:

```text
Delayed activation is assigned an explicit cross-code nuclear-decay-model systematic.
Do not promote either central value until evaluated Cu-64 yields identify the correct configuration.
```

## Outcome B — decay closes, EM transport differs

Paper treatment:

```text
Quote sensitivity to positron/annihilation transport and EM cut settings.
Use the configuration validated against the toy benchmark or laboratory data.
```

## Outcome C — toy closes, full-geometry raw deposits differ

Paper treatment:

```text
Treat the issue as geometry/source-position mapping; fix coordinates, materials or region assignment before reporting delayed rate.
```

## Outcome D — raw deposits close, event construction differs

Paper treatment:

```text
Use one common external event builder and detector response for both codes.
The transport codes are not the origin of the discrepancy.
```

## Outcome E — all per-decay efficiencies close

Paper treatment:

```text
The residual originates in source activity/weights/source realization. Promote source-v2 as the single delayed-source authority and rerun the paper baseline from it.
```

## Outcome F — ratio remains different but statistics are adequate and no single layer dominates

Paper treatment:

```text
Report the cross-code difference as a model systematic, not as a statistical uncertainty.
Keep the headline as a reference-model estimate and include both delayed values in a validation subsection.
```

---

# 29. Recommended owner checklist

```text
[x] Freeze repositories and environment manifests
[x] Verify actual FLUKA isotope Z/A/isomer at runtime
[x] Build FLUKA smoke decay-kernel outputs for Cu-64, Na-24, Al-28, I-128
[x] Build FLUKA 1e6/isotope production decay-kernel outputs for Cu-64, Na-24, Al-28, I-128
[x] Build Geant4/MEGAlib smoke decay-kernel outputs for Cu-64, Na-24, Al-28, I-128
[x] Compare first-pass branch/line yields for Cu-64, Na-24, Al-28, I-128
[x] Disposition Geant4/MEGAlib 1e6/isotope production decay-kernel gate: not triggered for current conclusion
[x] Build one common external positron/511 source list and pass T0 source-bookkeeping smoke
[x] Run Cu/Ta toy transport in both codes (T1/T2 smoke complete; T2 production W2/broad deposited-energy acceptance pass)
[x] Disposition FLUKA effective EM-cut scan gate: not triggered by current evidence
[x] Build cu64_common_positions.csv
[x] Build deterministic 1e6 Cu-64 parent resampling authority
[x] Audit source-volume name/material translation against the FLUKA region map
[x] Static coordinate-containment audit after inverse InstrumentFrame transform
[x] Run FLUKA 1k Phase-3 common Cu-64 raw-deposit plumbing smoke
[x] Run MEGAlib 1k Phase-3 common Cu-64 raw-hit plumbing smoke
[x] Calibrate MEGAlib HTsim detector/readout semantics against the common raw-deposit schema
[x] Disposition runtime engine point-location gate: not required before completed production transport; remains future mechanism diagnostic
[x] Run 1e6 Cu-64 parents per code
[x] Save raw deposit truth locally under `/tmp/phase3prod`; commit summaries only
[x] Apply deterministic analytic W2 response at parent-history stage
[x] Produce parent-history stage ratios and weighted uncertainties
[x] Assign first failed phase: full-geometry raw-deposit/source-material coupling
[x] Decompose Phase-3 raw coupling by source volume/material/production tag and local TES carrier
[x] Audit W2 raw selected histories against static source-boundary margins
[x] Run common 1 us / 1 ns time split and TES/active-shield topology builder
[x] Disposition final side-Compton/FoV gate: not triggered for current manuscript/systematic statement
[x] Update manuscript delayed-background statement
```

---

## 30. One-sentence operational rule

> Use the same Cu-64 parents, positions, weights, raw-output schema, event builder and detector response in both codes; stop at the first stage where the statistically resolved discrepancy appears.
