# Agent Watch

> Codex 任务跑完，**手表震一下** — 让你不再盯着屏幕等 Agent。

![](https://img.shields.io/badge/Python-3.10+-blue)
![](https://img.shields.io/badge/dependencies-zero-brightgreen)
![](https://img.shields.io/badge/tests-37%20passing-success)

---

## ✨ 这个工具能做什么

派 Codex（OpenAI Agent CLI）跑长任务时，你常常切去刷手机/开会/写文档，回来才发现它早就停在那儿等你了。

**Agent Watch** 把 Codex 的「任务完成」事件**实时推到你手腕上**：

```
Codex 任务完成 → 本地脚本 → Bark → iPhone 通知 → 华为/Apple Watch 震动
```

工作流闭环了：
- ✅ **不用盯屏** — 该写代码写代码、该开会开会
- ✅ **任务完成立刻知道** — 手表震一下，平均 3 秒内
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
| **测试** | `unittest`，37 个用例覆盖渲染、配置、Bark 客户端、Server API |
| **配置** | 仓库本地 `.agent-watch/config.json`，已 git-ignore |

设计原则：
- **零依赖** — clone 下来 `python3 agent_watch.py serve` 就能跑
- **不动全局** — 不会修改你的 `~/.codex/config.toml`，需要手动复制粘贴
- **失败软降级** — Bark 推送失败时退出码仍为 0，绝不阻塞 Codex 任务收尾
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
4. 点 **保存配置** —— 状态栏会告诉你保存到了哪里
5. 点 **发送测试通知** —— 几秒内 iPhone 响一下、手表震一下 ✅

🎉 **看到通知就成功了，到此结束。**

---

## 🔌 接入 Codex（可选）

UI 右下「**手动安装到 Codex**」区域会自动生成两段代码：

### 步骤 A：把这一行加到 `~/.codex/config.toml`

```toml
notify = ["python3", "/你的/路径/notify_watch.py"]
```

> 📌 本工具**不会自动改你的 Codex 全局配置**，需要你自己复制粘贴一次。

### 步骤 B：在终端先测一下脚本能跑通

页面上还会生成一条命令，模拟 Codex 调用脚本时传进来的 JSON 事件：

```bash
python3 /你的/路径/notify_watch.py '<JSON 事件>'
```

直接复制到终端跑，**手机应该会收到一条与 UI 预览完全一致的通知**。
能跑通就说明脚本和 Bark 都 OK，下次你用 Codex 跑任务，结束时手表会自动震。

---

## 📱 手表同步要求（华为为例）

- iPhone 能正常收到 Bark 通知
- **华为运动健康** 允许读取并同步 Bark 通知（在 App 里勾）
- 手表与 iPhone 保持蓝牙连接
- 手表没开「勿扰」
- iPhone 「专注模式」没把 Bark 静音

> 🔔 注意：因为 iOS 跨厂商通知协议限制，**第三方手表（华为/小米/OPPO）只能同步通知文字，不会显示 Logo 图片**。Apple Watch 也只显示 Bark 自己的图标，不显示自定义 Logo。Logo 仅在 iPhone 上看得到。

---

## 🧰 文件 / 目录说明

```
Po-agentWatch/
├── agent_watch.py            # CLI 入口：serve（启 UI）/ notify（钩子）
├── notify_watch.py           # Codex 直接调用的薄壳钩子脚本
├── agent_watch/              # 核心包
│   ├── server.py             # 本地 HTTP 服务 + REST API
│   ├── bark.py               # Bark HTTP 客户端
│   ├── config.py             # JSON 配置读写、合并、校验
│   ├── templates.py          # 标题/正文模板渲染、智能截断
│   ├── notify.py             # 事件解析与分发
│   └── static/               # UI 前端（HTML/CSS/JS）
├── tests/                    # 37 个单元测试
├── examples/config.example.json
└── .agent-watch/config.json  # 用户本地配置（git-ignore，自动生成）
```

---

## 🐛 常见问题

### Q：测试通知点了没反应？
A：错误提示在页面右下角小灰字 `#status` 里，看一眼。
最常见的两种：
- **`SSL: CERTIFICATE_VERIFY_FAILED`** —— python.org 装的 Python 证书没装。跑一次：
  ```bash
  bash "/Applications/Python 3.x/Install Certificates.command"
  ```
- **握手超时** —— 你装了 Clash/V2Ray 等代理软件且开了「设为系统代理」。Bark 是国内服务，不应走代理。临时解：
  - 系统设置 → 网络 → Wi‑Fi → 详细信息 → 代理，**取消勾选 HTTP / HTTPS / SOCKS**
  - 或在代理软件里切到「直连」模式

### Q：手表收不到通知？
A：按上面「手表同步要求」逐项排查。**绝大多数情况是华为运动健康里没开 Bark 的通知同步权限**。

### Q：能改示例事件数据吗？
A：当前版本不能，写死在 `agent_watch/server.py` 的 `SAMPLE_EVENT` 里。要改自己改源码（未来版本会做成 UI 可配）。

### Q：Bark Key 泄露了怎么办？
A：打开 Bark App → 设置 → **重置 Key**，再到 UI 里粘贴新的 Key 保存即可。

---

## 🧪 开发 / 跑测试

```bash
python3 -m unittest discover -s tests -v
```

预期：**37 个用例全部通过**。

---

## 📜 License

MIT — 自由使用、修改、二次分发。
