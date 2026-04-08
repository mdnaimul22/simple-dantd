import pytest
import json
from unittest.mock import patch, mock_open, AsyncMock
from src.services.state import load_state, save_state, get_proxy_users

@pytest.mark.asyncio
async def test_load_state_missing_file():
    with patch("builtins.open", side_effect=FileNotFoundError):
        result = await load_state()
        assert result == []

@pytest.mark.asyncio
async def test_load_state_valid(tmp_path):
    data = [{"subnet": "1.1.1.1/32", "user": "test", "password": "pwd"}]
    test_json = json.dumps(data)
    with patch("builtins.open", mock_open(read_data=test_json)):
        result = await load_state()
        assert result == data

@pytest.mark.asyncio
async def test_save_state_success(mock_save_state_open):
    result = await save_state([{"subnet": "1.1.1.1/32", "user": "u", "password": "p"}])
    assert result is True
    mock_save_state_open.assert_called()

@pytest.mark.asyncio
async def test_get_proxy_users():
    with patch("src.services.state.list_proxy_users", new_callable=AsyncMock) as m:
        m.return_value = ["testuser1", "testuser2"]
        users = await get_proxy_users()
        assert users == ["testuser1", "testuser2"]
        m.assert_called_once()
