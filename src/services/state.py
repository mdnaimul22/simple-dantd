import json
from src.config import settings

async def load_state() -> list[dict]:
    """Load subnet-user-password mappings from state file as raw dicts."""
    try:
        with open(settings.state_file, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

async def save_state(entries: list[dict], sudo_password: str = None) -> bool:
    """Save subnet-user-password mappings to state file."""
    try:
        import os
        os.makedirs(os.path.dirname(settings.state_file), exist_ok=True)
        with open(settings.state_file, 'w') as f:
            json.dump(entries, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving state: {e}")
        return False
