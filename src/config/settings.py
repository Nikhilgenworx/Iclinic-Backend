from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "iClinic-Backend"

    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"

    AUTH_BACKEND_URL: str = "http://localhost:8001"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
