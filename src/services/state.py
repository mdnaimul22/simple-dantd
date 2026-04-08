import json
import os
from src.config import settings
from src.providers import list_proxy_users


async def load_state() -> list[dict]:
    """Load subnet-user-password mappings from state file as raw dicts."""
    try:
        with open(settings.state_file, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


async def save_state(entries: list[dict]) -> bool:
    """Persist subnet-user-password mappings to state file."""
    try:
        os.makedirs(os.path.dirname(settings.state_file), exist_ok=True)
        with open(settings.state_file, "w") as f:
            json.dump(entries, f, indent=2)
        return True
    except Exception as e:
        print(f"[state] save_state error: {e}")
        return False


async def get_proxy_users() -> list[str]:
    """Return the list of system users currently in the danteproxy group.

    Delegates to the user_manager provider — services never touch system
    calls directly.
    """
    return await list_proxy_users()
