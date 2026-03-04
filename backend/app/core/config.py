from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """集中管理后端运行配置。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Paper Learning Platform API"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = True
    backend_cors_origins: str = "http://localhost:5173"

    postgres_db: str = "paper_learning"
    postgres_user: str = "paper_user"
    postgres_password: str = "paper_password"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/0"

    mineru_api_key: str | None = None
    mineru_base_url: str | None = None
    dashscope_api_key: str | None = None
    local_dev_user_id: str = "local-dev-user"
    local_dev_user_email: str = "dev@paper-learning.local"
    local_dev_user_name: str = "本地开发用户"

    @property
    def sqlalchemy_database_uri(self) -> str:
        """生成 SQLAlchemy 使用的数据库连接串。"""
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        """将逗号分隔的跨域来源转换为列表。"""
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
