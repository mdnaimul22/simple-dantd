import pytest
from unittest.mock import patch
from src.providers.system import check_binary, check_group

def test_check_binary_success():
    with patch("shutil.which") as m:
        m.return_value = "/usr/sbin/danted"
        res, msg = check_binary("danted")
        assert res is True
        assert msg == "/usr/sbin/danted"

def test_check_binary_failure():
    with patch("shutil.which") as m:
        m.return_value = None
        res, msg = check_binary("missingcmd")
        assert res is False
        assert "not found" in msg

def test_check_group_success():
    with patch("grp.getgrnam") as m:
        # getgrnam returns a struct_group in reality, mock just needs to not throw KeyError
        m.return_value = ("danteproxy", "x", 1001, [])
        res, msg = check_group("danteproxy")
        assert res is True
        assert "exists" in msg

def test_check_group_failure():
    with patch("grp.getgrnam") as m:
        m.side_effect = KeyError("missinggroup")
        res, msg = check_group("missinggroup")
        assert res is False
        assert "not found" in msg
