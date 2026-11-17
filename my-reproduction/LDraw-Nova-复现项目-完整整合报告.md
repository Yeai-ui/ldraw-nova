# LDraw-Nova 复现项目 · 完整整合报告

> 用途：项目已无法整体拷贝，本报告将全部 5 份文档（进度报告 v2 / 复现手册 v1 / 路线B实现手册 v2 / 路线B搭建记录 v3 / 快速命令卡 v1）整合为一份可独立复习的材料，重点服务于**简历实习经历部分 + 面试问答准备**。
> 整合日期：2026-11-13　|　原始复现日期：2026-10-21

---

## 一、电梯陈述（30 秒版，面试开场用）

> 我独立复现了开源项目 LDraw-Nova（GitHub: anteloc/ldraw-nova）的核心方法论——"AI 写生成程序 → 程序输出 CAD 源码 → 渲染自检 → 迭代修正"。在无 Docker、无前沿模型 API、全程本地零 token 成本的 Windows 环境下，我部署了 LDraw 官方零件库（24,858 个零件）、LeoCAD 渲染器和纯 Python 工具链，定位并修复了 3 处 Windows 平台兼容性问题，跑通 plan→build→validate→render→cad-check 五步机器校验流程，最终由 LLM 编写生成器产出一栋 360 块零件、五步全绿的合规 LEGO 街景模型，并沉淀了 5 份复现文档。这段经历让我真正理解了 3D 资产的数据格式、几何校验标准和"渲染→审查→修改"的质检闭环——这正好能迁移到 3D 模具数据标注的质量把控上。

---

## 二、项目背景：LDraw-Nova 是什么，复现的是什么

### 2.1 原项目

LDraw-Nova 是一个"AI 自主搭建 LEGO 模型"的开源项目，核心 Claim 是 **"3D 建模 = 写代码"**：不让 LLM（或人）直接写 3D 坐标，而是让 AI 写一个**生成器程序**，由程序算出所有坐标输出 `plan.json`（施工下单表），工具链负责摞模型、机器校验、渲染出图，最后"渲染→看→改"迭代。作者 showcase 是一座 **2175 块**的樱花庭院。

### 2.2 复现的两层含义（成本差一个数量级）

| 层次 | 做什么 | 门槛 |
|---|---|---|
| A. 部署复现 | 用 Docker 把作者的 Web 应用跑起来，调前沿模型 API 生成模型 | 高（单次大模型几十美元 token） |
| B. 方法复现 | 复现"AI 写生成器 → 输出 CAD 源码 → 渲染自检 → 迭代"这条链路 | 低（code agent + 零件库 + 渲染器） |

**我的选择：先走 B 验证方法。** 读源码后还发现关键事实——Web 应用只是 CLI 的一层皮，`ldraw_tools` 本体是约 20 个模块的**纯 Python CLI**，全部依赖只有 3 个包。所以 Docker 根本不是必需品，路线 B 在 Windows 本机即可完整落地。

### 2.3 复现结果分层判定（诚实边界，面试必背）

| # | 复现目标 | 状态 | 判定依据 |
|---|---|---|---|
| 1 | 取得项目本体 v0.6.0 完整包 | ✅ | 184 MB，含 `ldraw_tools/` 与 `.venv/` |
| 2 | 装好零件库与外部工具 | ✅ | LDraw 库 + LeoCAD 26.09 + poppler，`doctor` 全绿 |
| 3 | 跑通工具链五步 | ✅ | `plan → build → validate → render → cad-check` 全 `checks_passed: true` |
| 4 | 用"写代码"方式造出合规模型 | ✅ | 街角面馆 **360 块**，24×24 底座、首层可拆 |
| 5 | "渲染→看→改"迭代闭环 | ✅ | 雨篷问题 → 只改门头模块 → 重跑全绿（2 轮） |
| 6 | agent 自主跑完整流程 | ⚠️ 部分 | LLM 按规范写生成器，但"看渲染图找问题"由人工代劳 |
| 7 | 2175 块樱花庭院 | ❌ 未做 | 需前沿模型长链路 + 几十美元 token，RTX 5050 本地模型撑不住 |

**一句话：复现了"工具链 + 方法"，尚未复现"AI 自主建模 2175 块"。** 面试时要主动说清这个边界，这比夸大更加分。

---

## 三、环境搭建（全在本机实测）

```
系统        Windows（PowerShell），未用 Docker
工作目录    nova-full\ldraw-nova-0.6.0\
Python      3.13.14（项目内 .venv 隔离环境）
依赖        pyldraw3 1.7.0 / numpy 2.5.2 / jsonschema 4.26.0（仅 3 个）
LDraw 库    C:\Users\admin\ldraw\ldraw（24,858 parts + 1,791 p + LDConfig.ldr）
Poppler     pdftotext.exe（读 171 页 LDraw 官方规范 PDF）
LeoCAD      26.09（渲染 + BOM 交叉验证，agent 的"眼睛"）
API 消耗    0 token / 0 元（全程本地）
```

三样外部依赖的角色：
- **LDraw 零件库**：零件的几何与元数据来源（`part 3001` 可查尺寸/连接器/包围盒/BFC）
- **Poppler pdftotext**：让工具能读官方 PDF 规范（`spec --page 65`）
- **LeoCAD**：`render` 出 5 视角 PNG，`cad-check` 导出 BOM 与 plan 交叉复核

LeoCAD 实际调用形式（源码 `external.py`）：
```
leocad -l <零件库> -i <输出.png> -w 1000 -h 800 <模型.mpd>   # 渲染
leocad -l <零件库> -csv <bom.csv> <模型.mpd>                 # BOM 导出
```

---

## 四、我的关键技术贡献：Windows 三补丁

官方代码在 Windows 上**跑不起来**，我定位并修复了三处：

1. **启动脚本不可用**：`ldraw-agent` 是 sh 脚本、硬编码 `.venv/bin/python`；Windows venv 是 `Scripts\`。所有命令改用 `.venv\Scripts\python.exe -m ldraw_tools.cli <子命令>`。
2. **setup.sh 不可用**：它走 `uv sync` / `python3 -m venv`，手工完成等价步骤（venv → pip 装 3 依赖 → doctor）。
3. **符号链接视图静默失效（最关键）**：`ldraw_tools/common.py` 用 symlink 在 `.cache\` 下建零件库链接视图。Windows 无开发者模式时，目录链接**创建不报错但退化成空目录**（实测 `.cache\...\parts\` 文件数 = 0）——症状是 `index` 成功但 `part`/`build` 报 `PartNotFoundError`，极具迷惑性。修复：Windows 分支跳过符号链接、`target = root`，把 `parts.lst` 生成在真实库目录；同时把链接创建改成幂等（原代码第二次运行必触发 WinError 183）。

**面试话术**：这是典型的"静默失败"排查案例——工具不报错、只是悄悄给你一个空库，最后靠逐目录核对文件数才定位到根因。

### 附加修复：用户 PATH 被写坏事故与教训

在 Git Bash 里执行 `setx PATH "%PATH%;..."` 出了两个问题：bash 不展开 `%PATH%`（写进注册表的是字面量），且 `setx` 是**整体覆盖**不是追加，把原有条目冲掉了。用 Python `winreg` 写 `REG_EXPAND_SZ` 重建 7 条并广播 `WM_SETTINGCHANGE` 才修好。

教训（面试可讲）：
- Git Bash 里不要用 `%VAR%`（cmd 语法）；
- `setx` 改 PATH 前先读出、去重、拼接、再写回；
- GUI 子系统程序（Qt 应用如 LeoCAD）控制台直接回车 stdout 不可见，验证要 `2>&1 | Out-String`。

---

## 五、核心方法论：五步工具链

```
生成 plan.json → build → validate → render → cad-check
（算数）         （摞起来） （合规检查） （出图）  （LeoCAD 侧复核）
```

设计哲学：**少写坐标 = 少出错；错了可机器检查，不靠肉眼。** LLM 不直接写 3D 坐标，而是写生成器程序；`plan.json` 那 285 行 JSON 就是"模型源码"——可 diff、可版本管理、可 code review，这是传统 CAD 拖拽做不到的。

主流程命令（实测通过）：
```powershell
& $P output/generate_noodleshop.py --output output/noodleshop.plan.json   # ① 生成 plan
& $P output/check_geom.py output/noodleshop.plan.json                     # ② 自建几何预检
& $P -m ldraw_tools.cli build output/noodleshop.plan.json --output output/noodleshop.mpd --report output/noodleshop.build.json --force
& $P -m ldraw_tools.cli validate output/noodleshop.mpd                    # ④ 独立复核
& $P -m ldraw_tools.cli render output/noodleshop.mpd --outdir output/noodleshop-render --views home top back right front
& $P -m ldraw_tools.cli cad-check output/noodleshop.mpd                   # ⑥ 交叉验证
```

易错参数：`build` 的报告参数是 `--report <文件> --detail full|summary`，**没有 `--json`**。

碰撞检测方法（build 报告原文）：`AABB broad phase, oriented bounds separation, curated rectangular body SAT`——粗筛用 AABB，精判用分离轴定理。

---

## 六、主产物：360 块街角面馆（noodleshop）

### 6.1 最终实测结果

```
build       checks_passed: true   occurrence_count: 360
validate    checks_passed: true
render      home/top/back/right/front.png + leocad-bom.csv（5 视角）
cad-check   checks_passed: true   tool: LeoCAD   snapshot/bom 全部创建
BOM(LeoCAD) 360 —— 与 plan 完全一致
```

### 6.2 模型规格

- **5 个 section / 285 条放置指令 / 展开 360 个物理零件**，29 种零件-颜色组合、7 种颜色
- 底座 24×24 桩（12 块 6×8 板）；首层顶 -200 LDU；公寓顶 -408 LDU（= 17 层砖高，砖高 24 LDU）
- **首层可拆**（独立 section），配色：深蓝灰 72 / 沙绿 378 / 暖橙招牌 / 透明黄灯笼等
- 模块：`noodle-main`（底座+街面+雨篷+招牌+灯笼+护栏+路灯+机器人）、`noodle-ground`（可拆首层）、`noodle-upper`（公寓）、`noodle-door`、`noodle-window`

### 6.3 零件构成要点（BOM 实测）

| 零件 | 数量 | 占比 | 用途 |
|---|---|---|---|
| 3005 Brick 1×1 | 94 | 26.1% | 立管/门廊柱/细节 |
| 3020 Plate 2×4 | 72 | 20.0% | 街面/屋顶/楼板 |
| 3009 Brick 1×6 | 66 | 18.3% | 墙体砌筑 |

超过 1/4 是 1×1 砖——"管道/栏杆/立柱"类细节的代价，也是零件数从 320 涨到 360 的直接原因（雨篷柱 2→8 根，单项 +24 块）。

### 6.4 自建检查工具（超出原项目流程的自研部分）

| 脚本 | 作用 | 结果 |
|---|---|---|
| `check_geom.py` | 展开所有矩形件，两两 AABB 体块比对报穿透 | 346 件 → overlaps: 0 |
| `check_support.py` | 找底面无支撑的件（顶面贴合判定） | 25/346，其中 12 底座误报 + 2 有意悬挂 + 若干窗楣误报 + **1 个真问题（屋顶板中间无支撑）** |

### 6.5 这个模型证明了什么 / 证明不了什么（面试高频追问）

**证明了**：无前沿模型、无 API、无 Docker 的环境也能产出五步全绿的合规模型，"写代码建模"方法可迁移；360 块模型是未来真 agent 跑同一提示词的**基准线**（零件数/几何违规数/迭代轮数都可逐项对照）。

**证明不了（务必主动声明）**：
1. `physical_validity` 恒为 `"not_proven"`——工具只保证格式正确 + 几何 0 穿透 + 主要构件有支撑，没证明真能用实体积木拼（屋顶板中间无支撑、灯笼悬挂是已知遗留）。
2. 不等于 2175 块量级——差的不是时间，是**长链路规划能力**，需前沿模型撑几十轮工具调用。
3. 不是纯自主产物——"看渲染图找问题"一环由人代劳（当时模型不支持读图）。

---

## 七、迭代闭环实录（"渲染→看→改"，2 轮收敛）

| 轮次 | 反馈 | 改动 | 结果 |
|---|---|---|---|
| 1 | 雨篷悬空、没门高、横插门洞中部 | 门头模块：雨篷从 Y=-112 升至门头顶面 -160、招牌移到雨篷上、灯笼移位 | 336 块全绿 |
| 2 | 自查发现雨篷外排悬空 | 门头模块：柱子 4→8 根两排，两排板各有支撑 | **360 块全绿** |

关键点：**只改门头一个模块，其余 4 个 section 不动**——模块化设计让迭代的影响面可控。

---

## 八、踩坑记录（10 条真实踩坑，面试技术问答素材）

### 建模层面

1. **`plate_field()` 中心公式错**：`(c + pw/2)*STUD` 应为 `(c*pw + pw/2)*STUD` → 一错就是 200+ 块互相穿模。
2. **砖高 24 ≠ 板高 8**：给砖用了板的 Y（-8），立管直接沉进底座 16 LDU。
3. **网格约束**：2×2 件中心必须是 20 的倍数、1×1 是 10 的奇倍数——灶台按直觉摆会压到柜台。
4. **别信零件名**：`3004` "Brick 1 x 2" 实为 x=2、z=1；`3009` "Brick 1 x 6" 实为 x=6、z=1。尺寸一律查 `rectangular-parts.json`。
5. **Y 是顶面不是底面**：`at:[x,Y,z]` 的 Y 是零件顶面，实体占 `[Y, Y+h]`，往上堆 = Y 变小；首层砖是 `-24` 不是 `-8`。
6. **包络必须精确拼合**：检查器不允许砖体重叠（它不知道砖缝交错），环形墙前后走满、左右让角；写了 `tile(lo, hi, pattern)` 函数铺不满即抛错，当场抓到手算错误。
7. **子模型引用要显性颜色**：模块内用 16（current colour）的，引用行必须给具体颜色，否则 `colour.unresolved_current`。
8. **LeoCAD 视角陷阱**：`front` 相机看 -Z 面，本模型门在 +Z → 看正面要用 `--views back`。

### 工程/环境层面

9. **Windows symlink 静默失效**（见第四节补丁 3）。
10. **setx 覆盖 PATH / GUI 程序 stdout 不可见**（见第四节）。

排错速查表：
| 现象 | 处理 |
|---|---|
| `doctor` 里 leocad/pdftotext 为 null | PATH 未生效，重开终端或手动补 |
| `PartNotFoundError ... parts.lst` | symlink 失效，打补丁 3 |
| `unknown argument --json` | 改用 `--report` |
| `colour.unresolved_current` | 子模型引用行给显性颜色 |
| `body_overlap` 大量报错 | 先跑自建 `check_geom.py` 定位 |

---

## 九、简历写法（已定稿）

### 写进实习经历（粤港澳大湾区国家技术创新中心 · AI 数据标注岗，作为第 3 条）

> 3、自主学习并完整复现开源项目 LDraw-Nova（AI 驱动的 3D 建模工具链）：在 Windows 环境本地部署 LDraw 零件库、LeoCAD 渲染器与 Python 工具链，独立定位并修复符号链接失效等 3 处平台兼容性问题；跑通 plan→build→validate→render→cad-check 五步校验流程，由 LLM 编写生成器代码产出 360 块零件的合规 CAD 模型，建立"渲染→审查→定向修改→重跑校验"的迭代闭环（2 轮收敛），深化对 3D 资产数据格式与质量校验标准的理解，反哺 3D 模具数据标注工作。

### 备选：独立项目经历条目

> **LDraw-Nova 开源项目复现（AI 驱动 3D 建模工具链）　独立复现**
> 项目职责：在 Windows/PowerShell 环境从零复现开源项目的"AI 写生成程序→输出 CAD 源码→渲染自检→迭代修正"链路，全程本地运行零 API 消耗；部署 LDraw 官方零件库（24,858 零件）、LeoCAD 26.09、Poppler 工具链并通过 doctor 全绿自检；修复 symlink 静默失效、sh 脚本不兼容等 3 处 Windows 平台问题；产出 360 块零件、五步校验全通过的合规模型，沉淀 5 份复现文档。
> 项目成果：验证了"代码生成 + 渲染自检"的 AI 建模方法可行性，掌握 LDraw/.mpd 数据格式、AABB/SAT 几何碰撞校验与迭代质检流程，可迁移至 3D 数据标注与质检场景。

**写作纪律**：不写"复现了 AI 自主建模"（那层没做成）；数字只用实测值（360 块 / 五步全绿 / 3 处补丁 / 2 轮迭代 / 24,858 零件 / 0 token）；时间写 2026-10。

---

## 十、面试问答预案

**Q1：这个项目你具体做了什么？**
按"背景 → 路线选择 → 环境搭建 → 三个补丁 → 五步流程 → 360 块产物 → 2 轮迭代"的顺序讲，控制在 2 分钟内，边界（第 2.3 节）主动带上。

**Q2：为什么不用 Docker？**
读完源码发现 Web 应用只是 CLI 的一层皮，本体是 20 个模块的纯 Python CLI，依赖只有 3 个包；Docker 镜像做的事就是装 LDraw 库 + Poppler + LeoCAD 再套 Web 界面。我在 Windows 上直接做同样的事，还顺手修了官方代码的三处 Windows 兼容问题——这比照着 README 跑一遍含金量高。

**Q3：遇到的最难的 bug？**
推荐讲 symlink 静默失效：`index` 成功但 `build` 报零件不存在，零件明明在 parts.lst 里。最后发现 Windows 无开发者模式时目录链接创建不报错、退化成空目录——工具在悄悄给你空库。逐目录核对文件数才定位。亮点是"静默失败"的排查思路 + 幂等化修复。

**Q4：模型 360 块和作者 2175 块差在哪？**
不是"多堆一会儿"的差距，是长链路规划能力：2175 块需前沿模型撑住几十轮工具调用，单次 token 成本几十美元；我的环境（RTX 5050 本地模型 + 被限流的 API）撑不住。360 块的意义是基准线——将来真 agent 跑同一提示词，零件数/几何违规/迭代轮数可逐项对照。

**Q5：这和你实习的 3D 数据标注有什么关系？**
三点：① 理解了 3D 资产的结构化表示（plan.json 可 diff、可版本管理，对应标注数据的 schema 思维）；② 掌握了机器质检闭环（几何穿透/支撑校验 + 渲染人工审查），对应标注质检的"机检 + 人审"；③ 修复静默失败的排查能力，对应标注 pipeline 的疑难 case 定位。

**Q6：如果重做一次会怎么改进？**
① 先跑通 `run.ps1` 固化（环境变量兜底 + doctor 预检 + 五步串行失败即停）；② 等限流过去让 agent 真正自主跑完整流程，与 360 块基准对照；③ 用支持读图的多模态模型替代人工评审渲染图，补上闭环最后一环。

---

## 十一、环境重建速查（万一要再跑）

```powershell
# 从 nova2.tgz 解压后
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install pyldraw3==1.7.0 numpy==2.5.2 jsonschema==4.26.0
# 然后必须重打第四节三个 Windows 补丁，否则必挂
```

每次开工初始化：
```powershell
cd nova-full\ldraw-nova-0.6.0
$env:LDRAW_DIR = [Environment]::GetEnvironmentVariable('LDRAW_DIR','User')
$env:PATH = [Environment]::GetEnvironmentVariable('Path','User') + ";" + $env:PATH
& .\.venv\Scripts\python.exe -m ldraw_tools.cli doctor
```
`library_present: true` 且 leocad/pdftotext 有路径 = 环境就绪。

保留资产：`nova2.tgz`（源码原包）、`ldraw-complete.zip`（零件库）、`poppler.zip`、`leocad-setup.exe`、`C:\Users\admin\ldraw\ldraw`（已装的零件库）。
