"""Application configuration."""
import os


class Settings:
    APP_NAME: str = "Stock Simulation Web"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    # Database
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_USER: str = os.getenv("DB_USER", "stock")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "stock123")
    DB_NAME: str = os.getenv("DB_NAME", "stock_web")

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    # JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production-please")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Timezone (China Standard Time UTC+8)
    TIMEZONE: str = "Asia/Shanghai"

    # Scheduler
    CRAWL_HOUR: int = 6
    CRAWL_MINUTE: int = 0
    NAV_UPDATE_HOUR: int = 15
    NAV_UPDATE_MINUTE: int = 5

    # CORS — allow frontend dev server
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


settings = Settings()
