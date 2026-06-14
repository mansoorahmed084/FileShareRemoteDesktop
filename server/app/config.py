from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    HOST: str = "0.0.0.0"
    PORT: int = 8765
    TLS_CERT: str | None = None
    TLS_KEY: str | None = None
    MAX_CONNECTIONS: int = 50
    MAX_MESSAGE_SIZE: int = 131072  # 128KB
    MAX_CHUNK_SIZE: int = 65568  # 64KB + 32-byte header
    MAX_FILE_SIZE: int = 104857600  # 100MB
    PAIR_CODE_EXPIRY: int = 60
    PAIR_MAX_ATTEMPTS: int = 5
    HEARTBEAT_INTERVAL: int = 30
    HEARTBEAT_TIMEOUT: int = 90
    ALLOWED_ORIGINS: str = "*"

    model_config = {"env_prefix": "RD_"}


settings = Settings()
