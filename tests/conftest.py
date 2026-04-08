import pytest
import asyncio
from unittest.mock import AsyncMock, patch, mock_open

@pytest.fixture
def mock_save_state_open():
    """Mock builtins.open so save_state writes to a fake file (no disk I/O)."""
    with patch("builtins.open", mock_open()) as m:
        yield m

@pytest.fixture
def test_client():
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)
