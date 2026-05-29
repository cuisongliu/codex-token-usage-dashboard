#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LABEL="io.github.cuisongliu.codex-token-usage-dashboard"

uninstall_macos() {
  local plist="${HOME}/Library/LaunchAgents/${LABEL}.plist"
  launchctl unload "${plist}" >/dev/null 2>&1 || true
  rm -f "${plist}"
  echo "Removed macOS LaunchAgent: ${plist}"
}

uninstall_linux_systemd() {
  local user_dir="${HOME}/.config/systemd/user"
  systemctl --user disable --now "${LABEL}.timer" >/dev/null 2>&1 || true
  rm -f "${user_dir}/${LABEL}.service" "${user_dir}/${LABEL}.timer"
  systemctl --user daemon-reload >/dev/null 2>&1 || true
  echo "Removed Linux systemd user timer."
}

uninstall_linux_cron() {
  local marker="# ${LABEL}"
  local current
  current="$(mktemp)"
  crontab -l > "${current}" 2>/dev/null || true
  grep -v "${marker}" "${current}" > "${current}.next" || true
  crontab "${current}.next"
  rm -f "${current}" "${current}.next"
  echo "Removed Linux cron job."
}

case "$(uname -s)" in
  Darwin)
    uninstall_macos
    ;;
  Linux)
    uninstall_linux_systemd
    if command -v crontab >/dev/null 2>&1; then
      uninstall_linux_cron
    fi
    ;;
  *)
    echo "Unsupported Unix platform: $(uname -s). Use uninstall.ps1 on Windows." >&2
    exit 1
    ;;
esac

echo "Local config and usage data were kept in ${ROOT_DIR}."
