import pytest
from unittest.mock import patch, AsyncMock
from src.services.setup import get_setup_status, get_suggested_subnets, retest_proxy_user

@pytest.mark.asyncio
async def test_get_setup_status_all_pass():
    with patch("src.services.setup.check_binary") as m_bin, \
         patch("src.services.setup.check_group") as m_grp, \
         patch("src.services.setup.run_cmd_async", new_callable=AsyncMock) as m_cmd, \
         patch("os.path.exists") as m_exists:
        
        m_bin.return_value = (True, "mock_path")
        m_grp.return_value = (True, "mock_group")
        
        async def mock_run_cmd(cmd):
            if "is-enabled" in cmd: return (0, "enabled", "")
            if "ip -o -4 addr" in cmd or "ip addr show dev" in cmd: return (0, "127.0.0.50", "")
            if "which danted" in cmd or "dpkg-query" in cmd: return (0, "/usr/sbin/danted", "")
            return (0, "", "")
        
        m_cmd.side_effect = mock_run_cmd
        m_exists.return_value = True

        status = await get_setup_status()
        
        # Verify schema
        assert status.dante_installed.ok is True
        assert status.curl_installed.ok is True
        assert status.group_exists.ok is True
        assert status.lo_alias.ok is True
        assert status.lo_service.ok is True
        assert status.dantd_service.ok is True
        assert status.venv_ready.ok is True
        assert status.env_file.ok is True

@pytest.mark.asyncio
async def test_get_suggested_subnets():
    with patch("src.services.setup.get_system_subnets", new_callable=AsyncMock) as m:
        m.return_value = [
            {"cidr": "0.0.0.0/0", "label": "Allow public access"},
            {"cidr": "192.168.1.0/24", "label": "Allow Local IP-Subnet"}
        ]
        suggestions = await get_suggested_subnets()
        
        # 0.0.0.0/0 is always first
        assert suggestions[0]["cidr"] == "0.0.0.0/0"
        assert suggestions[0]["label"] == "Allow public access"
        
        assert len(suggestions) == 2
        assert suggestions[1]["cidr"] == "192.168.1.0/24"

@pytest.mark.asyncio
async def test_retest_proxy_user_success():
    with patch("src.services.setup.test_user_socks5", new_callable=AsyncMock) as m:
        m.return_value = (True, "Connected - 1.2.3.4")
        res = await retest_proxy_user("test", "pwd", "127.0.0.50", 7000)
        assert res.ok is True
        assert res.output == "Connected - 1.2.3.4"
