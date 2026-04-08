import os
from src.config import settings
from .system import run_cmd_async

async def list_proxy_users() -> list[str]:
    group = settings.managed_group
    ret, stdout, _ = await run_cmd_async(f"getent group {group} | awk -F: '{{print $4}}' ")
    out = stdout.strip()
    return [u for u in out.split(',') if u]

async def ensure_group(sudo_password: str = None) -> None:
    group = settings.managed_group
    await run_cmd_async(f"getent group {group} || groupadd {group}", require_root=True, sudo_password=sudo_password)

async def ensure_user(username: str, password: str, sudo_password: str = None) -> None:
    await ensure_group(sudo_password)
    group = settings.managed_group
    nologin = "/usr/sbin/nologin" if os.path.exists("/usr/sbin/nologin") else "/sbin/nologin"
    await run_cmd_async(f"id -u {username} >/dev/null 2>&1 || useradd -M -s {nologin} {username}", require_root=True, sudo_password=sudo_password)
    await run_cmd_async(f"echo '{username}:{password}' | chpasswd", require_root=True, sudo_password=sudo_password)
    await run_cmd_async(f"id -nG {username} | grep -qw {group} || usermod -aG {group} {username}", require_root=True, sudo_password=sudo_password)

async def delete_user(username: str, sudo_password: str = None) -> None:
    group = settings.managed_group
    await run_cmd_async(f"id -u {username} >/dev/null 2>&1 && gpasswd -d {username} {group}", require_root=True, sudo_password=sudo_password)
