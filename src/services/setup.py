"""
Setup service — business logic for installation checks and subnet discovery.

Data flow:
    routes.py  →  services/setup.py  →  providers/system.py
                                      →  schema (types only)

This service is the single place that knows HOW to check system state.
Routes ask it for results; providers do the low-level OS calls.
"""
from pathlib import Path

from src.schema import CheckResult, SetupStatusResponse, TestUserResponse
from src.providers import run_cmd_async, check_binary, check_group, test_user_socks5
from src.providers.system import get_system_subnets
from src.config import settings


# ── Subnet suggestions ─────────────────────────────────────────────────────────

async def get_suggested_subnets() -> list[dict]:
    """Return ordered list of {cidr, label} subnet suggestions for the UI dropdown.

    Delegates OS detection to the provider; returns plain dicts so Jinja2
    templates and json.dumps() both work without extra serialisation.
    """
    return await get_system_subnets()


# ── Connectivity re-test ───────────────────────────────────────────────────────

async def retest_proxy_user(user: str, password: str, host: str, port: int) -> TestUserResponse:
    """Run a live SOCKS5 connectivity test for one proxy user and return result."""
    ok, output = await test_user_socks5(user, password, host, port)
    return TestUserResponse(ok=ok, output=output)


# ── Setup / installation status ────────────────────────────────────────────────

async def get_setup_status() -> SetupStatusResponse:
    """Check every installation requirement and return a fully-typed status report.

    Checks (in order):
        1. dante-server binary present
        2. curl binary present
        3. danteproxy system group exists
        4. loopback alias 127.0.0.50 active on lo
        5. lo-alias.service enabled in systemd
        6. simple-dantd.service enabled in systemd
        7. Python virtualenv (.venv) created
        8. .env config file present

    Service checks use `is-enabled` (not `is-active`) so a manual
    `python main.py` run still shows the service as correctly set up.
    """

    # ── internal helper — wraps provider cmd into CheckResult ──────────
    async def _cmd(cmd: str) -> CheckResult:
        """Run a shell command via provider; ok = exit-code 0."""
        ret, out, err = await run_cmd_async(cmd)
        detail = (out or err).strip()[:300] or "(no output)"
        return CheckResult(ok=(ret == 0), detail=detail)

    # ── 1. dante-server ────────────────────────────────────────────────
    _, danted_out, _ = await run_cmd_async(
        "which danted 2>/dev/null || dpkg-query -W -f='${Status}' dante-server 2>/dev/null"
    )
    text = danted_out.strip()
    dante_ok = bool(text) and ("install ok" in text or text.startswith("/"))
    dante = CheckResult(
        ok=dante_ok,
        detail=text or "dante-server not installed — run: sudo apt install dante-server",
    )

    # ── 2. curl ── provider: check_binary (no subprocess) ─────────────
    bin_ok, bin_detail = check_binary("curl")
    curl = CheckResult(ok=bin_ok, detail=bin_detail)

    # ── 3. danteproxy group ── provider: check_group ───────────────────
    grp_ok, grp_detail = check_group("danteproxy")
    group = CheckResult(ok=grp_ok, detail=grp_detail)

    # ── 4. loopback alias ──────────────────────────────────────────────
    _, lo_out, _ = await run_cmd_async("ip addr show dev lo")
    lo_active = "127.0.0.50" in lo_out
    lo_alias = CheckResult(
        ok=lo_active,
        detail="127.0.0.50 is active on lo" if lo_active
               else "Alias missing — run: sudo ip addr add 127.0.0.50/32 dev lo",
    )

    # ── 5. lo-alias.service (is-enabled, not is-active) ───────────────
    lo_svc = await _cmd("systemctl is-enabled lo-alias.service 2>/dev/null")
    if not lo_svc.ok:
        lo_svc = CheckResult(ok=False, detail="lo-alias.service not enabled — run setup.sh")

    # ── 6. simple-dantd.service (is-enabled, not is-active) ───────────
    dantd_svc = await _cmd("systemctl is-enabled simple-dantd.service 2>/dev/null")
    if dantd_svc.ok:
        dantd_svc = CheckResult(ok=True, detail="simple-dantd.service is enabled (app may be running manually)")
    else:
        dantd_svc = CheckResult(ok=False, detail="simple-dantd.service not enabled — run setup.sh")

    # ── 7. Python virtualenv ───────────────────────────────────────────
    root    = Path(__file__).resolve().parent.parent.parent
    venv_py = root / ".venv" / "bin" / "python"
    venv = CheckResult(
        ok=venv_py.exists(),
        detail=str(root / ".venv") + " ready" if venv_py.exists()
               else f"virtualenv not found at {root / '.venv'} — run setup.sh",
    )

    # ── 8. .env file ───────────────────────────────────────────────────
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    env_file = CheckResult(
        ok=env_path.exists(),
        detail=str(env_path) + " present" if env_path.exists()
               else ".env missing — copy .env.example and set DANTE_UI_SECRET",
    )

    return SetupStatusResponse(
        dante_installed=dante,
        curl_installed=curl,
        group_exists=group,
        lo_alias=lo_alias,
        lo_service=lo_svc,
        dantd_service=dantd_svc,
        venv_ready=venv,
        env_file=env_file,
    )
