import pytest
from unittest.mock import patch, AsyncMock
from src.schema.models import SetupStatusResponse, CheckResult, TestResult, TestUserResponse

def test_index_redirects_if_not_logged_in(test_client):
    response = test_client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers.get("location") == "/login"

def test_login_page_renders(test_client):
    response = test_client.get("/login")
    assert response.status_code == 200
    assert b"Admin Login" in response.content

def test_valid_login(test_client):
    response = test_client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers.get("location") == "/"
    assert "session" in response.cookies or len(response.headers.get_list('set-cookie')) > 0
    
def test_invalid_login(test_client):
    response = test_client.post("/login", data={"username": "admin", "password": "wrong_password"})
    assert response.status_code == 200
    assert b"Invalid credentials" in response.content

def test_authenticated_dashboard(test_client):
    test_client.post("/login", data={"username": "admin", "password": "admin"})
    response = test_client.get("/")
    assert response.status_code == 200
    assert b"Add Row" in response.content

def test_setup_page_renders(test_client):
    test_client.post("/login", data={"username": "admin", "password": "admin"})
    response = test_client.get("/setup")
    assert response.status_code == 200
    assert b"System Setup" in response.content

@patch("src.api.routes.get_setup_status", new_callable=AsyncMock)
def test_api_setup_status(mock_get_setup_status, test_client):
    c = CheckResult(ok=True, detail="ok")
    mock_get_setup_status.return_value = SetupStatusResponse(
        dante_installed=c, curl_installed=c, group_exists=c,
        lo_alias=c, lo_service=c, dantd_service=c, venv_ready=c, env_file=c
    )
    test_client.post("/login", data={"username": "admin", "password": "admin"})
    response = test_client.get("/api/setup-status")
    assert response.status_code == 200
    data = response.json()
    assert "dante_installed" in data
    assert data["dante_installed"]["ok"] is True

@patch("src.api.routes.deploy_configuration", new_callable=AsyncMock)
def test_save_route(mock_deploy, test_client):
    tr = TestResult(user="test", password="pwd", subnet="0.0.0.0/0", ok=True, output="PASS", cmd="cmd", cmd_display="cmd")
    mock_deploy.return_value = (True, "", [tr], "", 0)
    test_client.post("/login", data={"username": "admin", "password": "admin"})
    response = test_client.post("/save", data={
        "row[1][ip]": "0.0.0.0/0", 
        "row[1][user]": "test", 
        "row[1][pass]": "pwd",
        "sudo_password": "admin"
    }, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers.get("location") == "/result"

@patch("src.api.routes.retest_proxy_user", new_callable=AsyncMock)
def test_retest_user_route(mock_retest, test_client):
    mock_retest.return_value = TestUserResponse(ok=True, output="OK")
    test_client.post("/login", data={"username": "admin", "password": "admin"})
    response = test_client.post("/api/test-user", json={"user": "test", "password": "pwd"})
    assert response.status_code == 200
    assert response.json() == {"ok": True, "output": "OK"}
