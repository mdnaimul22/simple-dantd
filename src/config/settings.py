from pydantic_settings import BaseSettings, SettingsConfigDict

class AppConfig(BaseSettings):
    app_host: str = "127.0.0.50"
    app_port: int = 7000
    dante_ui_secret: str = "change-me-secret"
    admin_user: str = "admin"
    admin_pass: str = "admin"
    
    # Internal variables
    conf: str = "/etc/danted.conf"
    state_file: str = "profiles_data/profiles.json"
    managed_group: str = "danteproxy"
    default_port: int = 1080

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = AppConfig()
