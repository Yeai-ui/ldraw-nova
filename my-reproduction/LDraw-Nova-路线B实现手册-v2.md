# LDraw Nova 路线 B 实现手册 v2

> 目标：不装 Docker，在 Windows 本机直接跑通 `ldraw-agent` 工具链，
> 用 Claude Code / Codex 当 agent 复现「AI 写生成程序 → 程序输出 LDraw 模型 → 渲染自检 → 迭代」。
> 依据：v0.6.0 源码实测（2026-10-21），不是照抄 README。

---

## 0. 核心结论（实测推翻了 v1 的一个假设）

**路线 B 根本不需要 Docker。** 读完源码后发现：

- Web 应用（路线 A）只是 `ldraw-agent` CLI 的一层皮；
- `ldraw-agent` 本体是**纯 Python CLI**（`ldraw_tools/` 包，约 20 个模块）；
- 全部 Python 依赖只有 3 个：`pyldraw3==1.7.0`、`numpy==2.5.2`、`jsonschema==4.26.0`；
- 真正的外部依赖是三样：**LDraw 零件库 + Poppler(pdftotext) + LeoCAD**。

也就是说：路线 A 里的 Docker 镜像，做的正是"装这三个东西 + 跑这套 CLI + 套个 Web 界面"。
我们直接在 Windows 上做同样的事，跳过 Docker 和 Web 界面。

---

## 1. 已完成的部分（本机，2026-10-21 实测）

```text
仓库源码     C:\Users\admin\Desktop\fxian\nova-full\ldraw-nova-0.6.0\   (v0.6.0 完整 184 MB)
Python venv  .venv\ (Python 3.13.14，隔离环境)
依赖         pyldraw3 1.7.0 + numpy 2.5.2 + jsonschema 4.26.0  ✅ 已装
CLI 验证     python -m ldraw_tools.cli --help  ✅ 全部 30 个子命令正常列出
```

CLI 可用子命令（实测输出）：`examples / discover / spaceship / manual / mechanism /
technic / vehicle / catalog / design / part-board / doctor / index / search / part /
colours / spec / sections / study / extract / matrix / profiles / build / validate /
inspect / bom / compare-bom / snap / connectors / cad-check / render / glb`

当前 `doctor` 唯一报错：`Set LDRAW_DIR to the parts library` —— 即缺零件库。

---

## 2. Windows 大坑（实测确认，官方文档没写）

仓库自带的 `ldraw-agent` 启动脚本是 **sh 脚本，硬编码找 `.venv/bin/python`**。
Windows 的 venv 布局是 `Scripts\`，不是 `bin\`，所以：

```bash
./ldraw-agent doctor          # ❌ 在 Windows 上必然失败
```

**Windows 一律用这条等价命令代替一切 `./ldraw-agent`：**

```bash
.venv/Scripts/python.exe -m ldraw_tools.cli <命令>
```

（在仓库根目录 `C:\Users\admin\Desktop\fxian\nova-full\ldraw-nova-0.6.0` 下执行。

同理 `./setup.sh` 也不要直接跑，它的三步已在手工完成：venv → 依赖 → doctor。

---

## 3. 还缺的三样东西

### 3.1 LDraw 零件库（必需，~146 MB 下载 / ~1 GB 解压）

直链（已验证可用，2026-09-30 更新版）：

```bash
cd C:\Users\admin\Desktop\fxian
curl -L -o ldraw-complete.zip "https://library.ldraw.org/library/updates/complete.zip"
```

解压到 `C:\ldraw\`（或任意位置），确认目录里有 `parts\`、`p\`、`LDConfig.ldr`。
然后设置**用户环境变量**：

```powershell
setx LDRAW_DIR "C:\ldraw"
```

（设完重开终端。Git Bash 里临时用 `export LDRAW_DIR=/c/ldraw`。）

### 3.2 Poppler 的 pdftotext（必需）

`spec` 命令要读官方 PDF 规范（`docs/ldraw-specs.pdf`），靠 `pdftotext` 提取文本。
没有它 `doctor` 直接判失败（exit 2）。

- Windows 版：https://github.com/oschwartz10612/poppler-windows/releases
- 解压后把 `poppler-xx\Library\bin`（含 `pdftotext.exe`）加入 PATH

### 3.3 LeoCAD（渲染 + BOM 交叉验证，强烈建议）

agent 的"眼睛"。`render` 命令实际调用的是（源码 external.py 实测）：

```text
leocad -l <零件库> -i <输出.png> -w 1000 -h 800 <模型.mpd>     # 渲染快照
leocad -l <零件库> -csv <bom.csv> <模型.mpd>                   # BOM 导出
```

- 下载：https://github.com/leozide/leocad/releases （Windows 安装包）
- 装完把安装目录加入 PATH，终端里 `leocad --version` 能出版本即可
- LeoCAD 本身也是可视化编辑器，手改模型用它（比 LDView 更贴近本项目）

### 三样装齐后验证

```bash
cd C:\Users\admin\Desktop\fxian\nova-full\ldraw-nova-0.6.0
.venv/Scripts/python.exe -m ldraw_tools.cli doctor
```

期望输出 `checks_passed: true`，`tools` 里 `pdftotext` / `leocad` 都有路径。

---

## 4. 零件库就位后，先建索引

```bash
.venv/Scripts/python.exe -m ldraw_tools.cli index
```

它做的是：对 `parts\`、`p\`、`LDConfig.ldr` 建本地符号链接视图和标题索引（在 `.cache\`，
可随时删除重建，不动原库）。零件检索靠它 + 仓库自带的 `data/ldraw-info.db`（26 MB SQLite FTS5，
只读）。

---

## 5. Agent 循环：怎么用 Claude Code 跑

### 5.1 启动方式

在 Claude Code 里打开仓库根目录，第一条提示词：

```text
Read instructions.md first. Then build a small model:
a compact noodle-shop street corner, 300-500 parts, 24x24 stud base,
dark bluish gray + sand green palette, removable ground floor.
Follow the full workflow in instructions.md: doctor → discover → plan →
build → render → inspect → iterate. Use
.venv/Scripts/python.exe -m ldraw_tools.cli instead of ./ldraw-agent.
```

最后一句是关键——把 Windows 命令替换规则告诉 agent，否则它会去跑 sh 脚本。

### 5.2 它会走的真实流程（摘自 instructions.md，共 7 步）

| 阶段 | 命令（Windows 替换版） | 干什么 |
|---|---|---|
| 1 准备 | `cli doctor` / `cli spec --page 65` | 体检 + 查 LDraw 语言规范 |
| 2 找零件 | `cli search parts 'brick 2 x 4'`、`cli part 3001`、`cli colours 'blue'`、`cli part-board 3001 3010 --outdir output/board` | 检索真实零件、看连接器、渲染零件对比板 |
| 3 找参考 | `cli search submodels 'window OR balcony'`、`cli study data/models-annotated/10270-1.mpd` | 从 4 万+ 标注模型里找可复用结构 |
| 4 写计划 | （AI 写）`output/my-model.plan.json` | 遵守 `ldraw_tools/data/plan.schema.json`，符号引用如 `@arches.Arch1X6...` |
| 5 生成 | （AI 写）`generate.py` + `cli build output/my-model.plan.json --output output/my-model.mpd` | **程序算坐标**，build 前自动过装配/几何检查 |
| 6 自检 | `cli validate output/my-model.mpd --detail full`、`cli render ...` | 碰撞/间隙检测 + 渲染多视角图 |
| 7 迭代 | AI 看渲染图 → 改 plan/generator → 回到 5 | 直到满意，交付 .mpd + BOM + 渲染图 |

### 5.3 关键几何规则（instructions.md 原文，agent 也要遵守）

1. **Y 轴向下为正**；stud 间距 20 LDU；砖体高 24、板体高 8
2. 普通叠放：`y_upper = y_lower - upper_body_height`（stud 不额外加间隙）
3. 禁止拉伸/剪切/镜像完整零件；旋转用 `cli matrix y 90` 算
4. 颜色 16 继承；模型子装配放内嵌 `.ldr` 块

### 5.4 语义检索（可选，没有就退化）

`jev-rerank` 需要 `TYPESAFE_API_KEY`。**不配也能跑**——agent 会自动退到
`discover search ... --engine fts`（SQLite 全文检索），零件找得粗一点而已。
建议：先不配，跑通全链路后再决定。

---

## 6. 成本对照

| | 路线 A（Docker Web） | 路线 B（本机 CLI） |
|---|---|---|
| Docker Desktop | 必装（~1 GB + 5 GB 镜像） | **不需要** |
| 大模型 API | 必须（Astra/Opus 级） | 用你已有的 Claude Code 订阅 |
| 磁盘 | ~6 GB | 零件库 1 GB + LeoCAD ~0.3 GB |
| 一次 500 块小模型 | API 计费，几美元级 | Claude 订阅额度内 |
| 可改动性 | 黑盒 Web | 全链路源码可改（对研究有用） |

---

## 7. 跟你的研究的接口（一段话）

这套链路的研究价值在于**结构**：`instructions.md`（领域说明书）+ 只读参考库
（FTS5 索引）+ 受 schema 约束的中间表示（plan.json）+ 生成器（generator.py）+
物理检查器（validate）+ 渲染反馈闭环。把这个骨架里的"LDraw 零件"换成
"B-Rep 特征 + 加工面"，就是一条可发表的工作流：模型输出可执行的特征构造程序，
由 OCC 验证几何与工艺约束，渲染/检查结果回流给 agent 迭代。
你的 `topology_viewer`（STEP + AAGNet）正好是现成的"参考库 + 验证器"位置。

---

## 8. 下一步（待你确认）

1. **下载零件库**（146 MB，约 2-5 分钟）+ 解压 + 设 `LDRAW_DIR` —— 我可以直接做
2. **装 Poppler + LeoCAD** —— 需要你同意安装新软件；也可以你手动装，我给路径
3. 三样齐了之后，我用 Claude Code 的方式陪你跑第一个 300 块小模型

> 临时文件说明：`fxian\nova.tgz`（118 MB 截断废包）和 `fxian\ldraw-nova\`（空壳）
> 已无用可删；`fxian\nova2.tgz`（184 MB）是源码原包，建议保留；
> `fxian\ldraw-nova-0.6.0\`（截断版目录）也可删，正式目录是 `fxian\nova-full\ldraw-nova-0.6.0\`。
