#!/usr/bin/env bash
set -Eeuo pipefail

SERVICE_NAME="uralla-build-daemon.service"
DEFAULT_WORKSPACE="${URALLA_WORKSPACE:-$HOME/garmin_lab}"
WORKSPACE="${1:-$DEFAULT_WORKSPACE}"
WORKSPACE="$(cd "$WORKSPACE" 2>/dev/null && pwd -P || true)"

if [[ -z "$WORKSPACE" ]]; then
  printf '[daemon-install] ERROR: workspace does not exist: %s\n' "${1:-$DEFAULT_WORKSPACE}" >&2
  exit 1
fi

LAUNCHER="$WORKSPACE/start"
if [[ ! -x "$LAUNCHER" ]]; then
  printf '[daemon-install] ERROR: workspace launcher is missing: %s\n' "$LAUNCHER" >&2
  printf '[daemon-install] Run setup.sh first, then rerun this installer.\n' >&2
  exit 1
fi

if ! command -v systemctl >/dev/null 2>&1; then
  printf '[daemon-install] ERROR: systemd/systemctl is required\n' >&2
  exit 1
fi
if ! command -v sudo >/dev/null 2>&1 && [[ "$(id -u)" -ne 0 ]]; then
  printf '[daemon-install] ERROR: sudo is required to install the system service\n' >&2
  exit 1
fi

RUN_USER="${SUDO_USER:-$(id -un)}"
if [[ "$RUN_USER" == "root" && "$(id -u)" -eq 0 && -z "${SUDO_USER:-}" ]]; then
  printf '[daemon-install] ERROR: run this script as the normal build user, not directly as root\n' >&2
  exit 1
fi
RUN_GROUP="$(id -gn "$RUN_USER")"
UNIT_PATH="/etc/systemd/system/$SERVICE_NAME"

read -r -d '' UNIT <<EOF || true
[Unit]
Description=Uralla Garmin map build daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
Group=$RUN_GROUP
WorkingDirectory=$WORKSPACE
ExecStart=$LAUNCHER daemon
Restart=on-failure
RestartSec=30
TimeoutStopSec=300
KillMode=mixed
Environment=PYTHONUNBUFFERED=1
UMask=0022

[Install]
WantedBy=multi-user.target
EOF

printf '[daemon-install] installing %s\n' "$UNIT_PATH"
if [[ "$(id -u)" -eq 0 ]]; then
  printf '%s\n' "$UNIT" > "$UNIT_PATH"
  systemctl daemon-reload
  systemctl enable --now "$SERVICE_NAME"
else
  printf '%s\n' "$UNIT" | sudo tee "$UNIT_PATH" >/dev/null
  sudo systemctl daemon-reload
  sudo systemctl enable --now "$SERVICE_NAME"
fi

printf '[daemon-install] service enabled and started\n'
printf '[daemon-install] status:  systemctl status %s\n' "$SERVICE_NAME"
printf '[daemon-install] logs:    journalctl -u %s -f\n' "$SERVICE_NAME"
printf '[daemon-install] stop:    sudo systemctl stop %s\n' "$SERVICE_NAME"
printf '[daemon-install] restart: sudo systemctl restart %s\n' "$SERVICE_NAME"
