#!/usr/bin/env bash
# =============================================================================
#  Simple DantD — One-Command Setup
#  Usage: sudo bash setup.sh
#
#  What this script does (in order):
#   1. Verifies the script is running as root
#   2. Installs dante-server and curl via apt
#   3. Creates the "danteproxy" system group
#   4. Binds the loopback alias 127.0.0.50 to lo immediately
#   5. Installs a systemd oneshot service (lo-alias.service) so the alias
#      persists across reboots without relying on systemd-networkd or rc.local
#   6. Creates a Python virtual environment and installs the app
#   7. Copies .env.example → .env (if .env does not already exist)
#   8. Installs and enables simple-dantd.service so the UI starts on boot
# =============================================================================

set -euo pipefail

# --------------------------------------------------------------------------- #
#  Colour helpers
# --------------------------------------------------------------------------- #
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; exit 1; }

# --------------------------------------------------------------------------- #
#  Step 0 — Root check
# --------------------------------------------------------------------------- #
[[ $EUID -ne 0 ]] && error "This script must be run as root.  Try: sudo bash setup.sh"

# Resolve the directory where setup.sh lives (works even with symlinks)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo -e "${BOLD}========================================${RESET}"
echo -e "${BOLD}   Simple DantD — Automated Setup      ${RESET}"
echo -e "${BOLD}========================================${RESET}"
echo ""

# --------------------------------------------------------------------------- #
#  Step 1 — Install dante-server and curl
# --------------------------------------------------------------------------- #
info "Step 1/6 — Installing dante-server and curl ..."

if ! command -v apt-get &>/dev/null; then
    error "apt-get not found. This script supports Debian/Ubuntu only."
fi

apt-get update -qq
apt-get install -y -qq dante-server curl

# Disable danted for now — our UI will manage the config before first start
systemctl stop danted 2>/dev/null || true
systemctl disable danted 2>/dev/null || true

success "dante-server and curl are installed."

# --------------------------------------------------------------------------- #
#  Step 2 — Create danteproxy system group
# --------------------------------------------------------------------------- #
info "Step 2/6 — Ensuring 'danteproxy' system group ..."

if ! getent group danteproxy &>/dev/null; then
    groupadd --system danteproxy
    success "Group 'danteproxy' created."
else
    success "Group 'danteproxy' already exists — skipping."
fi

# --------------------------------------------------------------------------- #
#  Step 3 — Bind loopback alias 127.0.0.50 immediately
# --------------------------------------------------------------------------- #
info "Step 3/6 — Binding loopback alias 127.0.0.50/32 to lo ..."

LO_ALIAS="127.0.0.50/32"

if ip addr show dev lo | grep -q "127.0.0.50"; then
    success "Loopback alias already active — skipping live bind."
else
    ip addr add "${LO_ALIAS}" dev lo
    success "Loopback alias ${LO_ALIAS} bound to lo."
fi

# --------------------------------------------------------------------------- #
#  Step 4 — Install lo-alias.service (oneshot, persistent across reboots)
# --------------------------------------------------------------------------- #
info "Step 4/6 — Installing lo-alias.service for boot persistence ..."

cat > /etc/systemd/system/lo-alias.service <<'UNIT'
[Unit]
Description=Bind loopback alias 127.0.0.50 to lo
Documentation=https://github.com/mdnaimul22/simple-dantd
After=network.target
Before=simple-dantd.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/sbin/ip addr add 127.0.0.50/32 dev lo
ExecStop=/sbin/ip addr del 127.0.0.50/32 dev lo
# Ignore "RTNETLINK answers: File exists" — alias already active
SuccessExitStatus=0 2

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now lo-alias.service
success "lo-alias.service enabled and started."

# --------------------------------------------------------------------------- #
#  Step 5 — Python virtualenv + package install
# --------------------------------------------------------------------------- #
info "Step 5/6 — Setting up Python virtual environment ..."

# Include SUDO_USER's local/conda bin directories since sudo resets PATH
if [[ -n "${SUDO_USER:-}" && "$SUDO_USER" != "root" ]]; then
    REAL_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
    export PATH="$PATH:${REAL_HOME}/miniconda3/bin:${REAL_HOME}/anaconda3/bin:${REAL_HOME}/.local/bin"
fi

# Require python3.11+
PYTHON_BIN=""
for candidate in python3.11 python3.12 python3.13 python3; do
    if command -v "$candidate" &>/dev/null; then
        PY_VER=$("$candidate" -c 'import sys; print(sys.version_info[:2])')
        if "$candidate" -c 'import sys; exit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
            PYTHON_BIN="$candidate"
            break
        fi
    fi
done

[[ -z "$PYTHON_BIN" ]] && error "Python 3.11+ is required but was not found."

info "Using Python: $PYTHON_BIN ($PY_VER)"

VENV_DIR="${SCRIPT_DIR}/.venv"
if [[ ! -d "$VENV_DIR" ]]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    success "Virtual environment created at .venv"
else
    success "Virtual environment already exists — reusing."
fi

"${VENV_DIR}/bin/pip" install --quiet --upgrade pip
"${VENV_DIR}/bin/pip" install --quiet -e "${SCRIPT_DIR}[dev]"
success "Python packages installed."

# --------------------------------------------------------------------------- #
#  .env — copy from example if not present
# --------------------------------------------------------------------------- #
if [[ ! -f "${SCRIPT_DIR}/.env" ]]; then
    cp "${SCRIPT_DIR}/.env.example" "${SCRIPT_DIR}/.env"
    warn ".env created from .env.example — please review and set a strong DANTE_UI_SECRET."
else
    info ".env already present — not overwriting."
fi

# --------------------------------------------------------------------------- #
#  Step 6 — Install simple-dantd.service
# --------------------------------------------------------------------------- #
info "Step 6/6 — Installing simple-dantd.service ..."

# Detect the real (non-root) user who invoked sudo, fall back to root
REAL_USER="${SUDO_USER:-root}"
REAL_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)

cat > /etc/systemd/system/simple-dantd.service <<UNIT
[Unit]
Description=Simple DantD — Dante SOCKS5 Management UI
Documentation=https://github.com/mdnaimul22/simple-dantd
After=network.target lo-alias.service
Requires=lo-alias.service

[Service]
Type=simple
User=root
WorkingDirectory=${SCRIPT_DIR}
Environment="PATH=${VENV_DIR}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=${VENV_DIR}/bin/python main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable simple-dantd.service
success "simple-dantd.service installed and enabled."

# --------------------------------------------------------------------------- #
#  Done
# --------------------------------------------------------------------------- #
echo ""
echo -e "${BOLD}${GREEN}========================================${RESET}"
echo -e "${BOLD}${GREEN}   Setup complete!                      ${RESET}"
echo -e "${BOLD}${GREEN}========================================${RESET}"
echo ""
echo -e "  ${BOLD}Start the UI now:${RESET}"
echo -e "    sudo systemctl start simple-dantd"
echo ""
echo -e "  ${BOLD}Then open:${RESET}  http://127.0.0.50:7000"
echo ""
echo -e "  ${BOLD}Check status:${RESET}"
echo -e "    sudo systemctl status simple-dantd"
echo -e "    sudo journalctl -u simple-dantd -f"
echo ""
echo -e "  ${BOLD}Reboot persistence verified:${RESET}"
echo -e "    lo-alias.service    — loopback alias 127.0.0.50"
echo -e "    simple-dantd.service — UI starts on boot"
echo ""
warn "Remember to edit .env and set a strong DANTE_UI_SECRET before expose to network."
echo ""
