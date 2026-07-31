from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str
    APP_VERSION: str

    DATABASE_URL: str
    DATABASE_ECHO: bool = False

    REDIS_URL: str

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    OPENAI_API_KEY: str | None = None

    INSTAGRAM_APP_ID: str | None = None
    INSTAGRAM_APP_SECRET: str | None = None
    INSTAGRAM_REDIRECT_URI: str | None = None
    INSTAGRAM_GRAPH_API_VERSION: str = "v21.0"

    TOKEN_ENCRYPTION_KEY: str

    META_ACCESS_TOKEN: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
    )


settings = Settings()
