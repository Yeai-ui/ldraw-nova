# LDraw Nova 复现手册 v1

> 项目：https://github.com/anteloc/ldraw-nova
> Docker 包装：https://github.com/anteloc/ldraw-nova-docker
> 当前版本：v0.6.0（唯一 tag，2026-10-21 核实）
> 整理日期：2026-10-21

---

## 0. 先分清你要复现的是哪一层

这个词有两个完全不同的含义，成本差一个数量级：

| 层次 | 做什么 | 门槛 | 花费 |
|---|---|---|---|
| **A. 部署复现** | 把作者的 Web 应用在自己机器上跑起来，用同样的流程生成模型 | Docker + 前沿模型 API | 高（单次大模型跑几十美元） |
| **B. 方法复现** | 复现「AI 写生成程序 → 程序输出 CAD 源码 → 渲染自检 → 迭代」这条链路 | 一个 code agent + 零件库 + 渲染器 | 低（可用已有订阅） |

**建议：先走 B 验证方法，再决定是否投入 A。** 理由见第 6 节。

---

## 1. 本机环境现状（2026-10-21 实测）

```
Git           2.47.1.windows.1     ✅ 已装
Docker        —                    ❌ 未装
Docker Compose —                   ❌
显卡          RTX 5050             ⚠️ 见第 4 节
```

路线 A 必须先装 Docker Desktop（约 1 GB 安装包 + 5 GB 镜像构建空间）。

---

## 2. 路线 A：官方 Docker 部署（完整步骤）

### 步骤 1｜安装 Docker Desktop

- 下载地址：https://www.docker.com/products/docker-desktop/
- Windows 需开启 WSL2 后端，安装时按向导默认即可
- 装完**必须先启动 Docker Desktop**，并确认处于 Linux containers 模式
- 验证：

```bash
git --version
docker --version
docker compose version
```

三条都要出版本号。

### 步骤 2｜并排克隆两个仓库（关键）

**两个仓库必须是同级兄弟目录，不能嵌套。** 且必须用**同一个 tag**：

```bash
mkdir ldraw-nova-lab
cd ldraw-nova-lab
git clone --branch v0.6.0 https://github.com/anteloc/ldraw-nova.git
git clone --branch v0.6.0 https://github.com/anteloc/ldraw-nova-docker.git
```

正确结构：

```
ldraw-nova-lab/
├── ldraw-nova/
└── ldraw-nova-docker/
```

错误结构（Docker 构建会找不到相邻目录）：

```
ldraw-nova-lab/ldraw-nova/ldraw-nova-docker/   ← 不要这样
```

### 步骤 3｜构建镜像

```bash
cd ldraw-nova-docker
docker compose build
```

- 首次构建**约需 5 GB 磁盘**，时间取决于网络（下载 LDraw 完整零件库 + 渲染工具链）
- 中途看似卡住是正常的，看 Docker Desktop 的网络/磁盘占用确认在动
- 报错 `additional_contexts is not supported` → Compose 版本太旧，升级 Docker Desktop

### 步骤 4｜启动与访问

```bash
docker compose up -d
docker compose ps
```

- 主界面：http://localhost:8765
- VR（Meta Quest 3，WebXR）：https://localhost:8443（自签名证书，浏览器会告警）
- 停止：`docker compose down`（**不会**删除数据）

数据落在：
- `ldraw-nova-docker/data/`
- Docker 卷 `ldraw-nova-docker_config`

生成结果在宿主机：`ldraw-nova-docker/data/output/`（每个会话一个目录）

### 步骤 5｜接模型

进 **Settings** 填 API 连接。支持 OpenAI / Anthropic / OpenRouter，另有 Gemini / Azure OpenAI / Ollama 的 LiteLLM 预留位。

本机 Ollama / LM Studio 时，容器内**不能写 localhost**，要写：

```
http://host.docker.internal:11434
```

可选：`TYPESAFE_API_KEY` 启用 jev-rerank 语义重排（零件检索更准）。**没有也能跑**，退化为全文检索。

---

## 3. 第一条提示词（别用"做个最漂亮的"）

```text
Read instructions.md first.

Build a compact cyberpunk street-corner model with a noodle shop,
a narrow apartment above it, signs, pipes and a small delivery robot.

Constraints:
- target 300 to 500 parts;
- fit on a 24 x 24 stud base;
- use dark bluish gray, black, sand green and warm light colors;
- the ground floor must be removable so the interior can be inspected;
- avoid unsupported floating parts and obvious collisions;
- prefer common real LDraw parts;
- organize repeated structures as reusable submodels;
- render and inspect multiple views before finishing;
- deliver the MPD/LDR source, preview images and a CSV bill of materials.
```

好提示词要给出六类信息：**做什么 / 多大 / 什么风格颜色 / 哪里可拆可动 / 禁止什么错误 / 交付什么文件**。

迭代时**每轮只改一个模块**，别让 AI 推倒重来：

```text
Keep the current footprint and main structure.
Improve only the ground-floor storefront:
- make the entrance wider;
- add an interior counter and three seats;
- fix any collisions around the awning;
- render front, right and top views again.
```

---

## 4. 现实检查：钱和硬件

**这是最容易被忽略的部分。**

- 作者明确说：**大型、正确的模型主要依赖高能力模型**（Claude Opus 5.5 / GPT-6 Astra 级别）。低能力模型的工具调用、空间规划、长流程稳定性都不够。
- **RTX 5050 跑本地模型基本没戏。** 不是显存够不够的问题，是能力等级不够——本地 7B~30B 模型在这一长链路 agent 任务上会崩。Docker 部署只是个壳，算力大头在 API 侧。
- 作者估算：**用 Astra 设计单个 Technic 机构约 $5 token 成本**。2175 块的樱花庭院，量级会到几十美元一次。
- 所以：**先做 300~500 块的小模型**，确认渲染与导出链路通了，再逐步加楼层/装饰/机械结构。

---

## 5. 坑与安全

### 排错清单

| 现象 | 原因 / 处理 |
|---|---|
| `additional_contexts` 不支持 | Compose 太旧，升级 Docker Desktop |
| 构建卡住 | 观察 Docker Desktop 网络/磁盘，别急着 Ctrl+C |
| 容器访问宿主机 Ollama 失败 | 用 `host.docker.internal` 而非 `localhost` |
| 零件检索不准 | 配 `TYPESAFE_API_KEY` 启用 jev-rerank |
| 模型能连但做不出来 | 模型能力不足，换前沿模型 |

### 安全（重要）

- **Web 应用默认没有登录系统**，暴露 8765 / 8443 到局域网
- 不要做公网端口映射，不要在公共 Wi-Fi 长期开放
- 不用 VR 时不必开放 8443
- **API Key 不要写进 `docker-compose.yml` 再提交 Git**。用 Web Settings / Docker 卷 / `.env`，`.env` 必须进 `.gitignore`

---

## 6. 路线 B：不装 Docker，直接复现方法（推荐先做）

LDraw Nova 的真正创新**不在 Docker Web 应用**，而在三件事：

1. **instructions.md** —— 给 agent 的领域说明书（LDraw 语法、零件约定、建模规范）
2. **工具集** —— 零件检索、碰撞/间隙检测、无头渲染
3. **工作流约束** —— 强制 agent 先出 plan.json，再写 generator.py，再渲染自检

用 Claude Code / Codex 当 agent，可以零额外成本验证这条链路：

### 最小骨架

```bash
# 1. 拿零件库（LDraw 官方完整包，约 300 MB 解压后 1 GB+）
#    https://www.ldraw.org/help/downloads.html  下载 complete.zip
#    解压到 C:\ldraw\ ，需要 p/ 和 parts/ 两个目录

# 2. 拿渲染器
#    LDView（免费，支持命令行无头渲染）：https://tcobbs.github.io/ldview/
#    或 LeoCAD（带 GUI，可手改模型）

# 3. 拿 instructions.md
git clone https://github.com/anteloc/ldraw-nova.git
# 直接读里面的 instructions.md，它就是这个方法的"核心资产"
```

### 然后让 agent 按这个循环跑

```
你 = agent（Claude Code / Codex）
提示词 = "读 instructions.md，输出 plan.json，再写 generator.py，
        执行它生成 .ldr，用 LDView 渲染正/侧/顶三视图，
        你自己看图找碰撞和悬空，改 generator.py，重跑"
```

**LDView 命令行渲染示例：**

```bash
LDView.exe model.ldr -SaveSnapshot=front.png -SnapshotScale=2
```

这个路线能验证的东西：
- 大模型写生成程序 vs 直接写坐标，质量差异有多大
- 渲染反馈闭环到底提升了多少
- 哪类结构（Technic / 曲面 / 悬挑）是失败重灾区

---

## 7. 输出物对照

一次完整生成留下的东西：

| 产物 | 用途 |
|---|---|
| `.ldr` / `.mpd` | LDraw 源码，可在 LDView / LeoCAD / BrickLink Studio 继续编辑 |
| `.glb` | 导入 Blender 调材质灯光动画 |
| 多视角 PNG | AI 自检用，也可直接放报告 |
| BOM CSV | 零件名 / 颜色 / 数量 / Part ID，可估算真实采购成本 |

---

## 8. 它做不到什么（别被渲染图骗了）

三个层次，只过了前两层的一部分：

1. **格式正确** —— ✅ 文件能打开，零件存在
2. **几何合理** —— 部分 ✅ 无明显穿透、无大片悬空
3. **物理可搭建** —— ❌ **不保证**

作者自己说：这些设计**没有一个真用实体积木搭过**，他连试都没试。

拿到漂亮渲染图后至少人工检查：
- 是否有完全断开的零件组
- 关键承重处是否单点连接
- 装配顺序会不会被后续零件挡死
- 铰链/齿轮/转轴是否真能动
- 零件与颜色组合是否真实生产过

对比 BrickGPT（CMU）：它是在 47000+ 真实结构上训练、显式优化物理可搭建性的；LDraw Nova 走的是开放创意 + agent 工具链路线，**不优化稳定性**。

---

## 9. 建议的执行顺序

1. 先跑**路线 B**：装 LDView + 下零件库 + 用 Claude Code 直接跑一遍 300 块的小模型（成本 ≈ 0）
2. 确认链路真的有效、你也真的需要它
3. 再决定要不要装 Docker 走路线 A、要不要买 API 额度

**在验证方法有效性之前，不要为了一个 Docker 应用去装 Docker + 充 API 额度。**
