import asyncio
import os
import re
import ipaddress
from typing import Tuple

# Detect at import time whether sudo is usable on this system.
# NoNewPrivs=1 means the kernel blocks any privilege escalation (common in
# IDE sandboxes and some containers). We check once and cache the result.
_sudo_available: bool | None = None

async def _probe_sudo() -> bool:
    """Return True if sudo can actually escalate to root."""
    global _sudo_available
    if _sudo_available is not None:
        return _sudo_available
    if os.geteuid() == 0:
        _sudo_available = True
        return True
    proc = await asyncio.create_subprocess_shell(
        "sudo -n true 2>&1",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    combined = (stdout + stderr).decode()
    # Both "no new privileges" and "a password is required" are non-fatal
    # indicators — the former means it will never work, the latter means
    # NOPASSWD is not configured (password sudo may still work).
    if "no new privileges" in combined:
        _sudo_available = False
    else:
        _sudo_available = proc.returncode == 0  # True only for NOPASSWD=ALL
    return _sudo_available


async def run_cmd_async(
    cmd: str,
    require_root: bool = False,
    sudo_password: str = None,
) -> Tuple[int, str, str]:
    """Run an async shell command with optional sudo escalation.

    When *require_root* is True and the process is not already root:
    - If a *sudo_password* is supplied it is fed to ``sudo -S``.
    - If the system has NoNewPrivs=1 the command is still attempted but the
      caller will receive a non-zero return code and a human-readable stderr
      explaining the restriction.
    """
    if require_root and os.geteuid() != 0:
        escaped = cmd.replace("'", "'\"'\"'")
        if sudo_password:
            cmd = f"printf '%s\\n' '{sudo_password}' | sudo -S bash -lc '{escaped}'"
        else:
            cmd = f"sudo -n bash -lc '{escaped}'"

    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    stdout_s = stdout.decode("utf-8")
    stderr_s = stderr.decode("utf-8")

    # Surface a friendlier message for the "no new privileges" kernel block
    if "no new privileges" in stderr_s:
        stderr_s = (
            "Root access blocked: this process runs with NoNewPrivs=1 (common "
            "in IDE sandboxes or hardened containers). "
            "To fix, run the application as root or configure a NOPASSWD sudoers "
            "entry: `naimul ALL=(ALL) NOPASSWD: ALL`"
        )

    return proc.returncode or 0, stdout_s, stderr_s

async def cmd_exists(cmd: str) -> bool:
    ret, _, _ = await run_cmd_async(f"command -v {cmd} >/dev/null 2>&1")
    return ret == 0

async def detect_iface() -> str:
    ret, stdout, _ = await run_cmd_async("ip route get 1.1.1.1 | awk '/dev/ {for (i=1;i<=NF;i++) if ($i==\"dev\") print $(i+1)}' | head -n1")
    return stdout.strip() or "lo"

async def primary_ip_for_iface(iface: str) -> str:
    ret, stdout, _ = await run_cmd_async(f"ip -4 -o addr show dev {iface} scope global | awk '{{print $4}}' | cut -d/ -f1 | head -n1")
    return stdout.strip()

async def get_system_subnets() -> list[dict]:
    """Detect active IPv4 subnets and return as list of {cidr, label} dicts.

    Always prepends 0.0.0.0/0 so the user can quickly grant public access.
    Labels use plain text; the UI renders colour/icon based on type.
    Returns plain dicts so Jinja2 templates and json.dumps work directly.
    """
    from src.schema import SubnetSuggestion

    _, stdout, _ = await run_cmd_async("ip -o -f inet addr show | awk '{print $4}'")
    subnets: list[SubnetSuggestion] = [
        SubnetSuggestion(cidr="0.0.0.0/0", label="Allow Public access")
    ]
    seen: set[str] = set()
    for line in stdout.strip().split():
        if not line:
            continue
        try:
            net = ipaddress.IPv4Interface(line).network
            if net.prefixlen < 32 and not net.is_loopback:
                cidr = str(net)
                if cidr not in seen:
                    seen.add(cidr)
                    label = "Allow Local IP-Subnet" if net.is_private else "Allow IP-Subnet"
                    subnets.append(SubnetSuggestion(cidr=cidr, label=label))
        except ValueError:
            pass
    return [s.model_dump() for s in subnets]

async def detect_public_ip() -> str:
    urls = [
        "https://ifconfig.me",
        "https://icanhazip.com",
        "https://ipinfo.io/ip",
        "http://ipecho.net/plain"
    ]
    for url in urls:
        ret, stdout, _ = await run_cmd_async(f"curl -4 -sS --max-time 5 {url}")
        ip = stdout.strip()
        if re.match(r"^([0-9]{1,3}\.){3}[0-9]{1,3}$", ip or ""):
            return ip
    return ""

async def restart_danted(sudo_password: str = None) -> bool:
    ret, _, _ = await run_cmd_async("systemctl restart danted && systemctl is-active --quiet danted", require_root=True, sudo_password=sudo_password)
    return ret == 0


def check_binary(name: str) -> tuple[bool, str]:
    """Return (found, path_or_reason) for a binary in PATH.

    Pure Python / no subprocess — suitable for synchronous calls inside
    async services without blocking the event loop.
    """
    import shutil
    path = shutil.which(name)
    return (bool(path), path or f"{name} not found in PATH")


def check_group(name: str) -> tuple[bool, str]:
    """Return (exists, detail) for a POSIX system group.

    Reads /etc/group via the standard library — no subprocess needed.
    """
    import grp as _grp
    try:
        _grp.getgrnam(name)
        return (True, f"Group '{name}' exists")
    except KeyError:
        return (False, f"Group '{name}' not found — run setup.sh")

async def test_user_socks5(username: str, password: str, host: str, port: int) -> Tuple[bool, str]:
    if not await cmd_exists("curl"):
        return False, "curl not installed"
    
    attempts = 3
    last_out = ""
    for _ in range(attempts):
        cmd = f"curl -sS --max-time 15 -x 'socks5h://{username}:{password}@{host}:{port}' https://api.ipify.org"
        ret, stdout, stderr = await run_cmd_async(cmd)
        out = stdout.strip() or stderr.strip()
        last_out = out
        if ret == 0 and re.match(r"^([0-9]{1,3}\.){3}[0-9]{1,3}$", out or ""):
            return True, out
        await asyncio.sleep(1)
    return False, last_out
