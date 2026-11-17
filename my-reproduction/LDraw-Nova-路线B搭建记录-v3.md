# LDraw Nova 路线 B 搭建记录 v3（本机实测完成）

> 日期：2026-10-21
> 结论：**除 LeoCAD 渲染外，全链路已在你机器上跑通。**
> 本文件是执行记录 + 复现说明；v1（Docker 路线对照）、v2（方案）继续保留。

---

## 1. 执行结果总览

| 项目 | 状态 | 位置 / 说明 |
|---|---|---|
| 仓库源码 v0.6.0 | ✅ | `C:\Users\admin\Desktop\fxian\nova-full\ldraw-nova-0.6.0\`（184 MB 完整包） |
| Python 环境 | ✅ | `.venv\`，Python 3.13.14 |
| 三个依赖 | ✅ | pyldraw3 1.7.0 / numpy 2.5.2 / jsonschema 4.26.0 |
| **LDraw 零件库** | ✅ | `C:\Users\admin\ldraw\ldraw\`（24,858 个 parts + 1,791 个 p + LDConfig.ldr） |
| **Poppler pdftotext** | ✅ | `C:\Users\admin\nova-bin\poppler-26.09.0\Library\bin\pdftotext.exe` |
| **LeoCAD** | ✅ v26.09 已装 | `C:\Program Files\LeoCAD\`（已进用户 PATH） |
| 环境变量 `LDRAW_DIR` | ✅ 已写（新终端生效） | `C:\Users\admin\ldraw\ldraw` |
| PATH 追加 Poppler | ✅ 已写（新终端生效） | `C:\Users\admin\nova-bin\poppler-26.09.0\Library\bin`（v3.1 已修复写法，见文末增补） |

---

## 2. 功能验证证据（全部实测输出）

```
doctor      library_present: true
            tools: pdftotext ✅   leocad: null（唯一缺项）

index       24,856 个零件建索引

search      parts 'brick 2 x 4' → total 1691
            parts '3001'        → 3001.dat "Brick 2 x 4"

part 3001   code 3001.dat, path ...\parts\3001.dat
            description "Brick 2 x 4", author "James Jessiman", bfc "ccw"
            ✅ 完整元数据 + 连接器 + 包围盒

spec        --page 65 → 从 171 页官方 PDF 正确提取 LDraw 语法规范
            ✅ 证明 Poppler 链路通

build       examples/bridge.plan.json → output/bridge-test.mpd
            checks_passed: true, written: true, diagnostics: []
            collision_method: "AABB broad phase, oriented bounds
            separation, curated rectangular body SAT"
            occurrence_count: 5, bounds min[-60,-36,-40] max[60,8,40]
            physical_validity: "not_proven"   ← 符合项目定位

validate    output/bridge-test.mpd → checks_passed: true

render      ❌ FileNotFoundError —— 缺 leocad.exe（预期内）
```

生成的 `.mpd` 是标准 LDraw 源码，可直接用 LeoCAD / LDView / Studio 打开：

```
0 FILE bridge-main.ldr
0 Small display bridge with two pillars and a studded deck
0 Name: bridge-main.ldr
0 Author: LDraw Nova example
0 !LDRAW_ORG Model
0 // left: left red pillar
1 4 -40 0 0 1 0 0 0 1 0 0 0 1 bridge-pillar.ldr
...
```

---

## 3. 我打的三个 Windows 适配补丁（重要）

项目在 Windows 上是跑不起来的，源码里三处需要改。**这些改动已在你的副本里生效**，
如果重新解压源码，必须重打。

### 补丁 1：不能用 `./ldraw-agent`

仓库的 `ldraw-agent` 是 sh 脚本，硬编码 `.venv/bin/python`；Windows 的 venv 是 `Scripts\`。
**所有 `./ldraw-agent x` 一律换成：**

```bash
.venv/Scripts/python.exe -m ldraw_tools.cli x
```

### 补丁 2：`setup.sh` 也别直接跑

它走 `uv sync` / `python3 -m venv`，在 Windows 上同样不成立。已手工完成其等价步骤。

### 补丁 3：`ldraw_tools/common.py` 的符号链接视图在 Windows 上静默失效（关键）

**症状**：`index` 成功，但之后任何 `part` / `build` 都报
`PartNotFoundError ... parts.lst`，而 parts.lst 里明明有那个零件。

**根因**：`common.py` 用 `symlink_to` 在 `.cache\library-xxx\` 下建 `parts`、`p`、
`LDConfig.ldr` 的链接视图。Windows 无开发者模式/管理员权限时，目录链接创建**不报错但退化成
空的普通目录**（实测：`.cache\...\parts\` 文件数 = 0，`LDConfig.ldr` 大小 = 0 字节），
pyldraw3 读到的是空库。

**修复**（已改，两处）：

1. 链接创建改为幂等：已有有效链接跳过；悬空链接先删再建；已存在的普通文件/目录跳过
   （原代码 `if not link.is_symlink()` 在第二次运行时必然触发 WinError 183）。
2. Windows 分支**直接跳过符号链接视图**，`target = root`，把只读的 `parts.lst`
   生成在真实库目录里。

副作用（无害）：真实库目录下多了 `parts.lst`（1.6 MB）和 `signature` 两个文件。

> 备选方案：开启 Windows「开发者模式」后符号链接可用，就不需要补丁 3 的第 2 条。

---

## 4. 唯一剩余：LeoCAD（需要你手动装）

安装器要求管理员权限（实测 `WinError 740 请求的操作需要提升`），
静默安装被系统拦下，这个必须你亲自点一次 UAC。

**两步：**

1. 双击 `C:\Users\admin\Desktop\fxian\leocad-setup.exe`
   （或在 PowerShell 里 `Start-Process "C:\Users\admin\Desktop\fxian\leocad-setup.exe" -Verb RunAs`）
2. UAC 点「是」，一路默认安装

装完确认终端能找到它：

```bash
leocad --version
```

如果不在 PATH 里，把安装目录（默认 `C:\Program Files\LeoCAD`）加进 PATH，
或告诉我实际路径，我帮你配。

**LeoCAD 到位后**，agent 的眼睛就完整了：

```bash
.venv/Scripts/python.exe -m ldraw_tools.cli render output/bridge-test.mpd --outdir output/bridge-render
.venv/Scripts/python.exe -m ldraw_tools.cli cad-check output/bridge-test.mpd
```

源码里实测的调用形式（`ldraw_tools/external.py`）：

```
leocad -l <零件库> -i <输出.png> -w 1000 -h 800 <模型.mpd>   # 渲染
leocad -l <零件库> -csv <bom.csv> <模型.mpd>                 # BOM 导出
```

---

## 5. 现在怎么用

**新开一个终端**后（让 setx 写入的环境变量生效），在仓库根：

```bash
cd C:\Users\admin\Desktop\fxian\nova-full\ldraw-nova-0.6.0
.venv/Scripts/python.exe -m ldraw_tools.cli doctor
```

> 若环境变量还没生效（当前终端 `echo $LDRAW_DIR` 为空），先执行一次：
> ```bash
> export LDRAW_DIR="C:\\Users\\admin\\ldraw\\ldraw"
> export PATH="/c/Users/admin/nova-bin/poppler-26.09.0/Library/bin:$PATH"
> ```

然后让 Claude Code / Codex 打开这个目录，提示词：

```text
Read instructions.md first.
Build a compact noodle-shop street corner, 300-500 parts, 24x24 stud base,
dark bluish gray + sand green palette, removable ground floor.
Follow the workflow in instructions.md end to end.
IMPORTANT: this is Windows — always use
`.venv/Scripts/python.exe -m ldraw_tools.cli <command>`
instead of `./ldraw-agent <command>`.
```

最后一句必须带上，否则 agent 会去跑 sh 脚本然后失败。

---

## 6. 已验证 vs 未验证

**跑通**：零件检索、零件详情（尺寸/连接器/BFC）、官方规范查询、plan → build 生成、
几何与碰撞校验（AABB + SAT）、BOM、模型文件校验。

**未验证**（依赖 LeoCAD）：多视角渲染、`cad-check` 的 LeoCAD 快照/BOM 交叉验证、
`part-board` 零件对比图、GLB 导出。

**明确做不到**（项目自身限制，不是配置问题）：
物理可搭建性 `physical_validity: "not_proven"` —— 它只保证格式正确与几何合理，
不保证真实能拼起来。

---

## 7. 临时文件

- `fxian\ldraw-complete.zip`（146 MB）、`poppler.zip`（43 MB）、`leocad-setup.exe`（182 MB）
  安装完可删，建议先留着装完 LeoCAD 再说。
- `fxian\nova.tgz`（118 MB 截断废包）、`fxian\ldraw-nova\`（空壳）、
  `fxian\ldraw-nova-0.6.0\`（截断解压目录）都是失败产物，可删。
- `fxian\nova2.tgz`（184 MB）是源码原包，留着。
- `.cache\library-xxx\` 下的空壳目录因安全策略删不掉，无害，忽略即可。

---

## 9. v3.1 增补（2026-10-21 上午）：LeoCAD 渲染闭环验证完成

LeoCAD 26.09 已装到 `C:/Program Files\LeoCAD\`（NSIS 默认路径，UAC 手动确认）。

### 实测通过的最后三项

```
doctor      tools.leocad = C:/Program Files\LeoCAD\leocad.EXE
render      bridge-test.mpd → home.png / top.png / front.png + leocad-bom.csv
            （图内容正确：黄色 4x6 板 + 红蓝 2x2 砖）
cad-check   checks_passed: true, tool: LeoCAD, snapshot/bom 全部创建
```

BOM 与 plan 一致（5 个零件：3003 蓝/红、3022 蓝/红、3032 黄）。

**至此路线 B 全链路 100% 跑通**：plan → build → validate → render → cad-check。

### 又修了一个本机 bug：用户 PATH 被写坏

第 4 节当时的 `setx PATH "%PATH%;C:/Users/.../Library/bin"` 是在 Git Bash 里执行的，
有两个问题：`%PATH%` 是 cmd 语法，bash 不展开，写进注册表的是**字面量**；
路径分隔符还被 MSYS 转成了双斜杠。已用 winreg 直接改回干净值（REG_EXPAND_SZ）：

```
用户 PATH = C:/Users/admin/nova-bin/poppler-26.09.0/Library/bin;C:/Program Files\LeoCAD
```

注意：用户 PATH 本来就不需要 `%PATH%` 前缀（Windows 自动拼接系统 PATH + 用户 PATH）。
旧值备份在 `fxian\path-backup-20261021.txt`。已广播 WM_SETTINGCHANGE，
**新开的终端**即可直接用 `leocad --version` 和 `pdftotext -v` 验证。

### 教训（以后 Windows 下写环境变量）

- 不要在 Git Bash 里 `setx PATH "%PATH%;..."`——bash 不展开 `%PATH%`，会写入字面量。
- 用 `setx` 只追加单条路径且不带 `%PATH%`；或者干脆用 Python winreg 写
  `REG_EXPAND_SZ`，写完广播 `WM_SETTINGCHANGE`。

---

## 10. v3.2 增补：`leocad --version` 无输出之谜 + PATH 二次修复

### 现象

新开一个 Windows 终端，`leocad --version` 回车后**静默返回，无输出、无报错**
（与之前「无法识别」的 CommandNotFoundException 表现不同）。

### 根因：两条独立的问题叠在一起

**(1) LeoCAD 是 Qt GUI 程序（Windows 子系统），直接执行时 stdout 不附着控制台**

实测对比（同一会话）：

```
直接回车   leocad --version                          -> 无输出，exit 0
带管道     (leocad --version 2>&1 | Out-String)      -> "LeoCAD Version 26.09 / Compiled Sep 20 2026"
带管道     (& "C:\...\LeoCAD.exe" --version 2>&1 | Out-String) -> 同上，输出正常
```

**结论：程序装好且可执行，只是 GUI 子系统的标准输出在控制台直接回车时不可见。**

对 `ldraw_tools` 无影响——它用 `subprocess.run(..., capture_output=True)`（走管道），
`render` 已实测正常出图。手动确认时加管道即可：

```
leocad --version 2>&1 | Out-String
```

**(2) 我上一轮的 PATH「修复」把原有用户级条目冲掉了（自伤）**

`setx PATH "..."` 是**整体覆盖**、不是追加。第二次写入时只写了 poppler + LeoCAD 两条，
把原本 HKCU\Environment\Path 里的 WindowsApps / npm / Ollama / Trae / kimi 等条目冲掉了。

已用 winreg 重建为 7 条（从会话环境提取用户级目录 + 目录存在性校验 + 去重）：

```
C:\Users\admin\AppData\Local\Programs\Trae CN\bin
C:\Users\admin\.kimi-code\bin
C:\Users\admin\AppData\Local\Microsoft\WindowsApps
C:\Users\admin\AppData\Local\Programs\Ollama
C:\Users\admin\AppData\Roaming\npm
C:\Users\admin\nova-bin\poppler-26.09.0\Library\bin
C:\Program Files\LeoCAD
```

已广播 WM_SETTINGCHANGE。在新 PATH 下实测 `doctor`：

```
tools.pdftotext = C:\Users\admin\nova-bin\poppler-26.09.0\Library\bin\pdftotext.EXE
tools.leocad    = C:\Program Files\LeoCAD\leocad.EXE
Get-Command leocad => C:\Program Files\LeoCAD\LeoCAD.exe
```

### 教训（升级版，Windows 环境变量）

1. **不要**在 Git Bash 里 `setx PATH "%PATH%;..."` —— bash 不展开 `%PATH%`，写入字面量。
2. **不要**用 `setx` 覆盖整个 PATH —— 它是整体赋值，会冲掉原有条目。
   改 PATH 前**先读出来、去重、拼接、再写回**。
3. 用 Python `winreg` 写 `REG_EXPAND_SZ`，写完广播 WM_SETTINGCHANGE（`SendMessageTimeoutW`）。
4. GUI 子系统程序（如 Qt 应用）在控制台直接回车时 stdout 不可见，验证要加管道或 `2>&1`。
## 11. 自创模型：kiosk v2 —— 从 plan 到渲染全链路（10:52-11:30 补记）

### 产物

| 文件 | 说明 |
|---|---|
| `output/verify_parts.py` | 批量验证 18 个候选零件 ID 是否存在（全部 OK） |
| `output/generate_kiosk.py` | v1（保留作对照，坐标手算有错） |
| `output/generate_kiosk_v2.py` | **v2 终版**，全坐标由代码计算 |
| `output/kiosk_v2.plan.json` | 生成的 plan（~110 个实例） |
| `output/kiosk_v2.mpd` | 构建出的多文件模型 |
| `output/kiosk_v2.build.json` | 构建报告 `checks_passed: true` |
| `output/kiosk_v2-render*/` | home/top/front/back/right 五视角 PNG + BOM CSV |

### 三条决定性的语义（v1 翻车的根因）

1. **LDraw 放置语义**：`at:[x,Y,z]` 的 Y 是**零件顶面**，实体占据 `[Y, Y+h]`。
   往上堆 = 往负方向减。第一层砖放在 `-24`（= `-BRICK`），不是 `-8`（`-PLATE`）。
   v1 把首层放在 `-8`，整堵墙穿模。
2. **零件足迹看包络表，不看名字**：`3009` "Brick 1 x 6" 实际 `x_studs=6, z_studs=1`；
   `3028` "Plate 6 x 12" 实际 x 方向 12 桩。名字里两个数字的顺序和轴对应关系
   极易搞反 —— 以 `ldraw_tools/data/rectangular-parts.json` 为准。
3. **包络必须精确拼合**：body-overlap 检查对砖体不允许重叠，砖缝要自己排。
   环形墙 = 前后两面走满 12 桩（含角），左右两面只走中间 10 桩（6+4）。

### 两个 Windows/工具坑

- **子模型引用颜色**：assembly 模式下每个叶子必须解析出具体颜色（`validation.py:219`）。
  模块内部用 16（current colour）的，引用它的那一行**必须给显性颜色**，
  否则 `colour.unresolved_current`。
- **`build --json` 不存在**：参数是 `--report <file> --detail full|summary`；
  另外本会话 shell 继承的是旧环境变量，`LDRAW_DIR` 要 `export`，LeoCAD/poppler
  要手动补 PATH（新开终端则不需要）。

### 值得复用的生成器写法

`tile(lo, hi, pattern)`：把 `[lo, hi]` 用给定桩数序列精确铺满，铺不满直接抛错
（这次就是它当场抓到"侧垛只有 4 桩不是 8 桩"的手算错误）。
侧墙用 `(6,4)` / `(4,6)` 逐层交替，天然形成错缝砌法。

### 视角备忘

LeoCAD 的 `front` 相机看的是 -Z 面；本模型 `Z_FRONT = +110`（门所在面），
所以看门要用 `--views back`。
