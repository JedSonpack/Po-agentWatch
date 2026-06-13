# Agent Watch

> AI Agent 任务跑完，**手表震一下** — 让你不再盯着屏幕等 Codex / Claude Code 干完活。

![](https://img.shields.io/badge/Python-3.10+-blue)
![](https://img.shields.io/badge/dependencies-zero-brightgreen)
![](https://img.shields.io/badge/agents-Codex%20%7C%20Claude%20Code-purple)

---

## ✨ 这个工具能做什么

派 Codex 或 Claude Code 跑长任务时，你常常切去刷手机/开会/写文档，回来才发现它早就停在那儿等你了。

**Agent Watch** 把 Agent 的「任务完成」事件**实时推到你手腕上**：

```
Codex / Claude Code 任务完成
        ↓
   本地 notify 脚本
        ↓
       Bark
        ↓
    iPhone 通知
        ↓
华为 / Apple Watch 震动
```

工作流闭环了：
- ✅ **不用盯屏** — 该写代码写代码、该开会开会
- ✅ **任务完成立刻知道** — 手表震一下，平均 3 秒内
- ✅ **支持 Codex 和 Claude Code** — 同一份脚本，两种 Agent 都能用
- ✅ **可定制提醒文案** — 标题/正文/长度/Logo/声音都能自己定，自带实时预览
- ✅ **隐私自托管** — 所有配置在本地，Bark Key 永不上传

---

## 🛠 技术栈

| 维度 | 选择 |
|---|---|
| **语言** | Python 3.10+，**纯标准库**，零第三方依赖 |
| **后端** | `http.server.ThreadingHTTPServer` 启个本地 Web UI |
| **前端** | 原生 HTML / CSS / JS，无构建、无框架 |
| **推送** | [Bark](https://github.com/Finb/Bark)（开源 iOS 推送通道） |
| **测试** | `unittest`，覆盖渲染、配置、Bark 客户端、Server API、Claude/Codex 事件归一化（测试代码仅本地保留） |
| **配置** | `~/.agent-watch/config.json`，用户级，所有项目共用，已 git-ignore |

设计原则：
- **零依赖** — clone 下来 `python3 agent_watch.py serve` 就能跑
- **不动全局** — 不会修改你的 `~/.codex/config.toml` 或 `~/.claude/settings.json`，需要手动复制粘贴
- **Agent 无关** — 内部把不同 Agent 的事件归一化成统一形态，下游一套渲染逻辑
- **失败软降级** — Bark 推送失败时退出码仍为 0，绝不阻塞 Agent 任务收尾
- **绕开代理** — Bark 客户端强制不读系统代理 / 环境变量代理，避免国内常见的 Clash 直连冲突
- **中文优先** — UI、错误提示、文档全中文，国内开发者无障碍

---

## 🚀 快速开始（傻瓜三步）

### 第 1 步：装 Bark App，拿到你的 Key

1. iPhone 打开 App Store，搜索 **Bark**，安装。
2. 打开 Bark，主页面会显示一段地址：
   ```
   https://api.day.app/AbCd1234XyZ.../
   ```
3. 中间那串 **`AbCd1234XyZ...`** 就是你的 **Bark Key**，等下要用。

> 💡 这个 Key 等于你手机的「推送密码」，**别提交到 GitHub、别发群里**。本工具已自动 git-ignore 配置文件，安全。

### 第 2 步：clone 并启动 UI

```bash
git clone https://github.com/JedSonpack/Po-agentWatch.git
cd Po-agentWatch
python3 agent_watch.py serve
```

终端会输出：

```
Agent Watch UI: http://127.0.0.1:8765
```

浏览器打开这个地址。

### 第 3 步：在 UI 里填配置 → 测试推送

1. **Bark Key** 一栏粘贴你刚刚复制的 Key
2. （可选）**Logo URL** 填一张你想在 iPhone 通知上显示的图标地址
3. （可选）**标题/正文模板** 改成你喜欢的样子，右边手表/手机预览**实时跟着变**
4. 点 **保存配置** —— 状态栏会告诉你配置保存到了哪里
5. 点 **发送测试通知** —— 几秒内 iPhone 响一下、手表震一下 ✅

🎉 **看到通知就成功了，基础部分到此结束。**

---

## 🔌 接入你的 AI Agent

UI 底部有「**手动接入 AI Agent**」区域，里面有两个 Tab：**Codex** 和 **Claude Code**。
切换看你想接哪个，每个 Tab 都给出**步骤 1（安装配置）+ 步骤 2（终端测试命令）**，**所有路径都根据你机器自动生成**，复制粘贴即可。

### 接入 Codex

把 UI 给的这一行加到 `~/.codex/config.toml`：

```toml
notify = ["python3", "/你的/路径/notify_watch.py"]
```

下次 Codex 任务结束，手机就会响。

### 接入 Claude Code

把 UI 给的 hooks JSON 合并进 `~/.claude/settings.json`：

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "python3 /你的/路径/notify_watch.py" }
        ]
      }
    ],
    "Notification": [
      {
        "hooks": [
          { "type": "command", "command": "python3 /你的/路径/notify_watch.py" }
        ]
      }
    ]
  }
}
```

下次 Claude Code：
- **主回复结束**（Stop hook）→ 推送「Agent 已完成」
- **请求授权 / 等待你输入**（Notification hook）→ 推送「⏸ Claude 等你确认」

两个时机的标题会自动区分，**不会让你以为「等授权」是「跑完了」**。

> 📌 本工具**不会自动改你的全局配置**，需要你自己复制粘贴一次。
> 同一个 `notify_watch.py` 同时支持两种 Agent —— 内部会自动判别事件类型并适配。
>
> **Bark Key 存在 `~/.agent-watch/config.json`**，由 UI 自动写入，所有项目共用同一份。Codex 和 Claude Code 在任意工作目录下触发时都能读到，不需要为每个项目复制配置。

---

## 🪝 Claude Code Hook 点选择

Claude Code 提供 8 个 hook 点，挂哪个就在哪个时机震表。下表是**适合用来推送通知**的几个：

| Hook | 触发时机 | 推荐挂吗 | 标题 |
|---|---|---|---|
| `Stop` | 主回复结束（一轮对话完成） | ⭐ 强烈推荐 | `Agent 已完成：{project}` |
| `Notification` | Claude 主动弹窗（请求权限 / 等待输入） | ⭐ 强烈推荐 | `⏸ Claude 等你确认：{project}` |
| `SubagentStop` | 子 agent（Task tool）回复结束 | 重度用户可挂 | 暂未支持 |
| `PreToolUse` | 工具调用前 | ❌ 太吵 | — |
| `PostToolUse` | 工具调用后 | ❌ 太吵 | — |
| `UserPromptSubmit` / `SessionStart` / `SessionEnd` | 输入 / 启动 / 关闭 session | ❌ 不需要通知 | — |

### 推荐策略

| 场景 | 推荐挂法 |
|---|---|
| **轻度用户** —— 只想知道任务跑完 | 只挂 `Stop` |
| **中度用户** —— 怕错过权限询问（推荐 ⭐） | 挂 `Stop` + `Notification` |
| **重度用户** —— 子任务也想追踪 | 三个都挂（小心通知轰炸） |

UI 给的默认配置就是「中度用户」方案 —— `Stop` + `Notification` 同时挂上。

### 实践方法

1. **想体验「等授权也震一下」**：直接用 UI 给的 JSON，里面已经包含两个 hook 点。
2. **想只接 Stop（轻度）**：把 JSON 里的 `"Notification"` 数组整段删掉。
3. **想只接 Notification**：反过来，把 `"Stop"` 数组删掉。
4. **想自己加 SubagentStop 等**：当前 `notify.py` 还没认这些事件，会被静默忽略 —— 提个 issue 我加支持。

> 💡 同一个 `notify_watch.py` 处理所有 hook —— 内部 `normalize_event()` 看 `hook_event_name` 字段决定怎么渲染标题，下游 Bark 推送链路一行不动。

---

## 📱 手表同步要求（华为为例）

- iPhone 能正常收到 Bark 通知
- **华为运动健康** 允许读取并同步 Bark 通知（在 App 里勾选）
- 手表与 iPhone 保持蓝牙连接
- 手表没开「勿扰」
- iPhone「专注模式」没把 Bark 静音

> 🔔 注意：因为 iOS 跨厂商通知协议限制，**第三方手表（华为/小米/OPPO）只能同步通知文字，不会显示 Logo 图片**。Apple Watch 也只显示 Bark 自己的图标，不显示自定义 Logo。Logo 仅在 iPhone 上看得到。

---

## 🧰 文件 / 目录说明

```
Po-agentWatch/
├── agent_watch.py            # CLI 入口：serve（启 UI）/ notify（钩子）
├── notify_watch.py           # Agent 直接调用的薄壳钩子脚本
├── agent_watch/              # 核心包
│   ├── server.py             # 本地 HTTP 服务 + REST API
│   ├── bark.py               # Bark HTTP 客户端（强制不走代理）
│   ├── config.py             # JSON 配置读写、合并、校验
│   ├── templates.py          # 标题/正文模板渲染、智能截断
│   ├── notify.py             # 事件解析、Codex/Claude 归一化、分发
│   └── static/               # UI 前端（HTML/CSS/JS）
├── tests/                    # 单元测试（仅本地保留，未随仓库发布）
├── examples/config.example.json
└── ~/.agent-watch/config.json    # 用户级配置，UI 自动生成
                                  # （不在仓库内，所有项目共用一份）
```

---

## 🧠 它是怎么同时支持两种 Agent 的

两种 Agent 把事件传给我们的方式不一样：

| | Codex | Claude Code |
|---|---|---|
| 配置入口 | `~/.codex/config.toml` 的 `notify = [...]` | `~/.claude/settings.json` 的 `hooks.Stop` |
| 触发时机 | 每个 turn 结束（`type: agent-turn-complete`） | 主回复结束（`hook_event_name: Stop`） |
| 数据传递 | argv[1] 是 JSON | stdin 是 JSON |
| 消息内容 | 直接带 `last-assistant-message` | 只带 `transcript_path`，需要从 JSONL 自己提取 |

`notify.py` 里有一个 **`normalize_event()`** 函数把 Claude 形态翻译成 Codex 形态，下游所有渲染逻辑（templates、bark）一行不动。
要再加一种 Agent，只需要在 `normalize_event()` 里加一个 `if` 分支即可。

---

## 🐛 常见问题

### Q：Codex / Claude Code 里 hook 看着没触发，手机收不到推送？
A：先确认 hook 脚本本身**有没有跑** —— Claude Code 对 Stop / Notification 这两个 hook 默认不会在对话窗口冒成功提示，安静成功是预期；Codex 的 notify 也不会有可见反馈。

最常见的失败原因是 Bark Key 没填或填错，配置文件位置在 **`~/.agent-watch/config.json`**。手动验证脚本有没有正常跑通：

```bash
echo '{"hook_event_name":"Stop","cwd":"/tmp","transcript_path":"/nonexistent.jsonl"}' \
  | python3 /你的/路径/notify_watch.py
```

无任何输出 = 推送已发出；有 `Bark Key 不能为空` = 还没在 UI 里保存配置（跑一次 `python3 agent_watch.py serve` 在网页上填 Key 保存即可）；其它错误（如 SSL / HTTP 400）见下一条。

> 💡 历史版本曾把配置存在仓库内 `Po-agentWatch/.agent-watch/`，从其它项目目录调起来读不到。当前版本已统一到 `~/.agent-watch/`，跨项目共用一份，不再需要复制。

### Q：测试通知点了没反应？
A：错误提示在页面右下角小灰字 `#status` 里，看一眼。
最常见的两种：
- **`SSL: CERTIFICATE_VERIFY_FAILED`** —— python.org 装的 Python 证书没装。跑一次：
  ```bash
  bash "/Applications/Python 3.x/Install Certificates.command"
  ```
- **`HTTP Error 400`** —— Bark Key 错了，重新粘贴你 Bark App 里的真实 Key 后保存。

### Q：之前 Bark 推送会被代理软件（Clash/V2Ray）卡住？
A：本项目从 v0.2 起 `bark.py` 强制走 `urllib.ProxyHandler({})`（空代理），**Bark 请求不再读系统代理 / 环境变量代理**。装了 Clash 也无所谓——直接打通。

### Q：手表收不到通知？
A：按「手表同步要求」逐项排查。**绝大多数情况是华为运动健康里没开 Bark 的通知同步权限**。

### Q：能改示例事件数据吗？
A：当前版本不能，写死在 `agent_watch/server.py` 的 `SAMPLE_EVENT` 里。要改自己改源码。

### Q：Bark Key 泄露了怎么办？
A：打开 Bark App → 设置 → **重置 Key**，再到 UI 里粘贴新的 Key 保存即可。

### Q：我手动调脚本测试时一直读不到 transcript 怎么办？
A：Claude 模式下脚本会去读 `transcript_path` 指向的 JSONL 文件。终端模拟时给个不存在的路径**也没事**——脚本会优雅降级成「任务已完成。」，仍然能推送。

---

## 🧪 开发 / 跑测试

> 测试代码 (`tests/`) 仅在维护者本地保留，未随仓库发布。如需从源码完整开发，请联系作者获取测试套件。

如果你本地有 `tests/` 目录：

```bash
python3 -m unittest discover -s tests -v
```

---

## 📜 License

MIT — 自由使用、修改、二次分发。
