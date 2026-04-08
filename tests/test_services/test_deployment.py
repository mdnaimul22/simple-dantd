import pytest
from unittest.mock import patch, AsyncMock
from src.services.deployment import deploy_configuration
from src.schema.models import TestResult

@pytest.mark.asyncio
@patch("os.geteuid", return_value=0)
async def test_deploy_configuration_flow(mock_geteuid):
    async def mock_run_cmd(cmd):
        if "is-enabled" in cmd: return (0, "enabled", "")
        if "ip -o -4 addr" in cmd or "ip addr show dev" in cmd: return (0, "127.0.0.50", "")
        if "which danted" in cmd or "dpkg-query" in cmd: return (0, "/usr/sbin/danted", "")
        return (0, "", "")

    with patch("src.services.deployment.save_state", new_callable=AsyncMock) as m_save, \
         patch("src.services.deployment.ensure_user", new_callable=AsyncMock) as m_user, \
         patch("src.services.deployment.write_danted_conf", new_callable=AsyncMock) as m_write, \
         patch("src.services.deployment.restart_danted", new_callable=AsyncMock) as m_restart, \
         patch("src.services.deployment.test_user_socks5", new_callable=AsyncMock) as m_test, \
         patch("src.services.deployment.wait_for_port", new_callable=AsyncMock) as m_wait:
        
        m_save.return_value = True
        m_write.return_value = (True, "")
        m_user.return_value = True
        m_restart.return_value = True
        m_wait.return_value = True
        m_test.return_value = (True, "Connected")
        
        entries = [{"subnet": "1.1.1.1/32", "user": "test_user", "password": "pwd"}]
        success, msg, results, restart_output, restart_code = await deploy_configuration(entries, sudo_password="mock_sudo")
        
        assert success is True
        assert len(results) == 1
        assert results[0].user == "test_user"
        assert results[0].ok is True
        
        m_save.assert_called_once_with(entries)
        m_user.assert_called_once()
        m_write.assert_called_once()
        m_restart.assert_called_once() # systemctl restart
        m_test.assert_called_once()

