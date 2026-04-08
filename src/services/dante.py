import re
from typing import Tuple
from src.config import settings
from src.providers import detect_iface, primary_ip_for_iface, run_cmd_async

def parse_allowed_clients(conf_text: str) -> list[str]:
    allowed = []
    for m in re.finditer(r"client\s+pass\s*\{[^}]*?from:\s*([^\s]+)\s+to:\s*0.0.0.0/0", conf_text, flags=re.S):
        subnet = m.group(1).strip()
        if subnet not in allowed:
            allowed.append(subnet)
    return allowed

def read_conf() -> str:
    try:
        with open(settings.conf, "r") as f:
            return f.read()
    except Exception:
        return ""

async def write_danted_conf(allowed_subnets: list[str], sudo_password: str = None) -> Tuple[bool, str]:
    iface = await detect_iface()
    bind_ip = await primary_ip_for_iface(iface)
    
    allowed_set = []
    for s in allowed_subnets:
        s = (s or "").strip()
        if s and s not in allowed_set:
            allowed_set.append(s)
            
    if bind_ip and f"{bind_ip}/32" not in allowed_set:
        allowed_set.append(f"{bind_ip}/32")
    if "127.0.0.1/32" not in allowed_set:
        allowed_set.append("127.0.0.1/32")

    content = []
    content.append("# Managed by dante-ui\nlogoutput: syslog\n")
    content.append(f"internal: {iface} port = {settings.default_port}\nexternal: {iface}\n")
    content.append("socksmethod: username\nclientmethod: none\n")
    content.append("user.privileged: root\nuser.unprivileged: nobody\n")
    
    for subnet in allowed_set:
        subnet = subnet.strip()
        if not subnet: continue
        content.append("client pass {\n   from: %s to: 0.0.0.0/0\n   log: connect disconnect\n}\n" % subnet)
        
    content.append("client block {\n   from: 0.0.0.0/0 to: 0.0.0.0/0\n   log: connect disconnect\n}\n")
    
    for subnet in allowed_set:
        subnet = subnet.strip()
        if not subnet: continue
        content.append("socks pass {\n   from: %s to: 0.0.0.0/0\n   command: bind connect udpassociate\n   log: connect disconnect\n}\n" % subnet)
        
    content.append("socks block {\n   from: 0.0.0.0/0 to: 0.0.0.0/0\n   log: connect disconnect\n}\n")
    
    tmp_path = "/tmp/danted.conf.new"
    with open(tmp_path, "w") as f:
        f.write("".join(content))
        
    await run_cmd_async(f"[ -f {settings.conf} ] && cp -a {settings.conf} {settings.conf}.bak.$(date +%s) || true", require_root=True, sudo_password=sudo_password)
    ret, _, stderr = await run_cmd_async(f"mv {tmp_path} {settings.conf} && chown root:root {settings.conf} && chmod 644 {settings.conf}", require_root=True, sudo_password=sudo_password)
    return ret == 0, stderr
