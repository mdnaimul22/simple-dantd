import pytest

def test_index_redirects_if_not_logged_in(test_client):
    response = test_client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers.get("location") == "/login"

def test_login_page_renders(test_client):
    response = test_client.get("/login")
    assert response.status_code == 200
    # Assert key content present in the new login.html
    assert b"Admin Login" in response.content
    assert b"form" in response.content

def test_valid_login(test_client):
    # Using hardcoded default credentials logic from settings
    response = test_client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers.get("location") == "/"
    
    # Check if a session cookie was set
    assert "session" in response.cookies or len(response.headers.get_list('set-cookie')) > 0
    
def test_invalid_login(test_client):
    response = test_client.post("/login", data={"username": "admin", "password": "wrong_password"})
    assert response.status_code == 200
    assert b"Invalid credentials" in response.content
