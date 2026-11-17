# LDraw Nova 快速命令卡 v1

> 路线 B（免 Docker）。本机环境：Windows + LeoCAD + Poppler + LDraw 零件库。
> 详细背景见 `LDraw-Nova-路线B搭建记录-v3.md`（含 v3.1 / v3.2 / v3.3 增补）。

## 0. 一句话类比

LDraw Nova 不让你（或 LLM）直接写 3D 坐标，中间隔了一层 **plan.json**：
它不是模型，是**施工下单表**——谁、在哪、什么颜色、起什么作用。
坐标交给生成器算，模型由 `build` 摞出来，最后用 `render` 出图肉眼验收。
少写坐标 = 少出错；错了可机器检查，不靠肉眼。

## 1. 进入环境（Windows，必须）

**注意**：官方的 `./ldraw-agent` 是 sh 脚本，硬编码 `.venv/bin/python`，Windows 上全废。
一律用下面的写法替代所有官方命令。

```powershell
# PowerShell（推荐）或 Git Bash 均可
cd C:\Users\admin\Desktop\fxian\nova-full\ldraw-nova-0.6.0
$env:LDRAW_DIR = "C:\Users\admin\ldraw\ldraw"        # 若已在用户环境变量里可省略
$env:PATH += ";C:\Program Files\LeoCAD;C:\Users\admin\nova-bin\poppler-26.09.0\Library\bin"

# 用这套 Python，不要用系统 python
.\.venv\Scripts\python.exe -m ldraw_tools.cli <子命令>
```

Git Bash 版：

```bash
cd /c/Users/admin/Desktop/fxian/nova-full/ldraw-nova-0.6.0
export LDRAW_DIR="C:/Users/admin/ldraw/ldraw"
export PATH="/c/Program Files/LeoCAD:/c/Users/admin/nova-bin/poppler-26.09.0/Library/bin:$PATH"
P=".venv/Scripts/python.exe"
$P -m ldraw_tools.cli <子命令>
```

体检：

```
$P -m ldraw_tools.cli doctor
```

应看到 `library_present: true`，且 tools 里 `leocad`、`pdftotext` 都有路径。

## 2. 全流程（正面 quintuple）

```
生成 plan.json  →  build  →  validate  →  render  →  cad-check
（算数）          （摞起来）  （合规检查）  （出图）     （复核）
```

### 一条龙示例（本项目实测通过）

```bash
# ① 生成自创模型 plan（所有坐标由代码计算）
$P output/generate_kiosk_v2.py --output output/kiosk_v2.plan.json

# ② 构建成 MPD —— 注意没有 --json，报告走 --report
$P -m ldraw_tools.cli build output/kiosk_v2.plan.json \
     --output output/kiosk_v2.mpd --report output/kiosk_v2.build.json \
     --force --detail full

# ③ 独立复核一遍 MPD
$P -m ldraw_tools.cli validate output/kiosk_v2.mpd

# ④ 出图 + 出 BOM
$P -m ldraw_tools.cli render output/kiosk_v2.mpd --outdir output/kiosk_v2-render

# ⑤ CAD 侧复核
$P -m ldraw_tools.cli cad-check output/kiosk_v2.mpd
```

`checks_passed: true` 才算过。`physical_validity` 永远是 `not_proven`——
工具只给"到目前为止没查出问题"，不给"物理上能拼"的证书。

## 3. 常用查询类命令

| 命令 | 干什么 |
|---|---|
| `part <id>` | 查零件元数据与描述（先确认 ID 存不存在，再写进 plan） |
| `search <词>` | 按描述搜零件 |
| `index` | 重建零件索引 |
| `colours` | 颜色代码表 |
| `spec --page N` | 读 LDraw 规范 PDF（靠 poppler 的 pdftotext） |
| `bom <mpd>` | 物料清单 |
| `inspect <mpd>` | 查看模型结构 |
| `sections <mpd>` | 列出子模型 |
| `snap / connectors` | 连接点、吸附建议 |
| `examples / discover / vehicle / technic / spaceship` | 参考KIT：现成范例与可复用构造 |

## 4. 写自定义 generator 的三条铁律（踩过的坑）

1. **Y 是顶面，不是底面**。`at:[x,Y,z]` 表示零件**顶面**在 Y，实体占 `[Y, Y+h]`。
   往上堆 = Y 变小。首层砖放在 `-24`（`-BRICK`），不是 `-8`。
2. **零件尺寸查 `ldraw_tools/data/rectangular-parts.json`，别信零件名**。
   `3009` "Brick 1 x 6" 实际 `x_studs=6, z_studs=1`；名字里数字顺序和轴极易搞反。
3. **砖体包络要精确拼合**。检查器不允许砖体重叠（它不知道砖缝交错），
   所以环形墙要自己排：前后两面走满、左右两面让出角。
   写代码时用"拼满区间否则报错"的 tile 函数，手算必错。
4. **子模型引用那行要给显性颜色**。模块内用 16（current colour）的话，
   引用它的行必须是具体颜色，否则报 `colour.unresolved_current`。

## 5. 视角备忘

LeoCAD 的 `front` 相机看的是 **-Z** 面。本项目里门在 `Z_FRONT = +110`，
所以**看门要用 `--views back`**。`--views` 支持 home / top / front / back / left / right。

## 6. 已知残留（无害）

- `assembly.disconnected_evidence`：门/窗/底板不在包络表里，连通性只能部分证明。warning，不影响通过。
- `coverage.collision_review`：同理，部分零件缺包络检查。warning。
- 用户环境变量 `LDRAW_DIR` 的持久化值带双斜杠 `C://Users//...`，工具会自动归一化，**不影响使用**（已实测）。
