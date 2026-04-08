<div align="center">

<h1>Simple DantD</h1>

<p>A lightweight, modern web dashboard for managing your Dante SOCKS5 proxy server.<br>
Configure subnets, manage Linux proxy users, deploy config, and verify connectivity — all from the browser.</p>

<p>
  <a href="https://github.com/mdnaimul22/simple-dantd"><img alt="GitHub" src="https://img.shields.io/badge/GitHub-simple--dantd-181717?logo=github"></a>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.110-009688?logo=fastapi&logoColor=white">
  <a href="./LICENSE"><img alt="License" src="https://img.shields.io/badge/License-MIT-2ea44f"></a>
</p>

<p>
  <a href="#quick-start">Quick Start</a> •
  <a href="#features">Features</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#project-structure">Structure</a> •
  <a href="#environment-variables">Config</a> •
  <a href="#api-reference">API</a>
</p>

</div>

---

## Features

- **Secure admin login** — credentials stored in `.env`, session-based auth
- **Smart subnet dropdown** — auto-detects active network interfaces and suggests CIDRs
- **Linux user management** — creates/updates system users in the `danteproxy` group
- **One-click deployment** — writes `/etc/danted.conf` and restarts `danted` via sudo
- **Live connectivity tests** — verifies each proxy user over `socks5h://` after deploy
- **Session-persisted results** — deployment result page accessible via `GET /result` any time
- **System diagnostics** — `/setup` page checks 8 installation requirements with live re-check
- **Clean architecture** — Routes → Services → Providers → Schema (strict Pydantic models)

## Dashboard

<div align="center">
  <img alt="Dante SOCKS5 Management Dashboard" src="docs/.asset/simple-dantd-dashboard.png" width="90%">
</div>

---

## Quick Start

```bash
git clone https://github.com/mdnaimul22/simple-dantd.git
cd simple-dantd
sudo bash setup.sh
```

The setup script handles everything automatically:

| Step | What it does |
|---|---|
| Installs `dante-server` + `curl` | via `apt` |
| Creates `danteproxy` system group | for proxy users |
| Binds loopback alias `127.0.0.50` | active immediately on `lo` |
| Persists alias across reboots | installs `lo-alias.service` (systemd oneshot) |
| Creates Python virtualenv | `.venv` with all pip dependencies |
| Copies `.env.example` → `.env` | only if `.env` does not yet exist |
| Installs `simple-dantd.service` | UI starts automatically on every boot |

After setup, start the service:

```bash
sudo systemctl start simple-dantd
```

Open **http://\<your-server-ip\>:7000** and log in with your admin credentials.

---

## Configure

Edit `.env` before starting — at minimum set a strong secret key:

```ini
ADMIN_USER=admin
ADMIN_PASS=admin
DANTE_UI_SECRET=change-me-in-production
APP_HOST=127.0.0.50
APP_PORT=7000
```

### Useful commands

```bash
sudo journalctl -u simple-dantd -f       # live logs
sudo systemctl status simple-dantd       # service status
sudo systemctl restart simple-dantd      # apply .env changes
```

---

## Using the Dashboard

### 1. Deploy a proxy configuration

1. Log in with your admin credentials.
2. Click **+ Add Row** and fill in Subnet, Username, Password.
   - Use the dropdown arrow to select from auto-detected subnets:
     - `0.0.0.0/0` — allow any client (public access)
     - `45.x.x.x/27` — restrict to your server's IP range
     - `172.x.x.x/16` — restrict to your private network
3. Click **Deploy Configuration →** and enter your sudo password.
4. After deployment the app writes `/etc/danted.conf`, restarts `danted`, and runs connectivity tests.

### 2. View results

After deploy you are redirected to **`GET /result`**, which shows each user's test outcome. You can return to this page any time (it is stored in your session). Each row has a **Test** button to re-run a single check, or use **Re-Test All**.

### 3. Check system setup

Visit **`/setup`** from the dashboard topbar. It runs 8 live checks and shows pass/fail status for each installation requirement.

---

## Running on a Production Server

The UI performs privileged operations (`useradd`, write `/etc/danted.conf`, `systemctl restart danted`). Use one of these approaches:

**Option A — Run as root (simplest)**

```bash
sudo python main.py
```

**Option B — Configure NOPASSWD sudoers**

```bash
sudo visudo
# Add (replace <username> with your Linux user):
<username> ALL=(ALL) NOPASSWD: ALL
```

> [!NOTE]
> In restricted environments (IDE sandboxes, containers with `NoNewPrivs=1`) sudo is blocked at the kernel level. System operations fail gracefully with a descriptive error — profile state is still saved locally.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Linux (Ubuntu / Debian) | Tested on Ubuntu 22.04+ |
| Python 3.11+ | system or conda/pyenv |
| sudo / root access | required for `danted` config + user management |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ADMIN_USER` | `admin` | Web UI login username |
| `ADMIN_PASS` | `admin` | Web UI login password |
| `DANTE_UI_SECRET` | `change-me-secret` | Session signing key — **change in production** |
| `APP_HOST` | `127.0.0.50` | Bind address for the web server |
| `APP_PORT` | `7000` | Bind port |

---

## Architecture

Data flows strictly in one direction:

```
HTTP Request
    │
    ▼
Routes  (src/api/routes.py)
│   Parse input → call ONE service → return dict / template
│   Zero business logic. Zero provider imports.
    │
    ▼
Services  (src/services/)
│   state.py       — load/save profiles + get_proxy_users
│   dante.py       — generate and write /etc/danted.conf
│   deployment.py  — orchestrate full deploy + test flow
│   setup.py       — installation checks + subnet discovery
    │
    ▼
Providers  (src/providers/)
│   system.py      — run_cmd_async, check_binary, check_group,
│                    get_system_subnets, test_user_socks5
│   user_manager.py — ensure_user, delete_user, list_proxy_users
    │
    ▼
Schema  (src/schema/models.py)   ← shared by all layers
    ProxyEntry · TestResult · SubnetSuggestion
    CheckResult · SetupStatusResponse
    TestUserRequest · TestUserResponse
```

---

## Project Structure

```
simple-dantd/
├── main.py                        # FastAPI application entry point
├── pyproject.toml                 # Dependencies (FastAPI, uvicorn, pydantic-settings)
├── setup.sh                       # One-shot installer and systemd setup
├── .env.example                   # Environment variable template
│
├── src/
│   ├── config/                    # AppConfig — Pydantic BaseSettings, single source of truth
│   ├── schema/
│   │   └── models.py              # All Pydantic data contracts
│   ├── providers/
│   │   ├── system.py              # OS-level: run_cmd_async, check_binary, network helpers
│   │   └── user_manager.py        # System user operations (useradd, chpasswd, getent)
│   ├── services/
│   │   ├── state.py               # Persist/load profiles_data/profiles.json
│   │   ├── dante.py               # Build and write /etc/danted.conf
│   │   ├── deployment.py          # Deploy orchestration and connectivity testing
│   │   └── setup.py               # Installation checks and subnet suggestion logic
│   └── api/
│       └── routes.py              # HTTP routes — GET/POST handlers only, no business logic
│
├── web/
│   ├── templates/
│   │   ├── login.html
│   │   ├── index.html             # Main dashboard with smart subnet dropdown
│   │   ├── result.html            # Deployment results (accessible via GET /result)
│   │   └── setup.html             # System diagnostics — 8-step install checker
│   └── static/
│       └── style.css              # Glassmorphic dark-mode CSS design system
│
├── tests/
│   ├── conftest.py
│   ├── test_api/test_routes.py
│   ├── test_providers/test_system.py
│   └── test_services/test_state.py
│
└── profiles_data/
    └── profiles.json              # Persisted proxy configurations (auto-created)
```

---

## API Reference

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/` | Yes | Main dashboard |
| `GET` | `/login` | — | Login page |
| `POST` | `/login` | — | Submit credentials |
| `GET` | `/logout` | Yes | Clear session |
| `POST` | `/save` | Yes | Deploy configuration |
| `GET` | `/result` | Yes | Last deployment results (session-based) |
| `GET` | `/setup` | Yes | System diagnostics page |
| `GET` | `/api/state` | Yes | JSON: subnets, managed users, saved entries |
| `GET` | `/api/setup-status` | Yes | JSON: 8-step installation check results |
| `POST` | `/api/test-user` | Yes | Re-run SOCKS5 connectivity test for one user |

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run all tests
python -m pytest tests/ -v

# Dev server with auto-reload
uvicorn main:app --host 127.0.0.50 --port 7000 --reload
```

---

## License

MIT License — see [LICENSE](./LICENSE) for details.
