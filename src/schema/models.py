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
