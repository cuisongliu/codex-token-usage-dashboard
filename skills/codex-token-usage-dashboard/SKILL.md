---
name: codex-token-usage-dashboard
description: Install, configure, operate, and troubleshoot the Codex Token Usage Dashboard from the cuisongliu/codex-token-usage-dashboard repository. Use when the user wants to install the dashboard, generate config.yaml from Codex config, collect token usage, enable or disable five-minute background collection, open the static dashboard, verify no secrets are committed, or debug dashboard installation on macOS, Linux, or Windows.
---

# Codex Token Usage Dashboard

Use this skill to help a user install and operate the static Codex token usage dashboard.

## Repository

Default repository:

```text
https://github.com/cuisongliu/codex-token-usage-dashboard
```

Default local directory:

```text
codex-token-usage-dashboard
```

## Workflow

1. Clone or enter the repository.
2. Run the platform installer.
3. Confirm `config.yaml` was generated locally.
4. Confirm `usage-data.json` and `usage-data.js` were generated locally.
5. Open `daily-token-usage.html`.
6. If the user wants background collection, confirm the scheduled task exists.

Never ask the user to paste their API key. The installer reads Codex credentials from:

```text
~/.codex/config.toml
~/.codex/auth.json
```

## Commands

Clone:

```bash
git clone https://github.com/cuisongliu/codex-token-usage-dashboard.git
cd codex-token-usage-dashboard
```

Install on macOS or Linux:

```bash
./install.sh
```

Install on Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Manual config generation:

```bash
python3 usage-static.py sync-config
```

Manual collection:

```bash
python3 usage-static.py collect
```

Open dashboard:

```bash
open daily-token-usage.html
```

Use `xdg-open daily-token-usage.html` on Linux. On Windows, open the HTML file directly.

Uninstall scheduled collection on macOS or Linux:

```bash
./uninstall.sh
```

Uninstall scheduled collection on Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
```

## Platform Behavior

- macOS: installer registers a LaunchAgent.
- Linux: installer prefers a systemd user timer; if unavailable, it falls back to cron.
- Windows: installer registers a Task Scheduler task.

The installer always runs a one-time collection before registering background collection. That one-time run proves `config.yaml` was loaded and the API is reachable.

## Verification

Check generated files:

```bash
ls -l config.yaml usage-data.json usage-data.js
```

Check generated config without exposing the token:

```bash
python3 usage-static.py print-config
```

Run syntax checks when editing the repo:

```bash
python3 -m py_compile usage-static.py
bash -n install.sh
bash -n uninstall.sh
```

Check macOS task:

```bash
launchctl list | grep io.github.cuisongliu.codex-token-usage-dashboard
```

Check Linux systemd timer:

```bash
systemctl --user status io.github.cuisongliu.codex-token-usage-dashboard.timer
```

Check Linux cron fallback:

```bash
crontab -l | grep io.github.cuisongliu.codex-token-usage-dashboard
```

## Safety

Do not commit generated private files:

```text
config.yaml
usage-data.json
usage-data.js
usage-refresh.log
usage-refresh.err.log
```

Before committing or publishing, scan for:

```text
sk-
Bearer
OPENAI_API_KEY
OSSAccessKeyId
signed object-storage query parameters
private gateway hostnames
```

If any real secret or private endpoint is found, stop and remove it before continuing.

## Troubleshooting

If `config.yaml` is not created:

1. Confirm `~/.codex/config.toml` exists.
2. Confirm `~/.codex/auth.json` exists.
3. Run `python3 usage-static.py sync-config`.
4. Run `python3 usage-static.py print-config`.

If collection fails:

1. Run `python3 usage-static.py collect`.
2. Check that `base_url` in `config.yaml` points to the intended API gateway.
3. Confirm the gateway exposes `/v1/usage`.
4. Confirm `auth_token` is present in `config.yaml`, but do not print it in chat.

If the page only shows example data:

1. Confirm `usage-data.js` exists.
2. Run `python3 usage-static.py collect`.
3. Reload `daily-token-usage.html`.
