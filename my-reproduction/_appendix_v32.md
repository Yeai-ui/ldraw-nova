
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
