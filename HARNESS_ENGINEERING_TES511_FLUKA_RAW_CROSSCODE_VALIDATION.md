---
document_type: harness_engineering
project: TES_511_BALLOON
workstream: fluka-raw-crosscode-validation
version: 1.1
status: ready-for-codex
verdict_governance: pure-function-cold-context-gatekeeper
execution_style: bounded-evidence-first
primary_language: zh-CN
purpose: 使用 FLUKA 对当前 fix5 几何、相同物理源与 day-15 活化链进行独立的 raw-level 交叉验证，区分输运代码差异、核反应模型差异与质量模型边界。
repo_url: https://github.com/lihaoyu13752201457-hue/TES_511_Balloon
tes_repo_root: /home/ubuntu/TES_511_Balloon
fluka_handoff_root: /home/ubuntu/Fluka_TES_511_Balloon
current_required_branch: delayed-source-authority-v2-20260624
current_required_head: 455999408676e9a2c9b1e531a6c8562fe880792d
baseline_digest: engineering/CLOSURE_DIGEST_20260624.md
expected_digest_git_head: 53990878401bd721679b29f573a59b5c133adc0a
completion_audit_recorded_git_head: 53990878401bd721679b29f573a59b5c133adc0a
completion_audit: engineering/delayed_source_authority_v2_20260624/00_manifest/completion_audit.json
fluka_setup_script: /home/ubuntu/fluka/setup_fluka.sh
fluka_home_expected: /home/ubuntu/fluka/fluka-4-5.1-local/usr/local/fluka
claim_boundary: 当前 detector/cryostat proxy mass model 下的 reference-exposure unresolved-line selected-rate estimate；本工程不自动升级为 flight-performance forecast。
primary_question: 在几何和物理源保持等价的条件下，FLUKA 与当前 Geant4/MEGAlib 是否给出同量级的 prompt、activation inventory 与 delayed raw TES 能量沉积？
primary_comparison_level: unsmeared raw physical energy deposition before coincidence, active-veto, Compton/FoV selection, detector response, and mission-time folding
non_goal: 不调参以迫使两代码一致；不优化侧口、屏蔽厚度或阈值；不替代完整载荷质量模型；不以单一 W2 窄窗决定代码正确与否。
geometry_authority: outputs/geometry/DEMO2_DR_v3p5_user_cylmag_redesign_multiholeW_fix5_20260621_megalib_proxy/DEMO2_DR_v3p5_minpatch_centerfinger_megalib_proxy.geo.setup
source_authority: config/megalib_sources_fullsphere20_fix5_tilt45 plus current source manifests and normalization audits
prompt_reference: engineering/background_validation_20260624/01_prompt_source_audit
activation_reference: engineering/delayed_source_authority_v2_20260624
veto_authority: Step05 post-processing E_shield < 50 keV and 1 us; recorded only for context and explicitly NOT applied in the primary FLUKA raw comparison
output_root_template: /home/ubuntu/TES_511_Balloon/engineering/fluka_crosscode_validation_YYYYMMDD/
---

# 0. 新 Codex Session 快速接手区

## 0.1 建议作为新 session 第一条消息直接粘贴

```text
你是 TES_511_BALLOON 的 FLUKA cross-code validation orchestrator。
先确认当前工作根是 `/home/ubuntu/TES_511_Balloon`，并读取位于
`/home/ubuntu/Fluka_TES_511_Balloon/HARNESS_ENGINEERING_TES511_FLUKA_RAW_CROSSCODE_VALIDATION.md`
的本 harness。先完整阅读本 harness 的第 0–6 节，只读取 allowlist 中的 authority 文件；不要浏览整个仓库，也不要修改 baseline。

当前应接上的 TES authority branch/head：
`delayed-source-authority-v2-20260624` /
`455999408676e9a2c9b1e531a6c8562fe880792d`。
若当前 HEAD 不同，不要直接失败；先记录 actual HEAD，并重新检查本 harness 列出的 authority paths、digest 和 completion audit 是否仍唯一。
注意：`engineering/CLOSURE_DIGEST_20260624.md` 与 completion audit 内部记录的 `git_head`
是生成审计时的 `53990878401bd721679b29f573a59b5c133adc0a`；当前 branch tip
`455999408676e9a2c9b1e531a6c8562fe880792d` 是把 digest/audit 增量提交到远端的 commit。
这不是冲突，除非对应文件内容或 authority paths 不存在/不唯一。

任务不是证明 Geant4 或 FLUKA 谁“正确”，而是在同一几何和同一物理源下比较：
1. raw prompt TES/shield 能量沉积；
2. eplus 停止、湮灭顶点及进入 TES 的 511 keV 光子；
3. neutron-induced Cu-64/Cu-62/I-128 residual inventory；
4. day-15 delayed raw 能谱；
5. prompt/delayed raw 比值及其代码模型差异。

主比较禁止使用 coincidence、active veto、Compton/FoV、TES smearing 和 mission-time fold。
先建立 geometry/source/scoring parity，再运行 eplus-only 与 neutron-only pilot。任何 authority 歧义、FLUKA 语义不明或资源不足都允许以 BLOCKED_* 合法结束；不得自动调几何、源或阈值。

第一阶段最小可执行目标不是 full-stat：只要 G0--G4 通过，就先跑一个 eplus-only
FLUKA raw-data smoke/MVP，生成 raw event table、primary sampling audit、run manifest 和
scoring closure。若 FLUKA 环境、source routine 或 scoring semantics 无法确认，合法停止到
对应 `BLOCKED_*`，不要猜 card 或改物理定义。
```

## 0.2 十分钟项目地图

必须区分两个目录：

```text
TES authority repo:
  /home/ubuntu/TES_511_Balloon

FLUKA handoff/harness directory:
  /home/ubuntu/Fluka_TES_511_Balloon

New outputs must be written under:
  /home/ubuntu/TES_511_Balloon/engineering/fluka_crosscode_validation_YYYYMMDD/
```

不要在 `/home/ubuntu/Fluka_TES_511_Balloon` 下生成工程输出；该目录只保存 handoff harness。

当前工程已经较强地证明：

- fix5 prompt 的 60 cm far-field radius、`pi R^2`、20 个 equal-mu 角分箱、replica/split 权重和 Step05 rate reconstruction 内部闭合；
- W2 prompt 主要来自 atmospheric-primary `eplus` 在外层被动结构中湮灭后产生的 511 keV 光子；这些 survivor 的主动屏蔽沉积为零；
- 当前 delayed W2 主要由焦平面附近 Cu 冷结构中的 neutron-induced Cu-64/Cu-62 贡献；
- 4 个 delayed position-sampling realization 给出约 10% 统计尺度的稳定结果；
- CsI 与同包络 BGO 的 W2 差异未达到统计显著；
- delayed-source v2 的方法学已闭合，但尚未 promotion 为新的 full-stat rate authority。

这些工作证明了“实现和账本没有显著的数量级 bug”，但**没有证明输入物理模型和 proxy mass model 就是真实飞行仪器**。本工程要解决的是下一个层级：独立输运代码在相同输入下是否得到相近的 raw 响应。

## 0.3 本工程必须记住的物理事实

1. **active shield 不能拒绝没有 shield deposit 的单个 511 keV 光子。**
2. **单像素 photoelectric event 没有可用于 Compton-cone veto 的多点拓扑。**
3. 被动材料既能屏蔽，也能成为 positron stopping/annihilation 或 secondary-production 的源。
4. “所有仪器都有窗口”不等于窗口等价；开口立体角、开口长度、主动准直、带电粒子标签、开口外材料和 detector area 都会改变背景。
5. FLUKA 与 Geant4 的 narrow 511 line shape 可能都不等于真实材料中的 annihilation Doppler broadening；因此 **480–550 keV 和连续谱比较优先于 0.84 keV W2 比较**。
6. cross-code agreement 只能降低“输运代码实现错误”的概率，不能弥补两边共同使用的不完整质量模型或错误外部源。

## 0.4 需要纠正的外部比较误区

不得在本工程或论文支持文档中写：

- “COSI 表中的 0.326/0.418/0.565 是各背景分量占比”；它们是对模拟分量拟合到数据的 normalization factors。
- “COSI internal component 等同 delayed activation”；公开 COSI 分量包含由对应入射粒子诱发的 prompt 和 activation interactions。
- “COSI 511 keV line 已被该论文证明由 Ge 自活化主导”；如果没有逐线来源证据，不得升级到这个结论。

正确比较应强调：COSI 是 kg 级 HPGe 宽视场全载荷，当前项目是小型聚焦 TES detector/cryostat proxy；二者的 detector self-activation、payload mass、FOV、altitude 和 event selection 均不同。

## 0.5 v1.1 优化要点（相对 v1.0）

1. 新增 `verdict_audit_agent`：terminal verdict 从 orchestrator 剥离，改由**冷上下文纯函数 gatekeeper** 裁定（§4.2、§5 的 S11G）。
2. **状态单一归属**：Executor 报 `claimed_status`，gatekeeper 裁 `terminal_status`，`FINAL_STATUS.md` 只认后者（§4.2）。
3. **Verdict quote rule**：每个 verdict tier 必须逐行引用 comparison/closure 证据（§19.6）。
4. **低能中子数据对照**：H3 与 WP07 显式记录 pointwise vs groupwise / 热散射 S(α,β) 库 / (n,γ) 数据集版本，锁定 Cu-64/I-128 ~2× 物理输入不确定度的来源。

以上只加治理与证据纪律，不改任何物理定义、几何、源或阈值。

# 1. Codex 执行合同

你是本工程的 **orchestrator**，不是自由探索者。必须完成一个有限状态、可审计、可停止的 cross-code workflow。

## 1.1 最终目标

在不改变当前物理定义的前提下：

1. 把 fix5 Geant4/MEGAlib proxy geometry 翻译为物理等价的 FLUKA combinatorial geometry；
2. 从同一个 machine-readable source authority 生成 Geant4 与 FLUKA source adapters；
3. 为两代码建立相同的 raw energy-deposition observables；
4. 先做 511 photon/eplus EM benchmark，再做 atmospheric eplus-only prompt pilot；
5. 做 neutron-only activation pilot，比较 Cu-64、Cu-62、I-128 等 residual inventory；
6. 运行八种 prompt particle families 的 raw simulation；
7. 用 FLUKA native activation-study route 计算 day-15 delayed raw spectrum；
8. 用 residual-production ledger 构建真正按生产位置抽样的 explicit delayed replay，作为第二条验证路线；
9. 对 Geant4 与 FLUKA 的 raw spectra、rates、annihilation topology、isotope inventory 和 prompt/delayed ratio 做分层比较；
10. 输出论文 claim boundary 和可引用的方法学说明，但**不自动改正文或提升 headline 数字**。

## 1.2 禁止事项

- 禁止原地修改 baseline geometry、source cards、Step05 或 manuscript；
- 禁止为了使两代码一致而调整材料、厚度、密度、源通量、角分布或 transport threshold；
- 禁止在 parity gate 通过前运行 full-stat；
- 禁止只比较 W2 就宣布 PASS/FAIL；
- 禁止把 FLUKA 当作绝对真值；
- 禁止使用 uniform-in-volume delayed source 代替真实生产位置；
- 禁止无限增加统计直到“结果好看”；
- 禁止让 subagent 再创建 subagent；
- 禁止在 FLUKA card 或 source-routine 语义不确定时凭记忆猜测。

# 2. 科学假设与可判定问题

## H0 — 源归一化假设

在同一物理 source phase space 下，两代码的每秒 incident-primary rate 必须完全一致。任何差异首先视为 adapter/normalization failure，而不是物理差异。

## H1 — 纯 511 photon EM 响应

在 geometry/material parity 通过后，单色 511 keV photon 的 attenuation、TES interaction probability、photoelectric/Compton fraction 和 shield deposition 应在较紧范围内一致。若这一层不一致，不允许解释 full background。

## H2 — atmospheric eplus prompt 机制

当前 Geant4 结果认为 W2 prompt 主要由 positron 在外层被动结构停止并湮灭后，一个 511 keV photon 到达 TES、另一个逃逸形成。FLUKA 应独立检验：

- positron stopping/annihilation region；
- annihilation vertex distribution；
- 到达 TES 的 photon parentage；
- raw TES spectrum；
- joint TES/shield energy deposition；
- single-volume/full-energy-deposit fraction。

## H3 — neutron-induced activation

FLUKA 应独立给出 Cu-64/Cu-62/I-128 等 isotope yield、region distribution、day-15 activity 和 raw delayed coupling。差异可来自核模型和 decay-chain implementation，不应被自动当成 bug。

**必须记录两代码的低能中子处理**（pointwise vs multigroup、热散射 S(α,β) 库、(n,γ) 截面数据集与版本），并与 Geant4 侧 `QGSP_BIC_HP`/`G4NDL` 并列对照：Cu-64/I-128 主要来自热/超热 (n,γ) 俘获，正是上一阶段标注的 ~2× 物理输入不确定度所在。若两代码低能中子数据处理不同，相关差异应归入 `INVESTIGATE_ACTIVATION_PHYSICS`，不得笼统称 “model spread”。

## H4 — 质量模型边界

若两代码在相同 proxy geometry 下相符，只能说明该 proxy 中的 code dependence 较小；不能说明缺失的 gondola、optical bench、lens support、electronics、pressure vessels 等对飞行背景不重要。

## H5 — narrow line-shape 边界

W2 只有 510.58–511.42 keV。两代码对 annihilation line 的 microscopic broadening 处理可能不同且都不完整。主判断以 unsmeared/broad-window integrated rate 和 topology 为准，W2 是 secondary diagnostic。

# 3. 非协商性 Authority 与边界

## 3.1 Baseline authority lock

起始时必须确认并 hash：

```text
/home/ubuntu/TES_511_Balloon/engineering/CLOSURE_DIGEST_20260624.md
/home/ubuntu/TES_511_Balloon/engineering/delayed_source_authority_v2_20260624/00_manifest/completion_audit.json
core_md/fix5_benchmarks.json
core_md/METHOD_FIX5_SIM_CLOSURE.md
outputs/geometry/DEMO2_DR_v3p5_user_cylmag_redesign_multiholeW_fix5_20260621_megalib_proxy/
config/megalib_sources_fullsphere20_fix5_tilt45/
engineering/background_validation_20260624/
engineering/delayed_source_authority_v2_20260624/
stepwise_maintenance/step05_veto_time_axis/outputs_fix5_fullstat_v2_exactpos_m50000_s260613_l1/
```

如果仓库 HEAD 与 digest/current harness 的
`455999408676e9a2c9b1e531a6c8562fe880792d` 不同：

- 记录当前 HEAD；
- 不自动认为错误；
- 重新检查 authority paths 是否仍一致；
- 若存在多个可能 authority，终止为 `BLOCKED_AMBIGUOUS_AUTHORITY`。

`completion_audit.json` 必须显示：

```text
status = PASS
completion_verdict = COMPLETE_LEGAL_NO_RATE_AUTHORITY_ENDPOINT
required artifacts = 74/74
JSON errors = 0
summary schema issues = 0
geometry mismatches = 0
forbidden path entries = 0
active processes = 0
```

若 completion audit 缺失或失败，不允许启动 FLUKA physics run；先停止到
`BLOCKED_AMBIGUOUS_AUTHORITY` 或生成新的只读 authority audit。

## 3.2 “几何不变”的操作定义

FLUKA 不能直接读取 MEGAlib `.geo`，因此“几何不变”定义为 **geometry-equivalent translation**：

- 同一 coordinate origin 和 45° instrument rotation；
- 同一 solid dimensions、Boolean apertures 和 placement；
- 同一 material composition、density、temperature-independent transport material；
- 同一 TES pixel/layer map；
- 同一 CsI/BGO active-shield volumes；
- 同一 side-port through-cut、W sleeve、entrance windows 和 passive structures；
- 同一 world/surrounding-source containment。

不允许为了简化 FLUKA 几何而删除 critical local structures。任何无法一一翻译的 solid 必须列入 `geometry_exceptions.csv`，并在 pilot 前由用户批准。

## 3.3 “源定义不变”的操作定义

不得直接手工重写一套“看起来相似”的 FLUKA source。必须先生成共享 source authority：

```text
source_phase_space_authority.json
source_energy_cdf_<particle>.npz or csv
source_angular_bins.csv
source_normalization.json
```

其中至少包含：

- 8 个 particle families；
- 20 个 equal-mu zenith bins；
- 每 bin 的 theta/mu bounds、deltaOmega、bin-integrated flux；
- energy spectrum/CDF；
- azimuth policy；
- up/down hemisphere policy；
- far-field radius = 60 cm；
- area convention = pi R^2；
- total physical rate by species；
- source location/direction sampling semantics；
- source-data SHA256。

Geant4 adapter 和 FLUKA adapter 必须从同一 authority 读取，禁止各自维护数值副本。

## 3.4 Primary raw-data 定义

主比较不使用任何 detector-analysis selection。一个 primary history 的 raw record 包含：

- 每个 TES pixel/active volume 的 physical energy deposition；
- TES total deposition；
- 每个 shield segment 和 shield total deposition；
- deposition time（仅记录，不用于 grouping）；
- first interaction process and volume where available；
- primary species, energy, direction, start position and physical weight；
- eplus annihilation vertex/region and daughter photon information where available；
- delayed history 的 isotope, isomer, decay position, source region and source weight。

Primary comparison explicitly excludes：

```text
TES Gaussian smearing
energy calibration
event grouping/coincidence
shield veto
Compton/FoV veto
single/multi-pixel selection
mission-time fold
significance
```

## 3.5 Veto authority

Step05 的 `E_shield < 50 keV`、`tau = 1 us` 只在本工程末尾作为可选 replay 检查，不能进入 primary cross-code verdict。

## 3.6 历史 FLUKA 资产边界

本机存在历史 FLUKA 工作目录：

```text
/home/ubuntu/fluka/cosmosray_bg_2602_fluka/
/home/ubuntu/fluka/megalib_fluka_480_550_crosscheck/
/home/ubuntu/fluka/megalibfix_fluka_image8_assets/
```

这些目录可以作为 **code pattern / implementation archaeology**，例如查看 user-routine
编译方式、MGDRAW 输出格式、runner 结构或 FLUKA setup 经验；但它们不是当前 fix5
数值 authority。已知不等价点包括但不限于：

- 旧模型并非当前 `DEMO2_DR_v3p5...fix5` 几何；
- 旧 source disk/radius 可能为 150 cm，而当前 authority far-field radius 是 60 cm；
- 旧角分箱可能为 10 bins / 96 deg，而当前 authority 是 20 equal-mu bins；
- 旧 delayed source 不是当前 `delayed_source_authority_v2_20260624` 的 source-v2 方法学；
- 旧 FLUKA outputs 不能作为本工程 Geant4-vs-FLUKA raw comparison 的数据点。

任何复用旧脚本必须复制/改写到新的
`/home/ubuntu/TES_511_Balloon/engineering/fluka_crosscode_validation_YYYYMMDD/scripts/`
并重新通过 G0--G4 parity gates。

# 4. Agent 架构与上下文隔离

仅允许两层：

```text
orchestrator
  ├── authority_agent
  ├── fluka_environment_agent
  ├── geometry_translation_agent
  ├── source_adapter_agent
  ├── raw_scoring_agent
  ├── em_benchmark_agent
  ├── prompt_agent
  ├── activation_agent
  ├── delayed_replay_agent
  ├── comparison_agent
  ├── verdict_audit_agent
  └── manuscript_support_agent
```

子 agent 不得创建子 agent。

## 4.1 Work packet 规则

每个 agent 只读取：

```text
work_packets/WPxx_<name>.md
00_manifest/baseline_authority_manifest.json
上一 gate 的 summary.json
本 WP 明确列出的 allowlist
```

每个 packet 必须包含：

1. 单一目标；
2. 输入 allowlist；
3. 禁止读取/修改列表；
4. 预期输出 schema；
5. acceptance criteria；
6. 资源上限；
7. 最大实现尝试次数；
8. 合法 stop states。

agent 间只能通过 `summary.json`、`summary.md` 和明确定义的 CSV/NPZ/HDF5 交换信息。大型 raw files 不直接注入另一个 agent 的上下文。

## 4.2 角色分离与状态单一归属（pure-function gatekeeper）

为防 orchestrator“给自己的工作打终分”，强制三类角色互斥、状态单一归属：

- **Executor（各 build/run agent）**：只产出证据与自报的 `claimed_status`；**不得**宣布 terminal verdict，也不得把任何 gate 自行置 PASS。
- **verdict_audit_agent（gatekeeper，纯函数 / 冷上下文）**：
  - 在**全新冷上下文**启动；只读 `11_crosscode_comparison/comparison_matrix.csv`、各 gate 的 `summary.json`/closure 字段、本 harness §19.3 预声明 tiers；**不读** orchestrator 中间推理、不读大 raw 文件；
  - 输出 `terminal_status` 必须是 §22 合法枚举之一，且按 §19.6 quote rule **逐项引用**判定所依据的 comparison row / closure 字段；
  - 纯函数：相同证据必给相同 verdict；不得发起新 run、不得改 plan、不得改任何物理/几何/源定义。
- **orchestrator**：维护 plan 与 state machine；**不得**自写 terminal verdict，也**不得覆盖** gatekeeper 裁决；仅当 gatekeeper 返回 `INCONCLUSIVE_*` 且资源门允许时，按预声明计划调度下一 tier。

**状态单一归属**：`claimed_status`（Executor 写）与 `terminal_status`（gatekeeper 写）分字段存储；`FINAL_STATUS.md` 只认 `terminal_status`；任一 gate 的 PASS 只能由 gatekeeper 依机器门 + acceptance 置位。

若无法在隔离子 agent 中运行 gatekeeper（单 session 退化），必须在 `crosscode_verdict.json` 标 `INDEPENDENCE=SINGLE_SESSION_DEGRADED`，并仍强制：终判前重置上下文、只喂 comparison summaries + §19.3 tiers、逐行引用证据。

# 5. 有限状态机

```text
S0 LOCK_AUTHORITIES
  -> G0 AUTHORITY_LOCKED | BLOCKED_AMBIGUOUS_AUTHORITY

S1 VERIFY_FLUKA_ENVIRONMENT
  -> G1 FLUKA_READY | BLOCKED_FLUKA_NOT_AVAILABLE | BLOCKED_LICENSE

S2 TRANSLATE_AND_AUDIT_GEOMETRY
  -> G2 GEOMETRY_PARITY_PASS | BLOCKED_GEOMETRY_TRANSLATION

S3 BUILD_SHARED_SOURCE_AUTHORITY_AND_ADAPTERS
  -> G3 SOURCE_PARITY_PASS | BLOCKED_SOURCE_SEMANTICS

S4 BUILD_RAW_SCORING_AND_EVENT_SCHEMA
  -> G4 RAW_SCORING_PASS | BLOCKED_SCORING_SEMANTICS

S4M RUN_MINIMUM_RAW_DATA_MVP
  -> G4M RAW_DATA_MVP_PASS | BLOCKED_RAW_DATA_MVP | RESOURCE_BLOCKED

S5 RUN_511_PHOTON_AND_SIMPLE_MATERIAL_BENCHMARKS
  -> G5 EM_BENCHMARK_PASS | INVESTIGATE_EM_PHYSICS

S6 RUN_EPLUS_ONLY_PROMPT_PILOT
  -> G6 EPLUS_PILOT_COMPLETE | RESOURCE_BLOCKED

S7 RUN_NEUTRON_ACTIVATION_PILOT
  -> G7 ACTIVATION_PILOT_COMPLETE | INVESTIGATE_ACTIVATION_SETUP

S8 RUN_FULL_PROMPT_RAW
  -> G8 FULL_PROMPT_COMPLETE | RESOURCE_BLOCKED

S9 RUN_NATIVE_FLUKA_DAY15_DELAYED
  -> G9 NATIVE_DELAYED_COMPLETE | BLOCKED_ACTIVATION_SEMANTICS

S10 RUN_TRUE_POSITION_SAMPLED_DELAYED_REPLAY
  -> G10 SAMPLED_DELAYED_COMPLETE | BLOCKED_ISOTOPE_REPLAY

S11 CROSSCODE_COMPARE            # comparison_agent 仅组装证据，不下 verdict
  -> G11 EVIDENCE_ASSEMBLED | INCONCLUSIVE_STATISTICS

S11G GATEKEEPER_VERDICT          # verdict_audit_agent 冷上下文纯函数裁定（§4.2）
  -> CROSSCODE_STRONG_AGREEMENT | CROSSCODE_CONSISTENT_WITH_MODEL_SPREAD |
       INVESTIGATE_PROMPT_PHYSICS | INVESTIGATE_ACTIVATION_PHYSICS |
       LINE_SHAPE_MODEL_DIFFERENCE | INCONCLUSIVE_STATISTICS

S12 BUILD_PAPER_SUPPORT          # 仅当 S11G 给出非 BLOCKED 终态后
  -> DONE
```

任何 `BLOCKED_*`、`INVESTIGATE_*` 或 `INCONCLUSIVE_*` 都是合法终点，不得自动改变科学定义以清除状态。

# 6. 循环、资源与停止规则

- 每个 WP 最多 2 次实现尝试；
- 每个 deterministic validation failure 最多修复并重试 1 次；
- 物理结果不符合预期不是软件错误，不触发自动重跑；
- pilot 统计不足时只允许升级到一个预先声明的 next tier；
- full prompt 和 delayed run 必须先生成 CPU、disk、wall-time estimate；
- 未经用户显式批准，不得启动预计 > 7 CPU-day、> 100 GB 或 > 10^8 histories 的任务；
- 不允许以“减小误差直到显著”为目的无上限增加统计；
- 不允许使用 variance reduction，除非两代码都定义了可证明无偏且等价的方案；primary comparison 优先 analogue/unbiased runs；
- 所有 random seeds、executable hashes、compiler、FLUKA version、data libraries 和 environment variables 必须写入 manifest。

# 7. 最终交付物目录

```text
engineering/fluka_crosscode_validation_YYYYMMDD/
  00_manifest/
    baseline_authority_manifest.json
    baseline_authority_manifest.md
    file_hashes.sha256
    git_status.txt
    execution_environment.json
    decision_log.md
    FINAL_STATUS.md

  scripts/
    README.md
    build_authority_manifest.py
    detect_fluka_environment.py
    build_geometry_translation.py
    build_source_authority.py
    build_raw_scoring_smoke.py
    run_eplus_raw_mvp.py

  work_packets/
    WP00_authority_lock.md
    WP01_fluka_environment.md
    WP02_geometry_translation.md
    WP03_source_adapter.md
    WP04_raw_scoring.md
    WP05_em_benchmarks.md
    WP06_eplus_prompt_pilot.md
    WP07_neutron_activation_pilot.md
    WP08_full_prompt.md
    WP09_native_delayed.md
    WP10_sampled_delayed.md
    WP11_crosscode_comparison.md
    WP11G_gatekeeper_verdict.md
    WP12_manuscript_support.md

  01_fluka_environment/
    fluka_setup_script.txt
    fluka_version.txt
    flair_version.txt
    executable_manifest.json
    compiler_manifest.json
    data_library_manifest.json
    manual_semantics_notes.md

  02_geometry_translation/
    region_map.csv
    material_map.csv
    geometry_exceptions.csv
    geometry_mass_closure.csv
    geometry_volume_closure.csv
    critical_dimension_closure.csv
    aperture_raytrace_geant4.csv
    aperture_raytrace_fluka.csv
    aperture_raytrace_comparison.csv
    overlap_check.log
    geometry_parity.json
    geometry_parity.md
    fluka_geometry/

  03_source_authority/
    source_phase_space_authority.json
    source_angular_bins.csv
    source_energy_cdf_*.npz
    source_normalization.json
    geant4_adapter_reconstruction.csv
    fluka_adapter_sampling_audit.csv
    source_parity.json
    source_parity.md
    source_routines/

  04_raw_scoring/
    raw_event_schema.json
    process_name_crosswalk.csv
    volume_name_crosswalk.csv
    scoring_closure.json
    scoring_closure.md
    scoring_routines/

  05_em_benchmarks/
    mono511_component_tests.csv
    mono511_full_geometry.csv
    positron_material_slab_tests.csv
    em_benchmark_comparison.csv
    em_benchmark_figures/
    em_benchmark_summary.json
    em_benchmark_summary.md

  06_eplus_prompt_pilot/
    run_manifest.csv
    raw_events/
      raw_events.parquet
      raw_events.csv
      primaries.csv
      source_sampling_audit.csv
    tes_spectrum.csv
    shield_spectrum.csv
    tes_shield_joint.csv
    annihilation_vertices.csv
    annihilation_region_summary.csv
    first_tes_process_summary.csv
    scoring_closure.json
    mvp_raw_data_verdict.json
    eplus_pilot_comparison.json
    eplus_pilot_comparison.md

  07_neutron_activation_pilot/
    run_manifest.csv
    residual_ledger.parquet
    residual_inventory_by_isotope.csv
    residual_inventory_by_region.csv
    residual_position_summary.csv
    day15_activity_by_isotope.csv
    day15_activity_by_region.csv
    activation_pilot_comparison.json
    activation_pilot_comparison.md

  08_full_prompt_raw/
    run_manifest.csv
    raw_spectra_by_species.csv
    raw_rates_by_species.csv
    raw_tes_shield_joint.csv
    full_prompt_summary.json
    full_prompt_summary.md

  09_native_delayed/
    irradiation_profile.json
    residual_inventory.csv
    day15_activity.csv
    native_delayed_spectrum.csv
    native_delayed_by_isotope.csv
    native_delayed_by_region.csv
    native_delayed_summary.json
    native_delayed_summary.md

  10_sampled_delayed/
    residual_position_ledger.parquet
    sampled_source_manifest.json
    sampled_source_inventory.csv
    sampled_source_position_closure.csv
    sampled_delayed_runs.csv
    sampled_delayed_spectrum.csv
    sampled_delayed_by_isotope.csv
    sampled_delayed_by_region.csv
    sampled_delayed_summary.json
    sampled_delayed_summary.md

  11_crosscode_comparison/
    comparison_matrix.csv
    raw_band_rates.csv
    prompt_delayed_ratio.csv
    isotope_inventory_comparison.csv
    region_contribution_comparison.csv
    spectral_ratio.csv
    uncertainty_budget.csv
    interpretation_decision_tree.md
    verdict_audit_inputs_manifest.json   # gatekeeper 冷上下文只读的证据清单
    crosscode_verdict.json               # gatekeeper 裁定：terminal_status + 逐行证据引用
    crosscode_verdict.md
    figures/

  12_manuscript_support/
    manuscript_claim_boundary.md
    manuscript_insertions_en.md
    manuscript_insertions_cn.md
    supplement_crosscode_methods.md
    supplement_crosscode_tables.md
    numbers_manifest.json
```

# 8. WP00 — Authority lock

## 8.1 操作

1. 读取 digest、repo authority index、current geometry/source manifests；
2. 记录 actual git HEAD、dirty status 和 untracked files；
3. 对所有 baseline inputs SHA256；
4. 标记 `old/`、legacy new_geo_re、未 promotion v2 delayed numbers 为非 authority；
5. 禁止任何 agent 写入 baseline paths；
6. 生成只读 copy/reference map，不复制大型 raw files，除非执行需要。

## 8.2 G0 acceptance

- 每个输入只有一个 `CURRENT` authority；
- geometry/source/normalization/digest hashes 完整；
- 存在歧义则 `BLOCKED_AMBIGUOUS_AUTHORITY`。

# 9. WP01 — FLUKA environment 与语义锁定

## 9.1 目标

确认可用的 FLUKA 版本、license、FLAIR、compiler、nuclear data 和 user-routine toolchain。

## 9.2 强制动作

- 只使用官方安装和官方当前 manual；
- 先尝试 source 本机 setup：

  ```bash
  . /home/ubuntu/fluka/setup_fluka.sh
  ```

  预期导出：

  ```text
  FLUKA_HOME=/home/ubuntu/fluka/fluka-4-5.1-local/usr/local/fluka
  FLUKADATA=/home/ubuntu/fluka/fluka-4-5.1-local/usr/local/fluka/data
  PATH contains /home/ubuntu/fluka/fluka-4-5.1-local/usr/local/fluka/bin
  ```

  之后必须定位 `rfluka`、`lfluka`、`fluka`。若 setup 脚本不存在或 executables
  不可执行，输出 `BLOCKED_FLUKA_NOT_AVAILABLE`，不得转用旧 run outputs 伪造 raw data。
- 记录 FLUKA exact version，不允许只写“FLUKA”；
- 编译最小 `source`、`mgdraw`、`usrrnc` routines；
- 跑官方或本地最小 smoke input；
- 逐项确认以下语义并在 `manual_semantics_notes.md` 引用 manual section：
  - far-field/custom source sampling；
  - event/history weight；
  - MGDRAW or equivalent energy-deposition logging；
  - `RADDECAY` semi-analogue vs activation-study；
  - `IRRPROFI`, `DCYTIMES`, `DCYSCORE`, `RESNUCLEi`；
  - `USRRNC` residual nucleus callback and fields；
  - isotope/isomer injection route；
  - prompt and delayed transport cutoffs。

语义无法由当前安装 manual 确认时，状态为 `BLOCKED_FLUKA_SEMANTICS`，不得依赖模型记忆。

# 10. WP02 — Geometry translation 与 parity audit

## 10.1 翻译策略

优先建立一个 deterministic translator 或 explicit geometry ledger，而不是手工在 FLAIR 中散乱重画。每个 Geant4/MEGAlib logical volume 映射到：

```text
source_volume_name
FLUKA body/region name
shape type
position/rotation
dimensions
material
density
calculated volume
calculated mass
critical flag
translation status
```

## 10.2 Critical geometry list

至少包括：

- 全部 TES Ta pixels/layers；
- substrate/support disks；
- Be/Al/Kapton entrance windows；
- 50 mK Cu can/cold plates；
- Still/4 K/60 K/vacuum-jacket shells；
- Cu/W passive liners；
- W bottom plate；
- side W sleeve/multihole structures；
- CsI active shield segments；
- exact rectangular side-port through-cuts；
- service proxies located near focal plane；
- global instrument rotation。

## 10.3 Parity tests

1. **Material parity:** elemental composition and density exact or explicitly documented；
2. **Dimension parity:** numeric source values reproduced；
3. **Volume/mass closure:** critical component relative difference target <0.5%，total modeled mass <0.1%；
4. **Aperture map:** 从 far-field/side-port direction 发射至少 10,000 条 non-interacting rays，比较每条 ray 的 ordered material path and path length；
5. **511 attenuation map:** 用 511 keV photons 做无 detector-response transmission test；
6. **Overlap/lost-region check:** 无重叠、无未赋材 region、无 unintended void；
7. **Pixel map:** TES layer/pixel ID 一一对应。

任何 critical aperture/material-path mismatch 都是 blocking，不允许以总质量闭合替代局部路径闭合。

# 11. WP03 — Shared source authority 与 adapters

## 11.1 Source authority construction

从当前 audited prompt source inputs 生成唯一的 code-independent source package。不得从 Step05 rates 反推 source。

对于 particle family `j`、angular bin `k`、energy bin/CDF `m`，记录：

```text
particle
energy distribution
theta/mu interval
phi distribution
deltaOmega
bin-integrated flux [cm^-2 s^-1]
far-field radius [cm]
area convention
physical rate [s^-1]
sampling probability
history weight
```

## 11.2 FLUKA adapter requirements

- custom source routine 从 authority 文件读取；
- 对给定 direction，在垂直于 direction 的 60 cm disk 上采样等价入射点，或实现经 analytic proof 与 Cosima FarFieldAreaSource 等价的方案；
- 不重复乘 `cos(theta)`；
- 不重复乘 solid angle；
- sampling probability 与 history weight 分开记录；
- 每 history 输出 source audit row；
- 每个 species 至少 10^6 次无输运采样检查 energy、mu、phi、position distribution。

## 11.3 Source parity acceptance

- integrated flux per species relative difference <1e-6；
- 20 angular bins flux closure <1e-6；
- far-field radius exactly 60 cm；
- area exactly `pi*60^2` within floating-point tolerance；
- generated energy/mu distributions 通过预声明的 statistical tests；
- simple analytical target crossing-rate benchmark within MC uncertainty。

# 12. WP04 — Raw scoring schema

## 12.1 Event-level authority schema

建议使用 Parquet/HDF5，至少字段：

```text
code
run_id
seed
history_id
stream                 # prompt or delayed
primary_tag
primary_energy_keV
primary_x_cm, primary_y_cm, primary_z_cm
primary_dx, primary_dy, primary_dz
history_weight
volume_id
volume_name
material_name
detector_kind          # TES_PIXEL / ACTIVE_SHIELD / OTHER
deposit_keV
deposit_time_s
track_id
parent_track_id
particle
creator_process
interaction_process
x_cm, y_cm, z_cm
isotope_Z, isotope_A, isomer
source_region
source_x_cm, source_y_cm, source_z_cm
```

若 FLUKA 无法提供某个 process-name field，必须保留 core energy-deposition fields，并把不可用字段标为 `NOT_AVAILABLE`，不得伪造 crosswalk。

## 12.2 Raw observables

对每个 history 生成：

- `tes_total_keV`；
- `shield_total_keV`；
- number of hit TES pixels；
- max TES pixel energy；
- any TES deposition；
- TES 50–8000 keV；
- 100–300、300–480、480–550、W2、550–800、800–1500、1500–3000、3000–8000 keV；
- shield `>0` 和 `>=50 keV` flags（只作 raw joint distribution，不作为 selection）；
- eplus annihilation vertex and number/energy/direction of annihilation photons；
- delayed isotope/region labels。

## 12.3 Scoring closure

Event dump 的总 energy deposition 必须与 independent FLUKA built-in scoring 在统计范围内闭合。未闭合不得进入 physics comparison。

## 12.4 Minimum raw-data MVP gate

本工程面向新 session 的最小可执行成功条件是：在 G0--G4 均通过后，先生成一个
**eplus-only FLUKA raw-data MVP**。这不是 physics verdict，也不用于论文数字；它只证明
当前 harness 足以从当前 TES authority 生成可审计 FLUKA raw event data。

### 触发条件

必须已经满足：

- authority lock PASS；
- FLUKA setup、version、manual semantics smoke PASS；
- fix5 geometry translation 至少覆盖 eplus pilot 所需 critical volumes，且无 blocking
  aperture/material-path exception；
- shared source authority 可生成 eplus adapter，far-field radius=60 cm，20 equal-mu bins
  和 `pi*60^2` area closure PASS；
- raw scoring routine 能记录 TES/shield deposition，并与内置 scoring 做 smoke closure。

### 默认运行规模

默认只跑：

```text
particle = eplus
histories = 1000--10000
seeds = 1 smoke seed, then 3 seeds only if smoke passes
transport = analogue/unbiased
selection = none
output = raw event data before veto/coincidence/topology/smearing
```

若 1000 histories 已暴露 scoring/source/geometry failure，立即停止并修 deterministic bug；不得因为
raw W2 事件少而自动扩大统计。若预计输出超过 5 GB 或 wall time 超过 2 h，必须先写
`pilot_resource_request.md` 并停止到 `RESOURCE_BLOCKED`，除非用户批准。

### 必须输出

```text
06_eplus_prompt_pilot/run_manifest.csv
06_eplus_prompt_pilot/raw_events/primaries.csv
06_eplus_prompt_pilot/raw_events/source_sampling_audit.csv
06_eplus_prompt_pilot/raw_events/raw_events.parquet
06_eplus_prompt_pilot/raw_events/raw_events.csv
06_eplus_prompt_pilot/scoring_closure.json
06_eplus_prompt_pilot/mvp_raw_data_verdict.json
06_eplus_prompt_pilot/summary.json
06_eplus_prompt_pilot/summary.md
```

`raw_events.parquet` 为首选；若当前 Python 环境没有 parquet writer，必须写 CSV 并在
`mvp_raw_data_verdict.json` 中标明 `parquet_unavailable=true`，不得因此阻断 raw-data MVP。

### 最小字段

`raw_events` 至少包含：

```text
run_id, seed, history_id, stream, primary_tag, primary_energy_keV,
primary_x_cm, primary_y_cm, primary_z_cm, primary_dx, primary_dy, primary_dz,
history_weight, volume_name, detector_kind, deposit_keV, deposit_time_s,
particle, track_id, parent_track_id, interaction_process,
x_cm, y_cm, z_cm, tes_total_keV, shield_total_keV
```

若 FLUKA 当前 user-routine 接口无法提供 process 或 ancestry 字段，填 `NOT_AVAILABLE` 并在
`process_name_crosswalk.csv` / `mvp_raw_data_verdict.json` 中解释。能量、history id、weight、
primary phase-space 和 TES/shield deposition 不得缺失。

### G4M acceptance

`mvp_raw_data_verdict.json` 必须给出：

```text
status = RAW_DATA_MVP_PASS | BLOCKED_RAW_DATA_MVP
histories_generated
raw_event_rows
primaries_rows
source_sampling_status
geometry_hash
source_authority_hash
fluka_executable_hash
scoring_closure_status
known_missing_optional_fields
```

只有 `RAW_DATA_MVP_PASS` 后，才能进入 mono-511 benchmark、eplus pilot physics comparison
或 full prompt planning。

# 13. WP05 — 511 photon 与 simple-material EM benchmarks

Full geometry 前先做最小基准：

## 13.1 Mono-511 photon

- vacuum -> single slab of Al, Cu, W, Ta, CsI/BGO, Be；
- 与当前代码同厚度或若干标准厚度；
- 比较 transmission、photoelectric、Compton、pair production（若适用）、energy deposition；
- full geometry 从 science aperture 入射 511 keV pencil/spot beam；
- full geometry isotropic 511 photons at selected external surfaces。

## 13.2 Positron material tests

在 Al、Cu、W、CsI/BGO 中注入与 atmospheric eplus spectrum 相关的代表能量：

- stopping range；
- annihilation-in-flight/rest fraction；
- annihilation vertex；
- photon multiplicity and energy；
- escape probability；
- TES-like downstream absorber full-energy peak probability。

## 13.3 Gate interpretation

- Pure photon attenuation 若差 >20%：优先检查 geometry/material/threshold；
- eplus topology 差 20–50% 可视为 model spread；
- 差 > factor 2：`INVESTIGATE_EM_PHYSICS`，full run 暂停。

# 14. WP06 — Atmospheric eplus-only prompt pilot

只有 G4M `RAW_DATA_MVP_PASS` 后才能进入本 WP 的 physics comparison。G4M 产出的
eplus raw event table 可以作为本 WP 的 smoke seed；若统计不足，只能按预声明资源门升级。

## 14.1 运行

- 只启用 authority `eplus` source；
- 至少 3 seeds；
- 统计目标以 raw TES 480–550 keV 有效计数为准，而不是总 histories；
- 先输出 resource estimate；
- 同时从 Geant4 authority 提取匹配 raw observables；若现有 raw 文件不含必要 provenance，只允许做一个 matched low-stat Geant4 replay，不得改物理配置。

## 14.2 必须比较

- any-TES raw rate；
- 50–8000、480–550、W2 raw rate；
- TES/shield joint distribution；
- annihilation vertex map by material/region；
- one vs two 511 photons reaching detector vicinity；
- first TES process；
- single/multi-pixel raw topology；
- fraction with shield total exactly zero / below 50 keV；
- broad spectrum shape。

W2 结果必须附一句：`secondary diagnostic; sensitive to annihilation-line-shape modeling`。

# 15. WP07 — Neutron-only activation pilot

## 15.1 目标

在不支付 full 8-family 成本前，验证最重要的 W2-delayed production channel。

## 15.2 运行要求

- 使用相同 neutron source authority；
- analogue or demonstrably unbiased transport；
- 启用 residual inventory scoring；
- 记录并写入 manifest：低能中子输运模式（pointwise/groupwise）、热散射 S(α,β) 库、(n,γ) 截面数据集与版本，与 Geant4 `QGSP_BIC_HP`/`G4NDL` 并列对照（这是 Cu-64/I-128 ~2× 不确定度的物理根处）；
- 通过 `USRRNC` 或当前版本等价接口记录每个 residual：
  - Z, A, isomer；
  - x,y,z；
  - region/material；
  - history/weight；
  - parent projectile tag；
- 使用 15 d constant irradiation profile 构造 day-15 activity；
- 输出 Cu-64、Cu-62、I-128、Na-24、W isotopes 的 production and activity；
- 同时输出所有 isotope inventory，禁止只记录预期核素。

## 15.3 Gate

- residual ledger 与 built-in `RESNUCLEi`/activity scoring closure；
- top isotope/region 稳定；
- Cu-64/Cu-62 statistical uncertainty 可判读；
- 若关键 isotope yield 只有极少 counts，允许一次预声明的统计升级。

# 16. WP08 — Full prompt raw simulation

只有 G2–G7 通过后运行。

- 8 particle families；
- same source authority；
- per-species independent seeds；
- output rate per physical second；
- 保留 species-separated spectra；
- 不做 coincidence/veto/Compton；
- primary report 用 50–8000 和 480–550 keV；
- W2 作为 secondary；
- 输出 `sum_w`、`sum_w2`、effective events and MC uncertainty。

# 17. WP09 — Native FLUKA day-15 delayed route

## 17.1 主路线

使用当前 FLUKA 版本官方 activation-study workflow：

- residual production from the same atmospheric particle sources；
- `RADDECAY` activation-study mode；
- `IRRPROFI` 表示 15 d exposure，beam intensity 与 source physical rate 一致；
- `DCYTIMES`/`DCYSCORE` 在 day 15 或经 manual 证明等价的时点评分；
- `RESNUCLEi`/activity scoring；
- prompt and delayed EM cutoffs 独立合理设置，但不得为了匹配 Geant4 调整；
- daughter feeding included according to FLUKA native analytical evolution；
- output raw TES/shield deposition spectra and isotope/region contributions。

**所有 card 语义必须由安装版本 manual 确认。** 本 harness 不授权 Codex 凭本段文字直接拼 card。

## 17.2 真实位置证明

- 使用 `USRRNC` ledger 记录 residual production positions；
- 抽样检查 delayed emission origin 是否与 residual production region/position 绑定；
- 输出 isotope-position density maps；
- 禁止仅以 region-uniform source 替代真实 residual distribution。

## 17.3 Native route boundary

FLUKA activation-study 结果是 cross-code main delayed estimate，但它可能使用 analytical weighting 而非可逐个自然解释的 decay event list。必须同时保留 binned scoring 和 inventory evidence。

# 18. WP10 — Explicit true-production-position sampled delayed replay

这是为了与当前 Geant4 production-position-sampled method 做同构检查，不替代 WP09 native route。

## 18.1 Source construction

从 FLUKA residual ledger 与 native day-15 activity 生成：

```text
(tag, region, material, Z, A, isomer, x, y, z, production_weight, day15_activity_weight)
```

在每个完整 key 内，按 physical activity 权重抽样真实 residual positions。不得：

- 丢失 projectile tag；
- 合并 ground/isomer states；
- 用 volume centroid；
- 均匀体采样；
- 以 raw residual count 替代 day-15 activity。

## 18.2 Replay

- custom FLUKA source routine 读取 sampled ledger；
- 注入 isotope/isomer at exact sampled position；
- 使用 semi-analogue radioactive decay transport；
- 至少 3 position-sampling seeds；
- M 和 decay histories 由 pilot efficiency 决定并有资源门控；
- 输出 inventory closure、position closure、raw TES spectrum and selected isotope/region contributions。

## 18.3 必须披露的 FLUKA 限制

- semi-analogue radioactive-decay spectra 是 inclusive，未必重现 correlated gamma cascades；
- isomer production/decay treatment 可能与 Geant4 不同；
- 若当前 FLUKA 版本不能可靠注入指定 isomer，状态为 `BLOCKED_ISOTOPE_REPLAY`，不得把 ground-state-only replay 伪装成完整结果。

# 19. WP11 — Cross-code comparison

## 19.1 比较层级

按顺序解释，禁止跳层：

1. geometry/material parity；
2. mono-511 photon response；
3. eplus-only raw prompt；
4. neutron residual inventory；
5. full prompt raw；
6. native delayed raw；
7. explicit sampled delayed raw；
8. optional application of common Step05-like cuts。

## 19.2 Primary metrics

```text
R(any TES > 0)
R(TES 50-8000 keV)
R(480-550 keV)
R(W2) [secondary]
R(shield > 0)
R(shield >= 50 keV)
TES/shield joint spectrum
prompt/delayed raw ratio
Cu-64, Cu-62, I-128 day-15 Bq
raw delayed rate by isotope and region
annihilation vertex distribution
```

## 19.3 预声明 verdict tiers

下列 tier **由 §4.2 的 verdict_audit_agent（冷上下文纯函数）套用**；comparison_agent/orchestrator 只提供证据，不得自行宣布 terminal verdict。

### `CROSSCODE_STRONG_AGREEMENT`

- geometry/source/scoring gates all PASS；
- pure 511 photon response within ~20%；
- broad-window prompt and delayed rates within ~30% including MC errors；
- isotope/region ordering consistent。

### `CROSSCODE_CONSISTENT_WITH_MODEL_SPREAD`

- broad prompt and delayed rates within factor 2；
- dominant mechanisms and top regions/isotopes一致；
- differences can reasonably be assigned to EM/hadronic/activation model spread。

### `INVESTIGATE_PROMPT_PHYSICS`

- geometry/source parity PASS；
- pure 511 photon benchmark passes；
- eplus annihilation topology or broad raw prompt differs by > factor 2。

### `INVESTIGATE_ACTIVATION_PHYSICS`

- residual Cu/I inventory or delayed broad rate differs by > factor 2；
- or top isotope/region ordering changes materially。

### `NORMALIZATION_OR_GEOMETRY_FAILURE`

- source integrated rate, local material path, mass or scoring closure fails。此时禁止物理解读。

### `INCONCLUSIVE_STATISTICS`

- uncertainty too large to distinguish factor-2 differences after one approved statistics escalation。

**差 > factor 3 必须进入 focused investigation；不得自动决定哪一代码错误。**

## 19.4 Narrow W2 解释规则

- W2 不得单独决定 cross-code verdict；
- 报告 unsmeared W2，同时报告 480–550 和至少一个更宽 line region；
- 对 annihilation-line shape 做独立 sensitivity display；
- 不允许把 COSI 的 phenomenological Voigt 参数直接当作本仪器材料的真实 response correction；
- 若 broad rate 一致、W2 不一致，优先标为 `LINE_SHAPE_MODEL_DIFFERENCE`。

## 19.5 结果解释矩阵

| 结果 | 合理解释 | 下一步 |
|---|---|---|
| FLUKA 与 Geant4 prompt/delayed 都相近 | 当前代码依赖较小；proxy mass/source physical uncertainty仍在 | 论文可增加 cross-code validation，但不升级 flight claim |
| prompt 相差大、activation 相近 | eplus stopping/annihilation/EM transport 或 aperture coupling 差异 | 检查 simple-material benchmark与 vertex maps |
| activation 相差大、prompt 相近 | nuclear model、low-energy neutron data、isomer/decay chain 差异 | 对 Cu/I cross sections 与 measured data 做专项 benchmark |
| 两者都相近但仍与公开 flight instrument不同 | 主要是 geometry/payload architecture/selection不可比 | 不再用 cross-code追逐，转向 mass-model envelope或实测校准 |
| 两者都差且 parity fail | 工程实现失败 | 修 parity，不做物理解读 |

## 19.6 Verdict quote rule（gatekeeper 强制）

verdict_audit_agent 赋的每一个 tier，必须在 `crosscode_verdict.json`/`.md` 中逐项附判定证据指针：

- 用到的 `comparison_matrix.csv` 行（metric、code-A value、code-B value、ratio、MC sigma）；
- 相关 gate 的 closure 字段（geometry mass/volume closure、source parity、scoring closure、aperture raytrace）；
- 命中的 §19.3 阈值（例：“broad delayed ratio 1.7 ∈ [0.5, 2] → CONSISTENT_WITH_MODEL_SPREAD”）。

无证据行的 verdict 无效。任一 metric 差 > factor 3 必须单列并指向 §19.5 决策行，不得被平均/聚合掩盖。

# 20. WP12 — 论文支持

## 20.1 不自动改正文

本工程只输出候选文本和数字 manifest。任何 headline 数字替换必须由用户另行批准。

## 20.2 可形成的论文贡献

若至少达到 `CROSSCODE_CONSISTENT_WITH_MODEL_SPREAD`：

- 可以声称关键 prompt/activation mechanism 经独立 transport code 交叉检查；
- 可以给出 raw-level cross-code systematic envelope；
- 可以把 prompt dominance 从“单一 Geant4 实现结果”升级为“在两套输运框架中均出现的 proxy-model feature”；
- 可以更有力地解释 active shield 与 Compton consistency selection为何不拒绝 clean single-photon annihilation events；
- 可在 Supplement 中给出 geometry/source parity、raw spectra 和 isotope inventory。

若未达到：

- 仍然有价值，因为 mismatch 本身定义了 model systematic；
- 论文应扩大 activation/atmospheric input uncertainty；
- 不得选择性引用较有利的一套代码。

## 20.3 建议输出的英文边界句

```text
An independent FLUKA transport calculation was performed using a geometry- and source-matched representation of the detector/cryostat proxy. The primary comparison was made at the unsmeared energy-deposition level, before anticoincidence, event-topology, and mission-time selections. [Describe quantitative agreement or discrepancy here.] This cross-code comparison constrains transport-model dependence for the present proxy mass model but does not address omitted payload mass or uncertainties common to both environmental source models.
```

# 21. Acceptance checklist

在 `FINAL_STATUS.md` 中逐项回答：

- [ ] Authority unique and hashed？
- [ ] FLUKA version/license/manual semantics locked？
- [ ] Critical geometry dimensions/materials/paths equivalent？
- [ ] Source flux/energy/angular sampling equivalent？
- [ ] Raw event/scoring closure passed？
- [ ] Minimum eplus-only raw-data MVP produced？
- [ ] Mono-511 photon benchmark passed？
- [ ] eplus-only topology compared？
- [ ] neutron residual inventory compared？
- [ ] Full prompt raw rates available？
- [ ] Native day-15 delayed raw result available？
- [ ] True-position sampled delayed replay available or legally BLOCKED？
- [ ] Broad spectra compared before W2？
- [ ] MC uncertainties and seeds reported？
- [ ] No geometry/source/threshold tuning occurred？
- [ ] Terminal verdict 由冷上下文 verdict_audit_agent（纯函数）裁定，orchestrator 未覆盖？
- [ ] 每个 verdict tier 附 comparison-row / closure 证据指针（§19.6 quote rule）？
- [ ] claimed_status 与 terminal_status 分离，FINAL_STATUS 只认 terminal？
- [ ] 两代码低能中子数据处理（pointwise/groupwise、热散射库、(n,γ) 数据集）已记录对照？
- [ ] Claim boundary preserved？

# 22. 合法终态模板

```text
FINAL_STATUS: CROSSCODE_STRONG_AGREEMENT
FINAL_STATUS: CROSSCODE_CONSISTENT_WITH_MODEL_SPREAD
FINAL_STATUS: INVESTIGATE_PROMPT_PHYSICS
FINAL_STATUS: INVESTIGATE_ACTIVATION_PHYSICS
FINAL_STATUS: LINE_SHAPE_MODEL_DIFFERENCE
FINAL_STATUS: INCONCLUSIVE_STATISTICS
FINAL_STATUS: BLOCKED_AMBIGUOUS_AUTHORITY
FINAL_STATUS: BLOCKED_FLUKA_NOT_AVAILABLE
FINAL_STATUS: BLOCKED_FLUKA_SEMANTICS
FINAL_STATUS: BLOCKED_GEOMETRY_TRANSLATION
FINAL_STATUS: BLOCKED_SOURCE_SEMANTICS
FINAL_STATUS: BLOCKED_SCORING_SEMANTICS
FINAL_STATUS: BLOCKED_RAW_DATA_MVP
FINAL_STATUS: BLOCKED_ACTIVATION_SEMANTICS
FINAL_STATUS: BLOCKED_ISOTOPE_REPLAY
FINAL_STATUS: RESOURCE_BLOCKED
```

`BLOCKED_*` 是合格工程终点。不得通过改动 baseline physics definition 来强行获得 PASS。

# 23. 官方技术参考（执行时必须以安装版本文档为准）

- FLUKA online manual: `RADDECAY`, `IRRPROFI`, `DCYTIMES`, `DCYSCORE`, `RESNUCLEi`, user routines and combinatorial geometry sections。
- FLUKA `USRRNC` documentation/training: residual Z/A/isomer、position、region and weight callback。
- FLUKA user-routine build instructions for custom source/scoring executables。
- Current TES_511_BALLOON source/geometry/normalization authorities listed in WP00。

任何文档与安装版本行为冲突时，安装版本的 official manual 和 executable smoke test 优先，冲突必须写入 `decision_log.md`。
