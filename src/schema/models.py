from pydantic import BaseModel
from typing import Optional


class ProxyEntry(BaseModel):
    subnet: str
    user: str
    password: str


class TestResult(BaseModel):
    user: str
    password: str
    subnet: str
    ok: bool
    output: str
    cmd: str
    cmd_display: str


class APIStateResponse(BaseModel):
    config_subnets: list[str]
    managed_users: list[str]
    state_entries: list[dict]


# ── Subnet suggestion returned to the dashboard dropdown ──────────────
class SubnetSuggestion(BaseModel):
    cidr: str    # e.g. "0.0.0.0/0" or "45.64.135.0/27"
    label: str   # e.g. "Allow Public access" (icon prefix included)


# ── Setup status ──────────────────────────────────────────────────────
class CheckResult(BaseModel):
    ok: bool
    detail: str = ""


class SetupStatusResponse(BaseModel):
    dante_installed: CheckResult
    curl_installed:  CheckResult
    group_exists:    CheckResult
    lo_alias:        CheckResult
    lo_service:      CheckResult
    dantd_service:   CheckResult
    venv_ready:      CheckResult
    env_file:        CheckResult


# ── Test-user request body ────────────────────────────────────────────
class TestUserRequest(BaseModel):
    user: str
    password: str
    host: str = "127.0.0.1"
    port: int = 1080


class TestUserResponse(BaseModel):
    ok: bool
    output: str
