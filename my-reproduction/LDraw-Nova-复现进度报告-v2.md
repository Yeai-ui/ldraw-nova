# LDraw Nova 复现进度报告 v2

- **日期**：2026-10-21
- **机器**：Windows 本机（PowerShell），**未使用 Docker**
- **API 消耗**：0 token / 0 元（全程本地）
- **工作目录**：`C:\Users\admin\Desktop\fxian\nova-full\ldraw-nova-0.6.0`
- **唯一产物**：街角面馆 `noodleshop`，**360 块**，五步全绿

---

## 一、结论摘要（分层，别混为一谈）

| # | 复现目标 | 状态 | 判定依据 |
|---|---|---|---|
| 1 | 取得项目本体 v0.6.0 完整包 | ✅ 完成 | `nova-full\ldraw-nova-0.6.0\`，184 MB，含 `ldraw_tools/` 与 `.venv/` |
| 2 | 装好零件库与外部工具 | ✅ 完成 | LDraw 库 + LeoCAD 26.09 + poppler，`doctor` 全绿 |
| 3 | 跑通工具链五步 | ✅ 完成 | `plan → build → validate → render → cad-check` 全 `checks_passed: true` |
| 4 | 用"写代码"方式造出合规模型 | ✅ 完成 | 街角面馆 **360 块**，24×24 底座、深蓝灰+沙绿、首层可拆 |
| 5 | "渲染→看→改"迭代闭环 | ✅ 完成 | 用户指出雨篷问题 → 只改门头模块 → 重跑全绿（2 轮） |
| 6 | **agent 自主跑完整流程** | ⚠️ 部分 | 由 LLM 按 `instructions.md` 写生成器，但靠**人工反馈**驱动，非 agent 自主长跑 |
| 7 | **2175 块樱花庭院** | ❌ 未做 | 作者 showcase 级，需前沿模型长链路 |

**一句话：复现了"工具链 + 方法"，尚未复现"AI 自主建模 2175 块"。**

---

## 二、Windows 环境实况

```
系统        Windows（PowerShell）
工作目录    C:\Users\admin\Desktop\fxian\nova-full\ldraw-nova-0.6.0
Python      3.13.14（项目内 .\.venv）
依赖        pyldraw3 1.7.0 / numpy 2.5.2 / jsonschema 4.26.0
LDraw 库    C:\Users\admin\ldraw\ldraw      （用户变量 LDRAW_DIR）
LeoCAD      26.09  → C:\Program Files\LeoCAD\leocad.EXE
pdftotext   C:\Users\admin\nova-bin\poppler-26.09.0\Library\bin
Docker      未安装、未使用
```

> `LDRAW_DIR` 持久化值是双斜杠 `C://Users//admin//ldraw//ldraw`，实测工具会自动归一化，**不要去改**。

### Windows 三补丁（已在当前副本内；重新解压会丢）

1. **不用 `./ldraw-agent`**（sh 脚本、硬编码 `.venv/bin/python`）
   → 一律 `.venv\Scripts\python.exe -m ldraw_tools.cli <子命令>`
2. **不跑 `setup.sh`**（走 `uv sync`）→ 直接 `pip install` 那三个依赖
3. **`ldraw_tools/common.py` 的 symlink 视图在 Windows 静默失效**
   症状：`index` 成功但 `part`/`build` 报 `PartNotFoundError`
   修复：Windows 分支跳过符号链接、`target = root`，`parts.lst` 生成在真实库目录（或开「开发者模式」）

---

## 三、目录取舍与清理记录

### 保留

| 路径 | 用途 |
|---|---|
| `nova-full\ldraw-nova-0.6.0\` | ✅ **唯一可运行副本** |
| `nova2.tgz`（175.5 MB） | 完整源码原包，环境炸了用它重来 |
| `ldraw-complete.zip`（139.3 MB） | 重装零件库 |
| `poppler.zip`（41.7 MB） | 重装 pdftotext |
| `leocad-setup.exe`（173.8 MB） | 重装 LeoCAD |
| `LDraw-Nova-*.md`（4 份） | 手册/命令卡/搭建记录/实现手册 |
| `jsd.json` `tree.json` `part_query.py` `verify_parts.py` `path-backup-20261021.txt` | 均为**非空**小文件，保留 |

### 本次已删除（约 113 MB）

| 目标 | 原因 |
|---|---|
| `nova.tgz`（112.8 MB） | 截断包，解压不完整 |
| `output\__pycache__\` | Python 缓存 |
| `output\bridge-render\.render-*/`（2 个） | 渲染中间临时目录 |

### ⚠️ 未删除（被环境安全闸拦截，需人工确认）

| 目标 | 体积 | 阻塞原因 |
|---|---|---|
| `ldraw-nova-0.6.0\` | **507.6 MB / 7446 文件** | 无 `ldraw_tools/`、无 `.venv/`，**跑不了**；但单目录文件数 > 500，触发 `SAFE_DELETE_BULK_CONFIRM_REQUIRED` |
| `ldraw-nova\` | 裸 `.git`（29 条目，工作区 0 文件） | 回收站操作被拒（`genie-trash rejected the path`） |
| `ldraw-nova-src\` | 裸 `.git`（28 条目，工作区 0 文件） | 同上 |

### `ldraw-nova-0.6.0\` 无用的取证（逐文件比对，非目测）

用相对路径 + 文件大小双重比对 `ldraw-nova-0.6.0\` 与 `nova-full\ldraw-nova-0.6.0\`：

```
旧目录文件数            7446
新目录文件数           12442
旧目录独有的文件            0   ← 每一个文件在新目录同路径下都存在
同名但大小不同的文件        0   ← 连内容长度都完全一致
```

即：**旧目录是新目录的严格子集**，删掉不会丢失任何内容。

它缺失的关键项（直接决定"跑不了"）：

```
ldraw_tools/      False   ← 程序本体，最致命
.venv/            False
instructions.md   False
pyproject.toml    False
setup.sh          False
ldraw-agent       False   ← 工作流入口
```

507.6 MB 的构成：`data\models-annotated` 387.9 MB（作者标注模型集）+ `examples` 79.5 MB + `categories` 7.1 MB + `docs` 5.5 MB，**全部在新目录里有副本**。零件库另有 `C:\Users\admin\ldraw\ldraw` 与 `ldraw-complete.zip` 兜底。

**判定：可安全删除，释放 507.6 MB。**

手动删除（确认后自行执行，不可恢复）：

```powershell
cd C:\Users\admin\Desktop\fxian
Remove-Item 'ldraw-nova-0.6.0','ldraw-nova','ldraw-nova-src' -Recurse -Force
```

---

## 四、每次开工的初始化（必跑）

```powershell
cd C:\Users\admin\Desktop\fxian\nova-full\ldraw-nova-0.6.0
$env:LDRAW_DIR = [Environment]::GetEnvironmentVariable('LDRAW_DIR','User')
$env:PATH      = [Environment]::GetEnvironmentVariable('Path','User') + ";" + $env:PATH
$P = ".\.venv\Scripts\python.exe"
& $P -m ldraw_tools.cli doctor
```

体检应见 `library_present: true`，且 `tools.pdftotext` / `tools.leocad` 有路径。
**出现 `null` = PATH 未生效**（旧会话 / IDE 内置终端最常见）。

> LeoCAD 是 Qt GUI 程序，控制台直接回车**输出不可见**，验证写：`leocad --version 2>&1 | Out-String`

---

## 五、Agent 提示词（原文）与 429 事件

```text
Read instructions.md first.
Build a compact noodle-shop street corner, 300-500 parts, 24x24 stud base,
dark bluish gray + sand green palette, removable ground floor.
Follow the workflow in instructions.md end to end.
IMPORTANT: this is Windows — always use
`.venv\Scripts\python.exe -m ldraw_tools.cli <command>`
instead of `./ldraw-agent <command>`.
```

**实测结果**：请求被网关拒绝，未送达 agent。

```
API Error: Request rejected (429)
model deepseek-ai/DeepSeek-V4-Pro
```

属于**模型供应商限流，与 LDraw Nova 无关**。故改走「本地代写生成器」方案：**全程不走 API、不受 429 影响**。

> 最后那句 Windows 修正**必须带**，否则 agent 会去执行 sh 脚本然后失败。

---

## 六、主流程命令（已实测）

```powershell
# ① 生成 plan（全部坐标由代码算）
& $P output/generate_noodleshop.py --output output/noodleshop.plan.json

# ② 自建几何预检（建议）
& $P output/check_geom.py    output/noodleshop.plan.json
& $P output/check_support.py output/noodleshop.plan.json

# ③ build
& $P -m ldraw_tools.cli build output/noodleshop.plan.json `
     --output output/noodleshop.mpd --report output/noodleshop.build.json `
     --force --detail summary

# ④ validate
& $P -m ldraw_tools.cli validate output/noodleshop.mpd

# ⑤ render
& $P -m ldraw_tools.cli render output/noodleshop.mpd `
     --outdir output/noodleshop-render --views home top back right front

# ⑥ cad-check（LeoCAD 侧复核）
& $P -m ldraw_tools.cli cad-check output/noodleshop.mpd
```

**参数要点**

- `build` 的报告参数是 `--report <文件> --detail full|summary`，**没有 `--json`**
- `render --views` 支持 `back top front left right home`
- ⚠️ **LeoCAD 的 `front` 相机看 -Z 面；本模型门在 +Z → 看正面请用 `back.png`**

---

## 七、已跑通的产物清单

| 模型 | 零件数 | build | validate | render | cad-check |
|---|---|---|---|---|---|
| `examples/bridge.plan.json`（官方示例） | — | ✅ true / written true | ✅ true | ✅ 出图+BOM | ✅ true |
| `kiosk_v2`（自创验证模型，粉/米白小亭子） | 70 | ✅ true | ✅ true | ✅ 出图+BOM | ✅ true |
| **`noodleshop`（主产物）** | **360** | ✅ true | ✅ true | ✅ 5 视角+BOM | ✅ true |

`noodleshop` 最终一轮实测：

```
build       checks_passed: true   written: true   occurrence_count: 360
validate    checks_passed: true
render      home/top/back/right/front.png + leocad-bom.csv
cad-check   checks_passed: true   tool: LeoCAD   snapshot_created/bom_created: true
BOM(LeoCAD) 360
```

---

## 八、街角面馆模型规格

**5 个 section / 285 条放置指令 / 展开 360 个物理零件**

| 模块 | 内容 |
|---|---|
| `noodle-main` | 24×24 桩底座（12×3036 板）+ 街面（18×3020 板）+ 雨篷 + 招牌 + 灯笼 + 立管 + 护栏 + 路灯 + 货箱 + 机器人 |
| `noodle-ground` | **可拆首层**：12×12 桩、8 层沙绿墙、4 扇 1×2×2 窗、4 桩玻璃门、柜台、灶台、2 桌、4 凳、地砖、屋顶板 |
| `noodle-upper` | 窄公寓：12×6 桩、8 层深蓝灰墙、2 扇窗、屋顶花箱 + 通风管 |
| `noodle-door` | 60596 门框 + 60623 门板（6 层高） |
| `noodle-window` | 60592 窗框 + 60601 玻璃（2 层高） |

- **尺寸**：底座 24×24 桩；首层顶 `-200` LDU；公寓顶 `-408` LDU；**自底座顶面起总高 408 LDU ≈ 17 层砖高**（折合 20.4 桩高）
  > 更正 v1 笔误：此前误写为「416 LDU ≈ 20.8 砖高」，混淆了"桩高"与"砖高"。砖高为 24 LDU，408 ÷ 24 = 17 层砖。
- **配色**：深蓝灰 72 / 浅蓝灰 71 / 沙绿 378 / 暖橙 225（招牌）/ 透明黄 46（灯笼）/ 透明 47（玻璃）/ 深棕 308（门）
- **门头**：雨篷 4 板（坐门头顶面 `Y=-160`，外伸 2 桩）+ 8 根柱两排（每根 6 砖）+ 招牌箱 2 砖坐于雨篷上 + 2 盏灯笼挂于门洞两侧

---

## 八·五、这个模型做了什么 / 有什么用

### 它做了一件什么事

一句话：**它是"用代码描述、由工具组装、经机器校验通过"的一栋可拆层 LEGO 街角建筑，
而非人手在 CAD 里摆出来的模型。**

全部几何来自 `generate_noodleshop.py` 的算术推导 —— 没有一个坐标是手写的。
模型组织成 **5 个 section / 285 条放置指令**，展开为 **360 个物理零件**
（LeoCAD 独立导出的 BOM 复核一致）；共 **29 种零件-颜色组合、7 种颜色**。

#### 结构分解

| 层级 | 内容 | 高度 |
|---|---|---|
| 底座 | 12 块 6×8 板拼成 24×24 桩 | 8 LDU |
| 街面 | 18 块 2×4 板（店铺前方） | 8 LDU |
| **首层（可拆）** | 12×12 桩、8 层沙绿墙、4 扇窗、玻璃门、柜台、灶台+炒锅/汤锅、2 桌、4 凳、地砖、屋顶板 | 顶面 -200 LDU |
| **二层公寓** | 12×6 桩、8 层深蓝灰墙、2 扇窗、屋顶花箱 + 通风管 | 顶面 -408 LDU |
| 外挂 | 雨篷 4 板 + **8 根门廊柱**、招牌箱、2 盏灯笼、两侧各 3 根 6 段立管、露台护栏、路灯、4 个货箱、送货机器人 | — |

#### 零件构成（实测 BOM）

| 零件 | 数量 | 占比 | 主要用途 |
|---|---|---|---|
| `3005` Brick 1×1 | 94 | 26.1% | 立管 36 + 门廊柱 48 + 机器人/灯笼/植物/桌凳腿 |
| `3020` Plate 2×4 | 72 | 20.0% | 街面 / 屋顶 / 楼板 |
| `3009` Brick 1×6 | 66 | 18.3% | 墙体砌筑（沙绿 36 + 深蓝灰 30） |
| `3010` Brick 1×4 | 34 | 9.4% | 墙体、招牌箱 |
| `3004` Brick 1×2 | 18 | 5.0% | 机器人手臂等 |
| `3036` Plate 6×8 | 12 | 3.3% | 底座 |
| `60592` 窗框 + `60601` 玻璃 | 各 6 | — | 首层 4 扇 + 公寓 2 扇 |

> **特性**：超过 **1/4** 的零件是 1×1 砖 —— 这是"管道/栏杆/立柱"类细节的代价，
> 也是零件数从 320 涨到 360 的直接原因（雨篷从 2 根柱加到 8 根，单这一项 +24 块）。

### 它的五种用途（按重要性排序）

| # | 用途 | 说明 |
|---|---|---|
| 1 | **工具链端到端验收证据** | 不是"能跑"，而是六步**全绿**：生成器 → plan.json → build → validate → render → cad-check，每步都有机器出具的结果 |
| 2 | **验证"写代码建模"方法可迁移** | 文章 Claim 是"3D 建模 = 写代码"。本次证明：一个**无前沿模型、无 API、无 Docker** 的 Windows 环境也能产出合规模型。`plan.json` 那 285 行 JSON 就是"模型源码" —— 可 diff、可版本管理、可 code review，这是传统 CAD 拖拽做不到的 |
| 3 | **基准线（baseline）** | 未来真 agent 跑同一提示词后，可逐项对照：零件数 360 / 几何违规 0 / 迭代 2 轮 / 是否需人介入。**没有基准就无法判断 agent 产物的好坏** |
| 4 | **回归测试 fixture** | 环境重装后（尤其丢掉 Windows 三补丁时），跑一遍此模型即可定位链路坏在哪一环，比读文档快 |
| 5 | **可分解教学样本** | 5 个 section 可单独渲染/替换 —— 抽掉 `noodle-upper` 即纯店铺，抽掉 `noodle-ground` 即"首层可拆"的字面演示 |

### 它证明不了什么（务必保留）

1. **`physical_validity: "not_proven"`** —— 工具证明的只是"格式正确 + 几何 0 穿透 + 主要构件有支撑"，
   **没证明真能拿实体积木拼起来**。已知未解决：屋顶板中间无支撑、灯笼为悬挂。
2. **不等于 2175 块那个量级** —— 360 vs 2175，差的不是"多堆一会儿"，而是**长链路规划能力**；
   作者那个量级需前沿模型撑住几十轮工具调用，单次 token 成本几十美元量级。
3. **不是纯自主产物** —— 闭环中"看渲染图找问题"一环由人代劳（当前模型不支持读图）。

---

## 九、自建检查工具（本次新增）

| 脚本 | 作用 | 当前结果 |
|---|---|---|
| `output/check_geom.py` | 展开所有矩形件，**两两 AABB 体块比对**报穿透 | 346 件 → **overlaps: 0** |
| `output/check_support.py` | 找出**底面无支撑**的件（顶面贴合判定） | 25 / 346 |

`check_support` 的 25 项分解：

- 12 项 = 底座板（**误报**：落在地面而非零件上）
- 2 项 = 灯笼（**有意设计**：挂在雨篷下）
- 其余 = 窗楣上方墙体（下方是窗框，非矩形件查不到 → **误报**）
- **屋顶板中间无支撑（真问题）**

---

## 十、踩坑与修复记录（8 条，都是真踩过的）

1. **`plate_field()` 中心公式错**：写成 `(c + pw/2)*STUD`，正确是 `(c*pw + pw/2)*STUD` → 一错就是 200+ 块互相穿模
2. **砖高 24 ≠ 板高 8**：给砖用了板的 Y（-8），立管直接沉进底座 16 LDU
3. **2×2 件中心必须是 20 的倍数、1×1 是 10 的奇倍数**：灶台按直觉摆会压到柜台
4. **`3004` "Brick 1 x 2" 是 x=2、z=1**，不是 1 桩宽 → 撞穿机器人身体
5. **`tile()` 铺不满即抛错**：`(6,4)` 铺 5 桩区间当场报错，避免静默错位
6. **雨篷太低**：原 `Y=-112`（只有窗楣高，横插门洞中部）→ 改为坐门头顶面 `FLOOR_TOP - DOOR_H - PLATE = -160`
7. **雨篷外排悬空** → 柱子由 2 根增到 8 根两排，两排板各自有支撑
8. **机器人手臂 vs 货箱互穿** → 机器人移到 `x=160`

### 核心约定（写生成器必须记住）

- `at:[x,Y,z]` 的 **Y 是零件顶面**，实体占 `[Y, Y+h]`；**往上堆 = Y 变小**，首层砖是 `-24` 不是 `-8`
- 零件尺寸查 `ldraw_tools/data/rectangular-parts.json`，**别信零件名**（`3009` "Brick 1 x 6" 实为 x=6、z=1）
- 砖体包络必须**精确拼合**，重叠即判定碰撞
- **子模型引用行要给显性颜色**，否则报 `colour.unresolved_current`

---

## 十一、迭代记录（人机协作的"渲染→看→改"）

| 轮次 | 反馈 | 改动模块 | 结果 |
|---|---|---|---|
| 1 | 雨篷悬空、没门高、像插在门中间 | 门头：雨篷升至门顶、招牌移到雨篷上、灯笼移到 x=±20 | 336 块全绿 |
| 2 | （自查发现）雨篷外排无支撑 | 门头：柱子 4 → 8，两排 | **360 块全绿** |

> 这就是文章「渲染 → 看 → 改」的核心循环，只是**评审由人代劳**（当前模型不支持读图）。

---

## 十二、尚未完成的三项

1. **agent 自主闭环**：`instructions.md` 那套自动流程一次没跑起来（429）。目前是手写生成器 + 人工评审。
2. **2175 块樱花庭院**：作者产物在 `examples/sakura-garden/`（含 `.mpd`/`plan.json`/`bom.json`/`generate.py`/`iterations/`）可**直接渲染看效果**，但渲染别人成品 ≠ 复现生成过程。该量级需 Claude Opus / GPT 级前沿模型长跑，单次 token 成本**几十美元量级**；RTX 5050 本地模型与被限流的 DeepSeek 均撑不住。
3. **物理可搭建性验证**：见下节。

---

## 十三、边界声明（别被渲染图骗了）

`physical_validity` 恒为 **`"not_proven"`**。工具只保证：**格式正确 + 几何无明显穿透 + 主要构件有支撑**。

**已知未解决**：

- 首层与公寓的**屋顶板中间无支撑**（只有四周墙托着，真实 LEGO 需内墙/梁）
- 灯笼为悬挂，无受压支撑（真实 LEGO 需侧向连接件）

作者自己的产物也是这个状态 —— 这是项目定位，不是本机环境缺陷。

---

## 十四、环境炸了怎么重建

```powershell
# 从 nova2.tgz 重新解压后
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install pyldraw3==1.7.0 numpy==2.5.2 jsonschema==4.26.0
```

依赖就这三条（见 `pyproject.toml`）。**然后必须重打第 2 节那三个 Windows 补丁，否则必挂。**

### 排错速查

| 现象 | 处理 |
|---|---|
| `doctor` 里 `leocad` / `pdftotext` 为 null | PATH 未生效，跑第四节前两行 |
| `leocad --version` 回车无输出 | 正常（Qt GUI），加 `2>&1 \| Out-String` |
| `PartNotFoundError ... parts.lst` | Windows symlink 失效，补丁 3 |
| `unknown argument --json`（build） | 改用 `--report` |
| `colour.unresolved_current` | 子模型引用行给显性颜色编号 |
| `body_overlap` 大量报错 | 先跑 `check_geom.py` 定位，别靠 CLI 逐条读 |

---

## 十五、下一步（三选一）

- **A（零成本，推荐先做）**：继续点模块打磨面馆 —— 下一个可点「公寓太秃（加窗/屋檐）」或「屋顶中间加支撑」。一轮只改一个模块。
- **B（才算严格复现）**：等 429 过去，用第五节提示词让 agent **自己跑一遍**，产出物与 360 块对照 —— 只有这步成功，才算"AI 自主建模"复现。
- **C（基建）**：把流程固化成 `run.ps1`（环境变量兜底 + doctor 预检 + 五步串行、失败即停）。
