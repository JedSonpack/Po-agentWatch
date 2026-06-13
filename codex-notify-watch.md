# Codex 完成通知到 iPhone / 华为手表

Agent Watch 是一个本地 Web UI 工具，用于定制 Codex 完成通知并通过 Bark 推送到 iPhone / 手表。

## 链路

```text
Codex notify hook -> notify_watch.py -> Bark -> iPhone 通知 -> 华为运动健康同步 -> HUAWEI WATCH FIT 4 震动
```

## 快速开始

```bash
cd agent-watch
python3 agent_watch.py serve
```

打开 `http://127.0.0.1:8765`，在 UI 中配置 Bark Key、消息模板和 Logo URL，即可预览和测试发送。

## 配置方式

Agent Watch 使用本地 JSON 配置文件：`.agent-watch/config.json`。

配置位于仓库根目录，可通过 UI 保存。该目录已被 `.gitignore` 忽略，Bark Key 不会被提交到 GitHub。

之前通过环境变量（`BARK_KEY` 等）配置的用户请迁移到 `.agent-watch/config.json`。

## 手动安装到 Codex

本工具不会自动修改 `~/.codex/config.toml`。请在 UI「手动安装到 Codex」区域复制生成的 `notify = [...]` 片段，并手动加入你的 Codex 配置。

示例：
```toml
notify = [“python3”, “/path/to/agent-watch/notify_watch.py”]
```

## 本地测试

```bash
python3 agent_watch.py notify '{“type”:”agent-turn-complete”,”cwd”:”/tmp/agent-watch”,”last-assistant-message”:”任务已完成。”,”input-messages”:[“测试通知”]}'
```

未配置 Bark Key 时，脚本会输出中文错误信息并以退出码 0 退出，不会影响 Codex 任务完成。

## 手表同步

需要满足：
- iPhone 能收到 Bark 通知。
- 华为运动健康允许读取并同步 Bark 通知。
- 手表和 iPhone 保持蓝牙连接。
- 手表没有开启勿扰。
- iPhone 专注模式没有静音 Bark。
