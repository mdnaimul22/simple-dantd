from fastapi import APIRouter, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from src.schema import ProxyEntry, APIStateResponse
from src.config import settings
from src.services import load_state, deploy_configuration, remove_user_entry, read_conf, parse_allowed_clients, save_state
from src.providers import list_proxy_users

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
router = APIRouter()
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))

def flash(request: Request, message: str, category: str = "info"):
    if "_messages" not in request.session:
        request.session["_messages"] = []
    request.session["_messages"].append({"message": message, "category": category})

def get_flashed_messages(request: Request, with_categories=True):
    messages = request.session.pop("_messages", []) if "_messages" in request.session else []
    if with_categories:
        return [(m["category"], m["message"]) for m in messages]
    return [m["message"] for m in messages]

def is_authenticated(request: Request) -> bool:
    return request.session.get('auth') is True

def require_auth(request: Request):
    if not is_authenticated(request):
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})

@router.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    return templates.TemplateResponse(
        request=request, name="login.html", context={
            "get_flashed_messages": lambda **kw: get_flashed_messages(request, **kw)
        }
    )

@router.post("/login", response_class=HTMLResponse)
async def login_post(request: Request, username: str = Form(""), password: str = Form("")):
    if username == settings.admin_user and password == settings.admin_pass:
        request.session['auth'] = True
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    flash(request, 'Invalid credentials', 'error')
    return templates.TemplateResponse(
        request=request, name="login.html", context={
            "get_flashed_messages": lambda **kw: get_flashed_messages(request, **kw)
        }
    )

@router.get("/logout")
async def logout(request: Request):
    request.session.pop('auth', None)
    flash(request, 'You have been logged out', 'info')
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    require_auth(request)
    entries = await load_state()
    return templates.TemplateResponse(
        request=request, name="index.html", context={
            "entries": entries,
            "get_flashed_messages": lambda **kw: get_flashed_messages(request, **kw)
        }
    )

@router.post("/save")
async def save(request: Request):
    require_auth(request)
    
    form_data = await request.form()
    sudo_password = form_data.get('sudo_password', '').strip()
    
    if not sudo_password:
        flash(request, 'Sudo password is required for system operations', 'error')
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    entries = []
    # Maximum 100 rows supported in the UI structure
    for i in range(1, 101):
        subnet = form_data.get(f'row[{i}][ip]')
        user = form_data.get(f'row[{i}][user]')
        password = form_data.get(f'row[{i}][pass]')
        if subnet is not None or user is not None or password is not None:
            if any([subnet, user, password]):
                entries.append({
                    'subnet': (subnet or '').strip(),
                    'user': (user or '').strip(),
                    'password': (password or '').strip()
                })

    ok, err, test_results, host_ip, host_port = await deploy_configuration(entries, sudo_password)
    
    if not ok:
        flash(request, err, 'error')
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    flash(request, f'Successfully deployed {len(entries)} entries and tested {len(test_results)} users', 'success')
    return templates.TemplateResponse(
        request=request, name='result.html', context={
            "results": test_results,
            "host": host_ip,
            "port": host_port,
            "get_flashed_messages": lambda **kw: get_flashed_messages(request, **kw)
        }
    )

@router.post("/delete-user")
async def delete_user_route(request: Request, username: str = Form(""), sudo_password: str = Form("")):
    require_auth(request)
    username = username.strip()
    sudo_password = sudo_password.strip()
    if username and sudo_password:
        await remove_user_entry(username, sudo_password)
        flash(request, f"User {username} deleted from {settings.managed_group}", 'info')
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/delete-entry")
async def delete_entry(request: Request, index: int = Form(...)):
    require_auth(request)
    entries = await load_state()
    if 0 <= index < len(entries):
        deleted = entries.pop(index)
        await save_state(entries)
        flash(request, f'Deleted entry: {deleted["subnet"]}', 'info')
    else:
        flash(request, 'Invalid entry index', 'error')
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/api/state", response_model=APIStateResponse)
async def api_state():
    conf_text = read_conf()
    return {
        'config_subnets': parse_allowed_clients(conf_text),
        'managed_users': await list_proxy_users(),
        'state_entries': await load_state(),
    }
