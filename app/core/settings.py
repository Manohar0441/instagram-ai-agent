from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str
    APP_VERSION: str

    OPENAI_API_KEY: str = ""

    DATABASE_URL: str

    REDIS_URL: str

    INSTAGRAM_APP_ID: str = ""

    INSTAGRAM_APP_SECRET: str = ""

    META_ACCESS_TOKEN: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
    )


settings = Settings()