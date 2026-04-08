import asyncio
import os
import socket
import time
from urllib.parse import quote as urlquote
from typing import Tuple

from src.config import settings
from src.schema import ProxyEntry, TestResult
from src.providers import detect_iface, primary_ip_for_iface, detect_public_ip, restart_danted, test_user_socks5, ensure_user, delete_user
from src.providers.system import _probe_sudo
from .state import save_state
from .dante import write_danted_conf

async def wait_for_port(host: str, port: int, timeout: float = 10.0) -> bool:
    """Wait until a TCP port is accepting connections asynchronously."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            # We use a synchronous probe in an executor, or just open_connection
            fut = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(fut, timeout=1.5)
            writer.close()
            await writer.wait_closed()
            return True
        except (OSError, asyncio.TimeoutError):
            await asyncio.sleep(0.5)
    return False

async def deploy_configuration(entries_data: list[dict], sudo_password: str) -> Tuple[bool, str, list[TestResult], str, int]:
    # Parse to pydantic models
    entries = [ProxyEntry(**e) for e in entries_data]

    # 1. Save State (works without root — stored locally)
    if not await save_state(entries_data):
        return False, "Failed to save state file", [], "", 0

    # 2. Early sudo check — fail fast with a clear message
    #    If already root, skip; if sudo is available, proceed; otherwise abort.
    if os.geteuid() != 0:
        sudo_ok = await _probe_sudo()
        if not sudo_ok:
            return (
                False,
                "State saved ✓ — but system operations require root access. "
                "The app is running under NoNewPrivs=1 (IDE sandbox / container). "
                "To deploy on your server: run `sudo python main.py` or add "
                "`naimul ALL=(ALL) NOPASSWD: ALL` to sudoers.",
                [], "", 0,
            )

    allowed = []
    for entry in entries:
        if entry.subnet and entry.subnet not in allowed:
            allowed.append(entry.subnet)
        if entry.user and entry.password:
            await ensure_user(entry.user, entry.password, sudo_password)

    # 3. Write Config
    ok, err = await write_danted_conf(allowed, sudo_password)
    if not ok:
        return False, f"Failed to write config: {err}", [], "", 0

    # 4. Restart Service
    if not await restart_danted(sudo_password):
        return False, "Failed to restart danted service", [], "", 0

    # 5. Fetch host ip for tests
    iface = await detect_iface()
    ip_iface = await primary_ip_for_iface(iface)
    if not ip_iface:
        ip_iface = await detect_public_ip()
    host_ip = ip_iface or '127.0.0.1'

    # Wait for service readiness
    await wait_for_port(host_ip, settings.default_port, timeout=10.0)

    # 6. Test Connectivities
    results = []
    for entry in entries:
        if entry.user and entry.password:
            ok, out = await test_user_socks5(entry.user, entry.password, host_ip, settings.default_port)
            u_enc = urlquote(entry.user)
            p_enc = urlquote(entry.password)
            real_cmd = f"curl -sS --max-time 20 -x 'socks5h://{u_enc}:{p_enc}@{host_ip}:{settings.default_port}' https://api.ipify.org"
            display_cmd = f"curl -sS --max-time 20 -x 'socks5h://{entry.user}:PASSWORD@{host_ip}:{settings.default_port}' https://api.ipify.org"
            
            res = TestResult(
                user=entry.user,
                password=entry.password,
                subnet=entry.subnet,
                ok=ok,
                output=out,
                cmd=real_cmd,
                cmd_display=display_cmd
            )
            results.append(res)

    return True, "", results, host_ip, settings.default_port

async def remove_user_entry(username: str, sudo_password: str) -> None:
    await delete_user(username, sudo_password)
