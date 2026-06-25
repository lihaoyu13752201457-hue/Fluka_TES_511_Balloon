# 交接笔记：FLUKA cross-code 的并行化、主线偏离与独立源 bug

- date: 2026-06-25
- scope: 记录两次 review 讨论的结论，供下一个 codex session / 维护者直接接手。
- 性质：诊断 + 修复方案，**只读分析**得出，未改动任何实现脚本。
- 关联：`tes511_alignment_status_20260625.md`、`eplus_alignment_status_20260624.md`、
  上层 harness `HARNESS_ENGINEERING_TES511_FLUKA_RAW_CROSSCODE_VALIDATION.md`。

---

## TL;DR（三件事）

- **a. 多线程不崩溃**：当前 `--max-parallel 1`（串行）是为了规避"终端/进程弹窗"，
  代价是 24 核只用 1 核、还出现过一段 **4h18m 的 stall**。正确做法是把**一个 driver
  进程后台 detached 启动**，并行池放在它**内部**（harness 只看到 1 个进程），
  `--max-parallel ≈ 20` + per-chunk 超时 watchdog + 少切块。
- **b. 偏离主线**：用 **replay G4 primaries** 代替独立源(defeat H0)、串行+stall、
  输出写进了 `Fluka_TES_511_Balloon`(违反 harness §0.2)、source-mode 切换没进
  `decision_log.md`、`source_parity` 是**假阳性 gate**、整条 delayed/activation(WP07–WP10)空缺。
- **c. 不要 replay，改独立源并修 bug**：独立源能谱**整体 ×1000 过热**(keV 被当 MeV)，
  外加 **×8 归一化**默认值错误。修这两处 + 加一道"对 `.sim.gz` 真值校验"的 gate，
  独立源就能对齐，replay 这根拐杖可以丢掉。

---

## 0. 背景：现状一句话

eplus prompt 的 cross-code "对齐"(FLUKA/G4 ≈ 1.035)是**靠 replay 实现的**——
把 Geant4 `.sim.gz` 里的 `IA INIT` 原初粒子逐条注入 FLUKA。它绕过了"源"这个环节，
所以数字好看，但 **H0(独立源归一化)从未被验证**，而独立源恰恰是 delayed/activation
必须的。真正要做的是：**让独立源(`sampled_source_authority` 模式)自己跑出同样的结果**。

---

## a. 多线程并行 + 终端不崩溃

### 症状与证据
- `run_eplus_equal_stat_chunks.py:92-97`：`--max-parallel` 默认 **1**，注释明说是为了
  "avoids repeated terminal/process popups"。
- `run_eplus_replay_replicas.py:103-104`：8 个 replica 又串行调度 → **嵌套串行**，
  8×16 = 128 个 FLUKA run 一次只跑一个。机器是 **24 核**(`nproc`)。
- 单 chunk 实测：FLUKA 仅 ~9s(geometry init 2.27s + 跟踪 15233 primary 6.69s)，
  墙上 ~25s(差额是 python 后处理 parquet/CSV + 调度器 `time.sleep(5)` 轮询)。
- **致命点**：rep02 的 `driver.log` 实测 `chunk_08` 03:29:05 → `chunk_09` 07:47:35，
  中间 **4h18m 零推进**(每 chunk 本该 25s)。整段 session 00:37→10:11 ≈ 9.5h，
  其中 ~45% 是这段 stall，~40% 是源对齐/中子的反复试错重跑，真实 FLUKA 计算只占 ~10%
  (且被串行又放大 ~10×)。

### 根因
"终端/进程弹窗"是 harness/UI 层每个**前台子进程**触发一次的问题。用 `--max-parallel 1`
回避，等于把并行整个关掉——付出了 chunking 的固定开销，却拿不到并行收益。

### 修复方向（按优先级）
1. **一个后台 driver，内部并行**：driver 用 `setsid`/`start_new_session=True` + 输出全部
   重定向到文件后台启动(`nohup ... &` 或 run_in_background)，让 harness 只看到 **1 个**
   长任务；并行池(`--max-parallel 20`，留几核给系统)放在 driver **内部**。
   这样既并行又不会按 chunk 数弹窗。
2. **每个 chunk 各自独立 `fluka_run/` 工作目录**(现在已经是)，所以并行对 FLUKA 安全；
   seed 已按 `seed + idx` 区分。只要把 `--max-parallel` 提上去即可。
3. **少切块**：不要把 243727 切 16 块再跑。要么**单进程跑完**(几何只 init 一次，省掉
   16× 的 init + 16× python 后处理 + 每 chunk 5s 轮询)，要么 chunk 数**匹配核数**
   (~20–24 块，每块 ~10k histories)一次并行铺满。当前是"切了块却串行"——最差组合。
4. **加 per-chunk 超时 watchdog**：给每个 chunk 设 wall-time 上限(例如 10×中位耗时)，
   超时就 kill+标记+继续，避免再出现 4 小时无人察觉的 stall。
5. **降低轮询开销**：`run_chunks` 里每 5s 对所有 `started_dirs` 做 glob+line_count
   (`run_eplus_equal_stat_chunks.py:188-192`)，chunk 多时会累积；并行铺满后可拉长间隔。

### 预期收益
128 个 chunk 串行 ≈ 43min；24 路并行 ≈ 2–3min。加上去掉 stall，整条 eplus 全量从
"~10h 量级"回到**分钟级**。

---

## b. 偏离主线的地方 + 修复

| # | 偏离 | 证据 | 修复 |
|---|---|---|---|
| B1 | **replay 代替独立源**(defeat H0) | comparison run 全是 `mode=megalib_sim_ia_init_replay`(`run_eplus_raw_mvp.py:818-830`)；audit `status=PASS_SIM_INIT_REPLAY` | 见 **§c**：修独立源 bug 后回到 `sampled_source_authority`，replay 只留作可选的 transport-only 旁证 |
| B2 | 串行 + 4h stall | 见 **§a** | 见 **§a** |
| B3 | 输出写进了 `Fluka_TES_511_Balloon` | `work_fluka_harness/` 下几十个 run dir、200MB+/replica；harness §0.2 明令"不要在此目录生成工程输出" | 正式产物落到 `/home/ubuntu/TES_511_Balloon/engineering/fluka_crosscode_validation_YYYYMMDD/`；此目录只留 handoff |
| B4 | source-mode 切换未记录 | `00_manifest/decision_log.md` 停在更早的 geometry BLOCK，没有 replay 这次转向 | 任何源/几何/阈值的实质改动都要进 `decision_log.md` |
| B5 | **`source_parity` 假阳性** | `build_source_authority.py:246-267` 的 1M-sample 审计只检"采样器复现自己那张 CDF"，**从不和 `.sim.gz` 真值比** → CDF 错 1000× 也 PASS | 见 **§c-3**：parity 必须含真值校验 |
| B6 | delayed/activation 整条空缺 | `07_/08_/09_/10_` deliverable 目录全空；`tes511_alignment_status` 自述 delayed replay 缺失 | 先把独立 prompt 源修对(§c)，再按 WP07→WP09→WP10 推进；activation 强依赖**正确的独立中子源** |

> 关键认识：B5+B1 是连锁的——正因为 parity gate 只自洽不验真，1000× 的能谱 bug 蒙混过关，
> 独立源跑出 50× 偏差，codex 找不到根因(查错了维度)，最后退而 replay 把源整个绕开。
> 修好 B5 的真值校验，这类 bug 在 gate 处就会被拦下。

---

## c. 不要 replay：用独立源复现 + 修 bug

### c-1. 主 bug：能谱整体 ×1000 过热（keV 被当 MeV）

**怎么定位的（逻辑 + 数据）**
- 逻辑锁定：replay 用**同一套几何/旋转/transport/scoring**就能 1.035 对齐，独立源换的
  **只有 primaries 生成**——所以 bug 必在"怎么生成 primary"，与几何/打分无关。
- 逐维对比 独立采样 vs G4 replay(真值)：

  | 维度 | 独立采样 | G4 replay(真值) | 判定 |
  |---|---|---|---|
  | 出生位置 \|pos\| | ~73 cm | ~73 cm | ✅ 一致 |
  | 方向 dz | ~0.05 | ~0.057 | ✅ 一致 |
  | **能量中位数** | **48,800 keV** | **49.9 keV** | ❌ **×978** |
  | 能量 max | 141 GeV | 615 MeV | ❌ ×1000 |

  → 圆盘/瞄准/旋转都对(codex 调了 2.3h 的 rotation/center/sign 本就没错)；**只有能量错 1000×**。

**确切位置**
- 谱文件 `expacs_fullsphere_20bin_sources/cosima_spectra_dp_2602units/eplus_bin00_theta18.19_pdf.dat`
  开头注释：`# 2602-compatible energy axis: archived keV values divided by 1000.`
- `build_source_authority.py:96-98`：把文件能量列直接当 **`energy_MeV`**。
- `build_source_authority.py:234`：`energy_keV = energy_MeV * 1000.0`。
- `run_eplus_raw_mvp.py:282`(`load_energy_cdfs` 读 `energy_keV` 列)→ `:385`(`sample_energy_keV`)
  → `:401-402`(`primary_energy_keV = 文件值×1000`，`primary_energy_GeV = energy_keV/1e6`)。
- **铁证**：文件能量列中位数 ≈ 48.8，Cosima 实际生成的 primary 中位数 = 49.9 keV →
  **Cosima 把文件列当 keV 用**，再 ×1000 就成了 48.8 **MeV**，正好 1000× 过热。

**为什么 1000× 过热 → 正好那个诊断特征**
- 真值 ~50 keV 的 eplus：一进外壳/窗口就停、湮灭，511 光子干净进 TES，**不碰 CsI**
  (= G4 那 242 个 active-veto 存活事件)。
- 被放大成 ~50 MeV 的 eplus：贯穿性粒子，**打穿 CsI 进 TES，沿途也在 CsI 丢能** →
  raw TES hit **多 6.24×**(2209 vs 354)、**~99% 带 CsI 符合**(veto 后只剩 16)、
  干净事件几乎没了(veto 后比 G4 **少 15×**，242 vs 16)。诊断里"几乎每个 TES hit 都伴随
  大额 CsI 沉积、所有 CsI 段均匀爆量"与此**完全吻合**。

**修复**
- 让独立源能量 = Cosima 实际用的值：即 `primary_energy_keV` 应等于谱文件能量列**原值**
  (当 keV)，**去掉 ×1000**。
  - 在 `build_source_authority.py`：CDF 的 `energy_keV` 应 = 文件原值(不是 `×1000`)；
    `energy_MeV` 命名具有误导性，应改为 `energy_keV` 为主、`energy_MeV = 原值/1000`。
  - 或在 runner 侧采样后不再 ×1000。任选其一，保证 `primary_energy_keV ≈ 文件原值`。
- 改完独立源能谱中位数会落回 ~50 keV，与 replay 一致。

> ⚠️ **更深的隐患，必须单独核**：那行注释字面意思是"文件 = archived_keV ÷ 1000"(即文件本意是
> **MeV**)，而 Cosima 是按 **keV** 读的。也就是说**整个 TES_511_BALLOON 的源可能本身就偏冷
> 1000×**——若属实，动摇的不只是 FLUKA 侧，而是 Step02/Step05 全部结果。
> 就 cross-code 而言，FLUKA 独立源**必须先对齐到项目实际用的那套 Cosima primaries(~50 keV)**，
> 这一点确定；但请**另开一项**去核实 Cosima 对 `.dat` 能量列的单位约定到底是 keV 还是 MeV。

### c-2. 次 bug：×8 归一化默认值

- `50× = 8.0×(归一化) × 6.24×(能量穿透)`。
- `8.0× = 1,949,816 / 243,727`(= 8 个 replica 的总生成数 / 单 replica)。
- 根因：`run_eplus_raw_mvp.py` 里 `history_weight = rate_s / norm_histories`，独立路线默认
  `norm_histories = histories = 243727`，而 G4 的 `rate_hz` 是按全量 1,949,816 定义的。
- replay 路线用 `run_eplus_replay_replicas.py:16` 的 `NORMALIZATION_HISTORIES = 1949816`
  + `--normalization-histories` 绕过了，但**独立路线没修**。
- 修复：独立源跑全量比较时，`--normalization-histories` 必须用**全部 replica 的总生成数**，
  不要用单次 histories。

### c-3. 必加的 gate：对 `.sim.gz` 真值校验（堵住 B5）

`source_parity` 不能只自洽。新增一步：从独立采样器抽 N 个 primary，与对应 species 的
`.sim.gz` IA INIT 真实分布做对比：
- 能量：KS / 分位(median、p10、p90)比值落在 [0.9, 1.1]；
- 方向(`dz`、`mu`)与出生位置(`|pos|`、xyz 分布)同样比对；
- 任一维偏离 >10% → `BLOCKED_SOURCE_SEMANTICS`，不许进 transport。

有这道 gate，c-1 的 1000× 能在源构建阶段就被拦下，而不是跑到 50× 才发现。

### c-4. 复现重跑的预期终态

修完 c-1 + c-2 + c-3 后：
1. 用 `sampled_source_authority` 模式(**不带** `--primary-source-sim-gz`)重跑 eplus 全量；
2. 独立源能谱中位数 ~50 keV、raw TES 率应落回 G4 同量级；
3. same-observable 比较(W2 / 480–550 / 50–8000，raw 与 active-veto)应自然对齐到 ~1.0，
   **无需** replay；
4. 之后才按 WP07(neutron activation)→ WP09(native day-15 delayed)→ WP10(sampled delayed)
   推进 prompt/delayed/bkg 完整构成对比。replay 仅作为"相同入射粒子下 transport 一致"的
   旁证保留，不作为主线。

---

## 附录：自洽用的关键数字

- 机器：24 核(`nproc`)。
- 单 chunk FLUKA：init 2.27s(geom 0.91s) + 跟踪 15233 primary 6.69s ≈ 9s；墙上 ~25s。
- 单 replica(16 chunk 串行)≈ 6–7min；全量 8 replica 串行 + stall ≈ 数小时。
- stall：rep02 `driver.log` `chunk_08` 03:29:05 → `chunk_09` 07:47:35 = **4h18m**。
- 失配分解：`50× = 8.0×(norm) × 6.24×(energy)`。
- 能量：独立中位 48,800 keV vs G4 真值 49.9 keV(×978)；max 141 GeV vs 615 MeV。
- raw counts：FLUKA 2209 vs G4 354(×6.24)；active-veto(CsI<50keV)：FLUKA 16 vs G4 242。
- 谱文件注释：`# 2602-compatible energy axis: archived keV values divided by 1000.`

## 附录：涉及的代码位置

- `build_source_authority.py:96-98`(energy_MeV 误标)、`:234`(×1000)、`:246-267`(自洽-only 审计)。
- `run_eplus_raw_mvp.py:278-298`(load/ sample energy)、`:385`、`:401-402`(能量写出)、
  `:324-353`(方向+圆盘采样，**正确**)、`:818-830`(replay 分支)。
- `run_eplus_equal_stat_chunks.py:92-97`(--max-parallel 默认 1)、`:188-192`(轮询 glob)。
- `run_eplus_replay_replicas.py:16`(NORMALIZATION_HISTORIES)、`:103-104`(--max-parallel 1)。
