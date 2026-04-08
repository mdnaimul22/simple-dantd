import pytest
from unittest.mock import patch, AsyncMock
from src.providers.system import cmd_exists

@pytest.mark.asyncio
async def test_cmd_exists_success():
    with patch("src.providers.system.run_cmd_async", new_callable=AsyncMock) as m:
        m.return_value = (0, "", "")
        assert await cmd_exists("curl") is True
        m.assert_called_once_with("command -v curl >/dev/null 2>&1")

@pytest.mark.asyncio
async def test_cmd_exists_failure():
    with patch("src.providers.system.run_cmd_async", new_callable=AsyncMock) as m:
        m.return_value = (1, "", "")
        assert await cmd_exists("missingcmd") is False
        m.assert_called_once_with("command -v missingcmd >/dev/null 2>&1")
