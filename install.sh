#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LABEL="io.github.cuisongliu.codex-token-usage-dashboard"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || command -v python || true)}"
CONFIG_PATH="${ROOT_DIR}/config.yaml"
SCRIPT_PATH="${ROOT_DIR}/usage-static.py"
LOG_PATH="${ROOT_DIR}/usage-refresh.log"
ERR_LOG_PATH="${ROOT_DIR}/usage-refresh.err.log"

if [ -z "${PYTHON_BIN}" ]; then
  echo "python3 or python is required." >&2
  exit 1
fi

if "${PYTHON_BIN}" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 9) else 1)
PY
then
  :
else
  echo "Python 3.9+ is required." >&2
  exit 1
fi

install_prerequisites() {
  chmod +x "${SCRIPT_PATH}"
  if [ ! -f "${CONFIG_PATH}" ]; then
    echo "Creating ${CONFIG_PATH} from Codex config..."
    "${PYTHON_BIN}" "${SCRIPT_PATH}" sync-config --config "${CONFIG_PATH}"
  else
    echo "Using existing ${CONFIG_PATH}"
  fi
  chmod 600 "${CONFIG_PATH}" 2>/dev/null || true
  "${PYTHON_BIN}" "${SCRIPT_PATH}" collect --config "${CONFIG_PATH}"
}

install_macos() {
  local plist="${HOME}/Library/LaunchAgents/${LABEL}.plist"
  mkdir -p "${HOME}/Library/LaunchAgents"
  cat > "${plist}" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON_BIN}</string>
    <string>${SCRIPT_PATH}</string>
    <string>collect</string>
    <string>--config</string>
    <string>${CONFIG_PATH}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${ROOT_DIR}</string>
  <key>StartInterval</key>
  <integer>300</integer>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${LOG_PATH}</string>
  <key>StandardErrorPath</key>
  <string>${ERR_LOG_PATH}</string>
</dict>
</plist>
PLIST
  launchctl unload "${plist}" >/dev/null 2>&1 || true
  launchctl load "${plist}"
  launchctl start "${LABEL}" || true
  echo "Installed macOS LaunchAgent: ${plist}"
}

install_linux_systemd() {
  local user_dir="${HOME}/.config/systemd/user"
  local service="${user_dir}/${LABEL}.service"
  local timer="${user_dir}/${LABEL}.timer"
  mkdir -p "${user_dir}"
  cat > "${service}" <<SERVICE
[Unit]
Description=Codex Token Usage Dashboard collector

[Service]
Type=oneshot
WorkingDirectory=${ROOT_DIR}
ExecStart=${PYTHON_BIN} ${SCRIPT_PATH} collect --config ${CONFIG_PATH}
StandardOutput=append:${LOG_PATH}
StandardError=append:${ERR_LOG_PATH}
SERVICE
  cat > "${timer}" <<TIMER
[Unit]
Description=Run Codex Token Usage Dashboard collector every 5 minutes

[Timer]
OnBootSec=30
OnUnitActiveSec=5min
Unit=${LABEL}.service

[Install]
WantedBy=timers.target
TIMER
  systemctl --user daemon-reload
  systemctl --user enable --now "${LABEL}.timer"
  systemctl --user start "${LABEL}.service" || true
  echo "Installed Linux systemd user timer: ${timer}"
}

install_linux_cron() {
  local marker="# ${LABEL}"
  local job="*/5 * * * * cd ${ROOT_DIR} && ${PYTHON_BIN} ${SCRIPT_PATH} collect --config ${CONFIG_PATH} >> ${LOG_PATH} 2>> ${ERR_LOG_PATH} ${marker}"
  local current
  current="$(mktemp)"
  crontab -l > "${current}" 2>/dev/null || true
  grep -v "${marker}" "${current}" > "${current}.next" || true
  printf '%s\n' "${job}" >> "${current}.next"
  crontab "${current}.next"
  rm -f "${current}" "${current}.next"
  echo "Installed Linux cron job."
}

install_linux() {
  if command -v systemctl >/dev/null 2>&1 && systemctl --user status >/dev/null 2>&1; then
    install_linux_systemd
  elif command -v crontab >/dev/null 2>&1; then
    install_linux_cron
  else
    echo "No systemd user session or crontab found. Run manually:" >&2
    echo "${PYTHON_BIN} ${SCRIPT_PATH} watch --config ${CONFIG_PATH}" >&2
    exit 1
  fi
}

install_prerequisites

case "$(uname -s)" in
  Darwin)
    install_macos
    ;;
  Linux)
    install_linux
    ;;
  *)
    echo "Unsupported Unix platform: $(uname -s). Use install.ps1 on Windows." >&2
    exit 1
    ;;
esac

echo "Dashboard: ${ROOT_DIR}/daily-token-usage.html"
