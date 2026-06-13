# Agent Watch

Agent Watch 是一个本地工具，用 Bark 把 Codex 任务完成通知推送到 iPhone，并通过系统通知同步到手表。

## 快速开始

```bash
git clone <repo-url>
cd agent-watch
python3 agent_watch.py serve
```

打开终端输出的本地地址，在页面里配置 Bark Key、消息模板和 Logo URL。

## 手动安装到 Codex

本工具不会自动修改 `~/.codex/config.toml`。请在 UI 中复制生成的 `notify = [...]` 配置片段，并手动加入你的 Codex 配置。

## 本地配置

用户配置保存在 `.agent-watch/config.json`，该目录已被 `.gitignore` 忽略。不要把 Bark Key 提交到 GitHub。
