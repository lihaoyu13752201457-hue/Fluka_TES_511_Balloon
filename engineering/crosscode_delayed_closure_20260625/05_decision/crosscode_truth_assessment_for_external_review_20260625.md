# Cross-Code Truth Assessment For External Review

Date: 2026-06-25

## One-Line Answer

不能把 FLUKA 或 TES_511_BALLOON/MEGAlib 的 delayed W2 中心值直接当作真实值。若必须给当前工程先验，我更倾向把 TES_511_BALLOON/MEGAlib 作为 511-keV photon ancestry / 本底构成的参考模型，但 delayed 绝对率仍应报告为 unresolved cross-code model systematic，而不是说 MEGAlib 已被验证为真。

原因不是“统计数不够”。`engineering.md` 约束下的独立源复现已经把差异定位到 full-geometry raw TES coupling；它发生在共同 detector response、W2 Gaussian response、active-veto/time grouping 之前。更合理的解释是 full geometry 里的 runtime transport / cut / region-material / boundary / scoring coupling 不同，尤其是 Cu-64 positron stopping、annihilation 511 photons escape path、TES 入射粒子谱和局部二次电子沉积。

## Current Numerical Facts

### TES_511_BALLOON final W2 comparison

| component | TES_511_BALLOON / MEGAlib cps | FLUKA cps | FLUKA/TES |
|---|---:|---:|---:|
| prompt | `0.036641023` | `0.031891161` | `0.870` |
| delayed | `0.002575203` | `0.006787802` | `2.636` |
| total | `0.039216227` | `0.038678963` | `0.986` |

结论：total W2 接近是 prompt deficit 与 delayed excess 的补偿，不能用 total agreement 验证 delayed component。

### Independent-source Phase-3 Cu-64 1e6 comparison

| gate | FLUKA | MEGAlib | FLUKA/MEGAlib | note |
|---|---:|---:|---:|---|
| any TES raw histories | `6566 / 1000000` | `2797 / 1000000` | `2.34752` | before response |
| 480-550 keV raw histories | `1470 / 1000000` | `1072 / 1000000` | `1.37127` | before response |
| W2 raw histories | `1269 / 1000000` | `1008 / 1000000` | `1.25893` | about `5.47 sigma` |
| W2 active-veto histories | `662 / 1000000` | `563 / 1000000` | `1.17584` | about `2.83 sigma` |
| W2 analytic Gaussian raw | `1265.99` | `1005.19` | `1.25946` | common response |
| W2 analytic Gaussian active-veto | `660.692` | `561.302` | `1.17707` | common response |

结论：`engineering.md` 下已经不是 10-event low-stat ambiguity。1e6 common Cu-64 parent stream 的 raw W2 difference 是统计上稳定的。

## What Engineering.md Has Already Constrained

### Source and decay identity

- Source authority: `254704` heavy-isotope rows, total delayed activity `86.9998420669 Bq`.
- FLUKA runtime source identity gate passes for checked delayed histories: dummy `HI-PROPE 53 128` is overridden before `set_primary`.
- Cu-64 Phase-3 source authority: `6927` common Cu-64 positions, `Z=29`, `A=64`, `isomer=0`, total Cu-64 activity `4.701904943149... Bq`.
- Deterministic common parent stream: `1000000` Cu-64 parent histories per code, equal diagnostic weight, no `.sim.gz` replay.

### Decay-kernel gates

FLUKA production decay kernel, `1e6` parents per isotope:

| nuclide | key result |
|---|---:|
| Cu-64 | positron yield `0.176483`; 1346-keV gamma yield `0.004785` |
| Na-24 | 1369-keV gamma `0.999939`; 2754-keV gamma `0.998547`; same-parent coincidence `0.998547` |
| Al-28 | 1779-keV gamma `1.0` |
| I-128 | photon yield `0.199216` |

Geant4/MEGAlib smoke decay kernel, `2e4` parents per isotope:

| nuclide | key result |
|---|---:|
| Cu-64 | positron yield `0.1767`; 1346-keV gamma yield `0.0043` |
| Na-24 | 1369/2754-keV lines about unit yield |
| Al-28 | 1779-keV gamma `1.0` |
| I-128 | photon yield `0.20605` |

结论：当前 delayed W2 差异不能解释为 Cu-64 beta+ branch 丢失，也不能解释为 FLUKA 完全没有 Na-24/Al-28 high-energy gamma cascade lines。

### Toy EM transport gate

- Phase-2 T0 source bookkeeping passes: both codes start the same explicit photon/positron primary table.
- Phase-2 generated-source Cu+Ta production gate passes broad W2/Ta deposited-energy checks:
  - Cu-64 positron rows: FLUKA/MEGAlib `1.029`, `1132` vs `1100`, `0.68 sigma`.
  - mono-511 rows: `0.986`.
  - pair-511 rows: `1.007`.

结论：不存在一个简单、全局的 Cu+Ta 511-keV EM deposited-energy mismatch。差异只在 full geometry 中出现。

### Geometry/source definition gates

- Source-region/material name audit: all `6927` Cu-64 rows pass `PASS_NAME_LEVEL`.
- Material split: Copper `6494` rows (`93.749%`), CuNi `433` rows (`6.251%`).
- Static coordinate containment audit: all `6927` rows pass `PASS_STATIC_CONTAINMENT` after inverse `InstrumentFrame.Rotation 0 45 0`.
- Minimum approximate static margin: `2.325151502e-05 cm`.
- Static boundary-margin audit: source positions with static margin `< 0.01 cm` contribute only about `13%` of net W2 raw difference.

结论：几何和源定义按工程约束已经高度一致。剩余问题不是“明显用了不同源/不同几何定义”，而是 runtime point location / navigator / region-material / transport coupling 这类 full-geometry execution 层问题。

## First Failed Phase

First failed phase: full-geometry raw-deposit/source-material coupling.

Evidence:

- Phase-3 raw production already differs before response: W2 raw `1269` vs `1008`.
- Common parent-history response preserves raw ratio: analytic W2 raw `1.25946`.
- Common active-veto/time-topology does not remove discrepancy:
  - parent-history and 1 us grouping identical;
  - 1 ns split only moves a small MEGAlib active-veto tail.
- Final side-Compton/FoV reconstruction is not yet the first failure layer.

This is the strongest statement produced by the current `engineering.md` run.

## Source-Volume Mechanism Evidence

The W2 raw difference is not monotonic and not a pure distance scalar. It changes sign by source volume.

| source volume | source histories | FLUKA W2 | MEGAlib W2 | diff | share of net | FLUKA/MEGAlib |
|---|---:|---:|---:|---:|---:|---:|
| `ColdPlate_MXC_50mK_SD_anchor` | `84445` | `438` | `227` | `+211` | `0.808` | `1.92952` |
| `Cu_SubstrateSupport_SolidDisk_L0_deepest` | `4708` | `74` | `164` | `-90` | `-0.345` | `0.45122` |
| `Cu_50mK_StillLike_Can_side_wall_above_side_port` | `26299` | `132` | `77` | `+55` | `0.211` | `1.71429` |
| `ColdPlate_CP_100mK_intercept` | `95876` | `88` | `42` | `+46` | `0.176` | `2.09524` |
| `Cu_50mK_StillLike_Can_side_wall_rectcut_window_band` | `31280` | `150` | `107` | `+43` | `0.165` | `1.40187` |

Global W2 selected source-to-TES distance distributions are similar:

| code | stage | events | median cm | p10 cm | p90 cm |
|---|---|---:|---:|---:|---:|
| FLUKA | raw | `1269` | `5.5281` | `2.046` | `11.027` |
| MEGAlib | raw | `1008` | `5.8465` | `1.087` | `9.8954` |
| FLUKA | active-veto | `662` | `5.6047` | `1.977` | `13.187` |
| MEGAlib | active-veto | `563` | `6.1179` | `1.1883` | `11.825` |

Interpretation:

1. 不是单纯统计误差。
2. 不是一个简单的 near/far distance factor。
3. 不是 CuNi-only 或 neutron/non-neutron tag-only。
4. 更像 dominant Cu volumes 周围的局部路径问题：positron range/stopping, annihilation vertex, 511 photons escape/attenuation, TES boundary incidence, secondary-electron local deposition, runtime region/material assignment。

## Photon Concern

用户的直觉是对的：很多 delayed W2 TES deposit 应该以 511-keV photons 进入 TES/Ta 附近，然后通过 photoelectric/Compton 产生局部电子沉积。当前证据支持这个方向。

MEGAlib `CC HIT` truth shows W2 TES rows mostly as local `e-` deposits with gamma `phot`/`compt` ancestry, plus smaller direct gamma rows. That means the physical background composition is photon-driven even when the local deposited carrier is electron.

FLUKA current raw dump cannot answer the same ancestry question. The scorer aggregates per region and stores only the first contributing local `JTRACK/ICODE` proxy for that region. Many rows appear as `EM_BELOW_THRESHOLD` / `ENDRAW` local deposition. This is not evidence that photons are absent; it only says that the existing FLUKA scoring schema loses incident ancestry.

Therefore:

- It is wrong to summarize the physical TES background as only neutron/electron.
- The correct statement is: source production is mostly neutron-produced Cu-64; TES energy deposition is expected to be photon/secondary-electron dominated; FLUKA incident photon ancestry is currently unmeasured.

## Local Code/Configuration Findings

### MEGAlib/Cosima

Actual Phase-3 source input includes:

```text
PhysicsListEM LivermorePol
PhysicsListRadioactiveDecay true
DecayMode ActivationDelayedDecay
StoreSimulationInfo all
StoreIsotopes true
PreTriggerMode Everything
DiscretizeHits true
DetectorTimeConstant 1e-9
```

Relevant local source:

- `/home/ubuntu/MEGAlib_Install/megalib-main/src/cosima/src/MCParameterFile.cc`
  - `PhysicsListEM LivermorePol` maps to `MCPhysicsList::c_EMLivermorePolarized`.
  - `Region.RangeCut` can be parsed, but the current Phase-3 input does not set explicit region range cuts.
- `/home/ubuntu/MEGAlib_Install/megalib-main/src/cosima/src/MCPhysicsList.cc`
  - `c_EMLivermorePolarized` registers `G4EmLivermorePolarizedPhysics`.
  - `G4RadioactiveDecayPhysics` is always registered.
  - `G4RadioactiveDecay` is post-modified with internal conversion and atomic rearrangement enabled.
  - atom deexcitation has fluorescence and Auger enabled.
  - `SetCuts()` starts with `SetCutsWithDefault()` and only applies region cuts if they were explicitly defined.

Potential implication:

- MEGAlib has better local ancestry visibility in the current artifacts.
- But MEGAlib full-geometry result may still be sensitive to default Geant4 production cuts and region cuts, because no explicit `Region.RangeCut` is present in the source.

### FLUKA

Actual Phase-3 input includes:

```text
DEFAULTS EM-CASCA
BEAM ... ISOTOPE
RADDECAY 2.0
DCYSCORE -1.0
EMFCUT -1.0E-05 1.0E-05 0.0 R0000001 @LASTREG
SCORE ENERGY
USERDUMP 100 99 6 RAWDUMP
```

Local source/scorer:

- `work_fluka_harness/run_delayed_isotope_raw_mvp.py`
  - reads `isotopes.dat` and launches heavy ion isotope primaries by Z/A/isomer.
- `work_fluka_harness/build_raw_scoring_smoke.py`
  - `MGDRAW` accumulates continuous track deposits.
  - `ENDRAW` accumulates local deposits including below-threshold EM energy.
  - per region, only the first local particle/proxy code is retained with the summed energy.

Potential implication:

- FLUKA total raw energy can be useful, but current FLUKA raw carrier labels are not ancestry-comparable with MEGAlib `CC HIT`.
- `BXDRAW` is currently unused for TES-boundary incident particle ancestry, even though FLUKA supports it.

## Literature And Manual Survey

### FLUKA

Official references:

- FLUKA official CERN references page: https://fluka.cern/documentation/references
  - lists Ahdida et al., "New Capabilities of the FLUKA Multi-Purpose Code", Frontiers in Physics 9, 788253 (2022).
  - lists Battistoni et al., "Overview of the FLUKA code", Annals of Nuclear Energy 82, 10-18 (2015).
- FLUKA user-routines documentation: https://fluka.cern/documentation/running/user-routines
  - user routines can customize scoring and obtain single-particle track/interaction details not available through standard cards.

Local FLUKA manual evidence:

- `EMFCUT` sets electron/photon production thresholds and transport cutoffs.
- FLUKA manual recommends explicit threshold values or checking them in the main output because defaults can be problem dependent.
- Transport cutoffs are region-based; production cutoffs are material-based.
- Minimum threshold is `100 eV` for photons and `1 keV` for electrons/positrons.
- `RADDECAY 2.0` is semi-analogue radioactive decay; emitted particles are transported in the same run, but spectra are inclusive and gamma cascades are not necessarily event-correlated in the same way as a full decay database representation.
- FLUKA photon physics includes Compton with Doppler broadening, photoelectric effect, Rayleigh scattering, fluorescence/Auger treatment when enabled by defaults/options.
- FLUKA electron physics includes positron/electron stopping differences, bremsstrahlung, and positron annihilation in flight/at rest.

### Geant4 / MEGAlib

Relevant papers:

- Brown and Dimmock, "An electromagnetic physics constructor for low energy polarised X-/gamma ray transport in Geant4", arXiv:2102.02721, https://arxiv.org/abs/2102.02721
  - A low-energy polarized X/gamma Geant4 constructor was validated against Compton polarimetry measurements and reproduced results at about the cross-section uncertainty scale. This supports Geant4 as a serious reference for low-energy X/gamma transport, but it is not a direct validation of this exact MEGAlib `LivermorePol` configuration in this TES geometry.
- Hauf et al., "Validation of Geant4-based Radioactive Decay Simulation", arXiv:1306.5129, https://arxiv.org/abs/1306.5129
  - Geant4 radioactive decay simulation was validated against HPGe source measurements. This supports the conclusion that the Cu-64 decay kernel itself is not the likely culprit, especially because our local decay-kernel gates also pass.
- Batic et al., "Validation of Geant4 simulation of electron energy deposition", arXiv:1307.0933, https://arxiv.org/abs/1307.0933
  - low-energy electron energy-deposition profiles are sensitive to Geant4 version/model/scattering choices; total energy is often less variable than local longitudinal profiles. This is directly relevant because the unresolved effect is local TES/Ta deposition in full geometry.
- Kim et al., "Validation Test of Geant4 Simulation of Electron Backscattering", arXiv:1502.01507, https://arxiv.org/abs/1502.01507
  - electron backscattering is sensitive to multiple/single scattering models and versions. This supports treating local electron/TES boundary effects as a model systematic rather than a solved constant.

Interpretation from literature:

- Neither FLUKA nor Geant4 has a generic right to be called "truth" for this exact full-geometry, thin-sensitive-volume 511-keV deposited-energy observable.
- Literature supports both as credible transport codes.
- Literature also supports exactly the weak point seen here: low-energy electron/photon local deposition near boundaries and thin detectors can be sensitive to model/cut/geometry choices.

## Which Is More Likely Closer To Reality?

My current answer:

1. For physical composition/ancestry, MEGAlib is more credible in the current artifacts because its `CC HIT` output preserves local particle, parent, creator process, and step-process ancestry. It directly shows gamma `phot`/`compt` ancestry feeding TES-local electrons. FLUKA's current raw dump cannot refute this because it records local deposit proxies, not TES-boundary incident ancestry.

2. For delayed W2 absolute rate, neither central value is certified. The FLUKA result is not dismissible as statistics; the MEGAlib result is not automatically true just because it is the original TES_511_BALLOON chain. The right paper treatment is unresolved cross-code model systematic.

3. If forced to select a working reference before the decisive scorer exists, I would use TES_511_BALLOON/MEGAlib as the reference central value and carry FLUKA as a systematic envelope, not average the two. The reason is pragmatic: MEGAlib is the native geometry/detector chain and currently has better event ancestry for the photon-driven W2 interpretation. The cost is that full-geometry rate closure remains unproven.

4. The most likely issue is not "one code lacks photons" or "one code has only neutron/electron background." It is a full-geometry coupling difference in how annihilation photons and secondary electrons reach/deposit in TES/Ta across complex Cu structures.

Confidence:

- High confidence: first failed phase is full-geometry raw coupling before response.
- High confidence: current FLUKA local carrier labels do not prove photons absent.
- Medium confidence: MEGAlib is the better current reference for ancestry/composition.
- Low-to-medium confidence: MEGAlib absolute delayed W2 central value is closer to experiment, because no experimental calibration or decisive matched ancestry scorer exists yet.

## Ranked Suspects

1. Runtime TES-boundary incident ancestry and annihilation path differences.
   - Need to measure photon/e-/e+ crossing into TES, not infer from local deposit labels.

2. Geant4/MEGAlib default range cuts versus FLUKA explicit `EMFCUT`.
   - MEGAlib currently uses `SetCutsWithDefault()` unless region cuts are set.
   - FLUKA explicitly sets `10 keV` e/gamma transport cutoffs across regions in the raw run.
   - A cut/region scan could change local thin-volume deposits without breaking the toy Cu+Ta broad closure.

3. Runtime point location / navigator / region-material assignment in complex boolean geometry.
   - Static containment passes, but runtime point location in FLUKA and Geant4 has not been measured.
   - Sign flips by source volume are consistent with local region/material/path differences.

4. FLUKA scoring schema compression.
   - This explains why FLUKA composition labels are ambiguous.
   - It does not by itself explain total raw W2 rate unless region aggregation or below-threshold local deposition is being counted differently from MEGAlib CC HIT truth.

5. Native MEGAlib detector threshold/discretization semantics.
   - Common builder uses `CC HIT` raw totals, so this is less likely to explain the full W2 raw difference.
   - Still worth checking whether `DiscretizeHits` or sensitive-detector thresholds suppress small deposits before `CC HIT` serialization.

## Decisive Next Diagnostics

Do not rerun broad prompt+activation first. Run targeted matched observables on the already identified dominant Cu volumes:

1. FLUKA `BXDRAW` TES-boundary scorer:
   - incident particle ID;
   - kinetic energy;
   - direction;
   - entering/leaving region;
   - source history ID;
   - source volume;
   - whether event later lands in W2.

2. FLUKA annihilation/stopping locator:
   - positron stopping position/material/region;
   - annihilation photon directions and energies;
   - distance/path to TES.

3. MEGAlib matched ancestry export:
   - from `CC HIT`/track information, summarize photon/electron boundary incidence and annihilation vertices if available.

4. Full-geometry cut scan, not tuning:
   - MEGAlib: explicit `Region.RangeCut` around TES/Ta/Cu; compare LivermorePol vs Penelope/Standard only for top source volumes.
   - FLUKA: delayed-only `EMFCUT` scan for the same top source volumes.

5. Top-volume restricted common-parent runs:
   - `ColdPlate_MXC_50mK_SD_anchor`.
   - `Cu_SubstrateSupport_SolidDisk_L0_deepest`.
   - These two volumes alone test the observed sign flip.

## External Reviewer Prompt

下面这段可以直接发给外部 reviewer / ChatGPT:

```text
We have two independent Monte Carlo implementations of delayed activation background for a TES 511-keV balloon instrument: the native TES_511_BALLOON/MEGAlib Geant4 chain and an independent FLUKA translation.

The original final W2 rates are:
- TES_511_BALLOON/MEGAlib prompt 0.036641023 cps, delayed 0.002575203 cps, total 0.039216227 cps.
- FLUKA prompt 0.031891161 cps, delayed 0.006787802 cps, total 0.038678963 cps.
Thus total agrees at 0.986x but prompt/delayed compensate; delayed is 2.636x higher in FLUKA.

To avoid replaying the MEGAlib .sim.gz chain, we built an independent common Cu-64 source:
- 6927 Cu-64 source positions, same source rows, Z=29 A=64 isomer=0, total activity 4.701904943 Bq.
- 1,000,000 deterministic Cu-64 parent histories per code.
- Source-region/material name audit passes for all rows.
- Static coordinate containment audit passes for all rows after the known InstrumentFrame rotation.
- Phase-2 common Cu+Ta EM toy transport passes W2 deposited-energy closure.

The first failed phase is full-geometry raw TES coupling:
- FLUKA any-TES raw 6566/1e6, MEGAlib 2797/1e6.
- FLUKA W2 raw 1269/1e6, MEGAlib 1008/1e6, ratio 1.25893, about 5.47 sigma.
- Common analytic W2 response gives ratio 1.25946.
- Common active-veto/time grouping does not remove the discrepancy.

The discrepancy changes sign by source volume:
- ColdPlate_MXC_50mK_SD_anchor: FLUKA 438, MEGAlib 227.
- Cu_SubstrateSupport_SolidDisk_L0_deepest: FLUKA 74, MEGAlib 164.
Global source-to-TES distance distributions are similar, and near-boundary source positions explain only about 13% of net difference.

MEGAlib CC HIT rows show local TES e- deposits with gamma phot/compt ancestry. FLUKA current raw dump stores only local deposit proxies such as EM_BELOW_THRESHOLD/ENDRAW, not incident TES ancestry.

MEGAlib uses PhysicsListEM LivermorePol, G4RadioactiveDecay, atom deexcitation fluorescence/Auger on, and default cuts unless Region.RangeCut is set. FLUKA uses DEFAULTS EM-CASCA, RADDECAY 2.0, DCYSCORE -1.0, and EMFCUT 10 keV electron/photon transport cutoffs across regions.

Question:
Given same source and nominally same geometry, which implementation would you treat as the better central reference for physical 511-keV TES background composition and delayed W2 rate? Is the observed difference more likely due to statistical fluctuation, missing physics in one code, or full-geometry runtime/cut/scoring/region coupling? What single matched diagnostic would best discriminate?
```

## File Evidence

Primary local artifacts:

- `work_fluka_harness/fluka_11_like_energy_band_stats_20260625/engineering.md`
- `engineering/crosscode_delayed_closure_20260625/05_decision/manuscript_delayed_background_statement.md`
- `engineering/crosscode_delayed_closure_20260625/05_decision/engineering_completion_audit.md`
- `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_common_raw_production_1e6/summary.md`
- `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_common_event_builder_parent_1e6/summary.md`
- `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_common_event_builder_time_topology_1e6/summary.md`
- `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_raw_coupling_decomposition_1e6/summary.md`
- `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_boundary_margin_audit_1e6/summary.md`
- `engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source/phase3_cu64_mechanism_focus_audit_1e6/summary.md`

Primary local code/config:

- `work_fluka_harness/run_phase3_cu64_common_megalib_raw.py`
- `work_fluka_harness/run_phase3_cu64_common_fluka_raw.py`
- `work_fluka_harness/run_delayed_isotope_raw_mvp.py`
- `work_fluka_harness/build_raw_scoring_smoke.py`
- `/home/ubuntu/MEGAlib_Install/megalib-main/src/cosima/src/MCParameterFile.cc`
- `/home/ubuntu/MEGAlib_Install/megalib-main/src/cosima/src/MCPhysicsList.cc`
- `/tmp/phase3prod/megalib/chunk_001_start0000001_n50000/megalib_inputs/phase3_cu64_common_megalib_raw.source`
- `/tmp/phase3prod/fluka/chunk_001_start0000001_n50000/fluka_run/phase3_cu64_common_raw.inp`

External sources:

- FLUKA official references: https://fluka.cern/documentation/references
- FLUKA user routines: https://fluka.cern/documentation/running/user-routines
- Geant4 low-energy polarized X/gamma transport: https://arxiv.org/abs/2102.02721
- Geant4 radioactive decay validation: https://arxiv.org/abs/1306.5129
- Geant4 electron energy deposition validation: https://arxiv.org/abs/1307.0933
- Geant4 electron backscattering validation: https://arxiv.org/abs/1502.01507
