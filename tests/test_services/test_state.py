import pytest
import json
import tempfile
from unittest.mock import patch, mock_open
from src.services.state import load_state, save_state

@pytest.mark.asyncio
async def test_load_state_missing_file():
    # If the file does not exist, it should return an empty list
    with patch("builtins.open", side_effect=FileNotFoundError):
        result = await load_state()
        assert result == []

@pytest.mark.asyncio
async def test_load_state_valid(tmp_path):
    # Test valid JSON parsing
    data = [{"subnet": "1.1.1.1/32", "user": "test", "password": "pwd"}]
    test_json = json.dumps(data)
    
    with patch("builtins.open", mock_open(read_data=test_json)):
        result = await load_state()
        assert result == data

@pytest.mark.asyncio
async def test_save_state_success(mock_save_state_open):
    """save_state should write to the state file and return True."""
    result = await save_state([{"subnet": "1.1.1.1/32", "user": "u", "password": "p"}])
    assert result is True
    mock_save_state_open.assert_called()
