---
name: codex-token-usage-dashboard
description: Automatically install, configure, run, display, browser-verify, and troubleshoot the Codex Token Usage Dashboard from the cuisongliu/codex-token-usage-dashboard repository. Use when the user wants a hands-off install flow that removes any previous scheduled collector, generates config.yaml from Codex config, collects token usage, enables five-minute background collection, opens the static dashboard page, verifies the page in a browser, verifies no secrets are committed, installs this skill with npx skills add, or debugs installation on macOS, Linux, or Windows.
---

# Codex Token Usage Dashboard

Use this skill to install and operate the static Codex token usage dashboard. The default behavior is automatic: remove any existing scheduled collector for this dashboard, install the current one, collect once, open the page, and verify the visible browser result.

## Repository

Default repository:

```text
https://github.com/cuisongliu/codex-token-usage-dashboard
```

Default local directory:

```text
codex-token-usage-dashboard
```

## Boundaries

Do:

- Automatically clone or enter the repository.
- Automatically uninstall the dashboard's existing scheduled collector before installing.
- Automatically run the platform installer.
- Automatically verify local generated files.
- Automatically open `daily-token-usage.html` after a successful install.
- Automatically verify the opened page in the Codex in-app browser when Browser is available.
- Reuse an existing `config.yaml` unless the user explicitly asks to regenerate it.

Do not:

- Print, paste, or commit `auth_token`.
- Commit `config.yaml`, `usage-data.json`, `usage-data.js`, or logs.
- Delete the user's `config.yaml` during uninstall.
- Add another web server or Node.js runtime.
- Force push or overwrite unrelated repository changes.

## Default Auto-Install Workflow

When this skill is invoked, execute the workflow in the current turn instead of only explaining the commands, unless the user asks for a dry run.

1. Clone or enter the repository.
2. Uninstall any previous dashboard scheduled collector. Ignore "not found" failures during uninstall.
3. Run the platform installer from the repo.
4. Confirm `config.yaml` was generated or reused locally.
5. Confirm `usage-data.json` and `usage-data.js` were generated locally.
6. Open `daily-token-usage.html`.
7. Use Browser to inspect the opened page. If Browser blocks `file://`, start a temporary Python stdlib static server on `127.0.0.1`, inspect `/daily-token-usage.html`, then stop the server.
8. Confirm the scheduled task exists and report the opened local path.

Never ask the user to paste their API key. The installer reads Codex credentials from:

```text
~/.codex/config.toml
~/.codex/auth.json
```

## Install This Skill

To install this skill with the skills CLI:

```bash
npx -y skills add cuisongliu/codex-token-usage-dashboard --skill codex-token-usage-dashboard --agent codex -g -y --copy
```

To list available skills before installing:

```bash
npx -y skills add cuisongliu/codex-token-usage-dashboard --list
```

After installing, tell the user to restart Codex before invoking `$codex-token-usage-dashboard`.

## Commands

Clone:

```bash
git clone https://github.com/cuisongliu/codex-token-usage-dashboard.git
cd codex-token-usage-dashboard
```

Auto-install on macOS or Linux:

```bash
./uninstall.sh || true
./install.sh
```

Auto-install on Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Install only on macOS or Linux:

```bash
./install.sh
```

Install only on Windows PowerShell:

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

Open dashboard from an agent:

- macOS: run `open daily-token-usage.html`.
- Linux with desktop: run `xdg-open daily-token-usage.html`.
- Windows PowerShell: run `Start-Process .\daily-token-usage.html`.
- Headless environment: report the absolute path to `daily-token-usage.html`.

## Browser Acceptance

After opening the dashboard, use Browser in the Codex app to inspect the page. Do not rely only on OS-level `open`.

Browser may block direct `file://` navigation. If that happens, start a temporary Python stdlib static server from the dashboard directory, navigate Browser to `http://127.0.0.1:<port>/daily-token-usage.html`, verify the page, and stop the server. This local server is only a verification surface; do not turn it into the dashboard runtime.

The expected page must satisfy:

- The page is not blank.
- The visible page contains `Token 用量`, `日`, `周`, `月`, and `每日明细`.
- The status area indicates the page is reading local `usage-data.js`. If it shows example data, explicitly report that as not fully verified.
- The page does not show config-load, missing-token, or API error text.
- The page does not expose `auth_token`, `Bearer`, `sk-`, or a real API key.

If Browser is unavailable or the environment is headless, report that browser verification was not executed, then verify `usage-data.js`, `usage-data.json`, and `python3 usage-static.py print-config` from the filesystem instead.

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

The printed config must redact the token as `***`.

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

Check Windows scheduled task:

```powershell
Get-ScheduledTask -TaskName CodexTokenUsageDashboard
```

## Refreshing Config

Only regenerate `config.yaml` when the user explicitly asks to reload credentials or provider settings:

```bash
python3 usage-static.py sync-config --force
python3 usage-static.py collect
```

After regeneration, open the page again.

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
