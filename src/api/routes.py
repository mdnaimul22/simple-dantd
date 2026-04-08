"""
API routes — HTTP request/response layer only.

Responsibility:
    - Parse HTTP input (path params, form data, JSON body)
    - Call exactly ONE service function per endpoint
    - Return a response dict or template render

This layer MUST NOT import from providers, contain business logic, or
do system calls. All data flows inward through Pydantic-typed services.

    Request → [Routes] → [Services] → [Providers] → OS / external
                   ↑                       ↑
              HTTP types              Schema (Pydantic)
"""
from fastapi import APIRouter, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import json

from src.config import settings
from src.schema import (
    APIStateResponse,
    SetupStatusResponse,
    TestUserRequest,
    TestUserResponse,
)
from src.services import (
    load_state,
    save_state,
    get_proxy_users,
    deploy_configuration,
    remove_user_entry,
    read_conf,
    parse_allowed_clients,
    get_suggested_subnets,
    get_setup_status,
    retest_proxy_user,
)

BASE_DIR  = Path(__file__).resolve().parent.parent.parent
router    = APIRouter()
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))


# ── Session helpers ────────────────────────────────────────────────────────────

def flash(request: Request, message: str, category: str = "info") -> None:
    if "_messages" not in request.session:
        request.session["_messages"] = []
    request.session["_messages"].append({"message": message, "category": category})


def get_flashed_messages(request: Request, with_categories: bool = True):
    msgs = request.session.pop("_messages", []) if "_messages" in request.session else []
    if with_categories:
        return [(m["category"], m["message"]) for m in msgs]
    return [m["message"] for m in msgs]


def is_authenticated(request: Request) -> bool:
    return request.session.get("auth") is True


def require_auth(request: Request) -> None:
    if not is_authenticated(request):
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})


# ── Auth routes ────────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    return templates.TemplateResponse(
        request=request, name="login.html",
        context={"get_flashed_messages": lambda **kw: get_flashed_messages(request, **kw)},
    )


@router.post("/login", response_class=HTMLResponse)
async def login_post(request: Request, username: str = Form(""), password: str = Form("")):
    if username == settings.admin_user and password == settings.admin_pass:
        request.session["auth"] = True
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    flash(request, "Invalid credentials", "error")
    return templates.TemplateResponse(
        request=request, name="login.html",
        context={"get_flashed_messages": lambda **kw: get_flashed_messages(request, **kw)},
    )


@router.get("/logout")
async def logout(request: Request):
    request.session.pop("auth", None)
    flash(request, "You have been logged out", "info")
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


# ── Dashboard ──────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    require_auth(request)
    entries          = await load_state()
    suggested_subnets = await get_suggested_subnets()   # service call, not provider
    return templates.TemplateResponse(
        request=request, name="index.html",
        context={
            "entries": entries,
            "suggested_subnets": suggested_subnets,
            "get_flashed_messages": lambda **kw: get_flashed_messages(request, **kw),
        },
    )


@router.post("/save")
async def save(request: Request):
    require_auth(request)
    form_data     = await request.form()
    sudo_password = form_data.get("sudo_password", "").strip()

    if not sudo_password:
        flash(request, "Sudo password is required for system operations", "error")
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    entries = []
    for i in range(1, 101):
        subnet   = form_data.get(f"row[{i}][ip]")
        user     = form_data.get(f"row[{i}][user]")
        password = form_data.get(f"row[{i}][pass]")
        if any([subnet, user, password]):
            entries.append({
                "subnet":   (subnet   or "").strip(),
                "user":     (user     or "").strip(),
                "password": (password or "").strip(),
            })

    ok, err, test_results, host_ip, host_port = await deploy_configuration(entries, sudo_password)

    if not ok:
        flash(request, err, "error")
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    flash(request, f"Deployed {len(entries)} entries, tested {len(test_results)} users", "success")

    # Store results in session so GET /result can display them after browser back/forward
    request.session["last_results"] = {
        "results": [r.model_dump() for r in test_results],
        "host":    host_ip,
        "port":    host_port,
    }
    return RedirectResponse(url="/result", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/result", response_class=HTMLResponse)
async def result_page(request: Request):
    require_auth(request)
    data = request.session.get("last_results")
    if not data:
        flash(request, "No deployment results found. Please deploy first.", "info")
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    import json as _json
    return templates.TemplateResponse(
        request=request, name="result.html",
        context={
            "results":      data["results"],
            "results_json": _json.dumps(data["results"]),
            "host":         data["host"],
            "port":         data["port"],
            "get_flashed_messages": lambda **kw: get_flashed_messages(request, **kw),
        },
    )


@router.post("/delete-user")
async def delete_user_route(request: Request, username: str = Form(""), sudo_password: str = Form("")):
    require_auth(request)
    username      = username.strip()
    sudo_password = sudo_password.strip()
    if username and sudo_password:
        await remove_user_entry(username, sudo_password)
        flash(request, f"User {username} deleted from {settings.managed_group}", "info")
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/delete-entry")
async def delete_entry(request: Request, index: int = Form(...)):
    require_auth(request)
    entries = await load_state()
    if 0 <= index < len(entries):
        deleted = entries.pop(index)
        await save_state(entries)
        flash(request, f'Deleted entry: {deleted["subnet"]}', "info")
    else:
        flash(request, "Invalid entry index", "error")
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


# ── Setup page ─────────────────────────────────────────────────────────────────

@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    require_auth(request)
    return templates.TemplateResponse(
        request=request, name="setup.html",
        context={"get_flashed_messages": lambda **kw: get_flashed_messages(request, **kw)},
    )


# ── JSON API ───────────────────────────────────────────────────────────────────

@router.get("/api/state", response_model=APIStateResponse)
async def api_state():
    """Read-only snapshot of current Dante config, system users, and saved state."""
    conf_text = read_conf()
    return {
        "config_subnets": parse_allowed_clients(conf_text),
        "managed_users":  await get_proxy_users(),   # via service, not provider
        "state_entries":  await load_state(),
    }


@router.get("/api/setup-status", response_model=SetupStatusResponse)
async def api_setup_status(request: Request):
    """Delegate entirely to the setup service — route has zero business logic."""
    require_auth(request)
    return await get_setup_status()


@router.post("/api/test-user", response_model=TestUserResponse)
async def api_test_user(request: Request, body: TestUserRequest):
    """Delegate entirely to the setup service."""
    require_auth(request)
    if not body.user or not body.password:
        return JSONResponse({"ok": False, "output": "user and password are required"}, status_code=400)
    return await retest_proxy_user(body.user, body.password, body.host, body.port)
