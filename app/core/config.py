from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Visitor Management System"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    DATABASE_URL: str
    REDIS_URL: str
    MAIN_POS_ID: int = 2

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

settings = Settings()