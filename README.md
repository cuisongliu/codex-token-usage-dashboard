# Codex Token Usage Dashboard

一个不依赖 Node.js 的 Codex token 用量静态看板。

它由两部分组成：

- `usage-static.py`：使用 Python 标准库读取 `config.yaml`，调用用量接口并生成 `usage-data.json` / `usage-data.js`。
- `daily-token-usage.html`：纯静态 BI 看板，读取 `usage-data.js`，展示日、周、月统计和每日明细。

## 安全边界

不要提交这些文件：

- `config.yaml`：包含 API key。
- `usage-data.json` / `usage-data.js`：包含你的真实用量、费用和网关地址。
- `usage-refresh.log` / `usage-refresh.err.log`：本地采集日志。

仓库只保留：

- `config.example.yaml`
- `usage-data.example.js`
- 源码和安装脚本

## 快速开始

安装脚本会先从 `~/.codex/config.toml` 和 `~/.codex/auth.json` 生成本地私有 `config.yaml`，然后立即采集一次数据，再注册每 5 分钟采集任务。

macOS / Linux:

```bash
./install.sh
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

然后打开：

```bash
open daily-token-usage.html
```

Linux 可以用 `xdg-open daily-token-usage.html`，Windows 可以直接双击 HTML 文件。

如果还没有生成 `usage-data.js`，页面会显示 `usage-data.example.js` 里的示例数据。

## Codex Skill

仓库内置一个 Codex skill：

```text
skills/codex-token-usage-dashboard
```

用户可以把这个目录安装到自己的 Codex skills 目录后，用 `$codex-token-usage-dashboard` 让 Codex 自动完成安装和展示。

skill 的默认边界：

- 自动进入或 clone 仓库。
- 自动卸载旧的 dashboard 定时采集任务。
- 自动运行当前平台安装脚本。
- 自动生成或复用本地 `config.yaml`。
- 自动采集一次数据并生成 `usage-data.js`。
- 自动打开 `daily-token-usage.html`。
- 不打印、不提交、不删除 `config.yaml` 里的密钥。

示例：

```text
Use $codex-token-usage-dashboard to install the dashboard, restart the collector, and open the page.
```

## 手动运行

只生成本地配置：

```bash
python3 usage-static.py sync-config
```

采集一次数据：

```bash
python3 usage-static.py collect
```

## 手动配置

也可以手动创建配置：

```bash
cp config.example.yaml config.yaml
chmod 600 config.yaml
```

然后编辑：

- `base_url`：你的 Sub2API / OpenAI-compatible 网关地址。
- `auth_token`：接口鉴权 token。
- `timezone`：统计时区。
- `days`：生成最近多少天的数据。
- `refresh_minutes`：页面刷新和后台采集间隔。

## 自动采集

安装脚本按系统选择定时机制：

- macOS: LaunchAgent
- Linux: systemd user timer，若不可用则回退到 cron
- Windows: Task Scheduler

卸载定时任务：

```bash
./uninstall.sh
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
```

## 数据流

```text
~/.codex/config.toml + ~/.codex/auth.json
            |
            | sync-config, first run only
            v
        config.yaml
            |
            | collect every 5 minutes
            v
 usage-data.json + usage-data.js
            |
            v
 daily-token-usage.html
```

静态页面不会读取 `config.yaml`，也不会接触 API key。
