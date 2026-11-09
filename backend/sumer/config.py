"""الإعدادات من متغيرات البيئة. القيم الحساسة لا توضع في الكود."""

import os
from dataclasses import dataclass, field
from pathlib import Path


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv(
        "SUMER_DATABASE_URL", "postgresql://sumer:sumer_dev@127.0.0.1:5432/sumer"))
    redis_url: str = field(default_factory=lambda: os.getenv("SUMER_REDIS_URL", "redis://127.0.0.1:6379/0"))
    # مفتاح التطبيق: يشفّر أسرار 2FA ويوقّع البصمات المؤقتة. إلزامي بالإنتاج.
    app_secret: str = field(default_factory=lambda: os.getenv("SUMER_APP_SECRET", ""))
    backup_key: str = field(default_factory=lambda: os.getenv("SUMER_BACKUP_KEY", ""))
    env: str = field(default_factory=lambda: os.getenv("SUMER_ENV", "development"))
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("SUMER_DATA_DIR", "./data")).resolve())
    models_dir: Path = field(default_factory=lambda: Path(os.getenv("SUMER_MODELS_DIR", "./models")).resolve())
    # للاختبارات المحلية فقط: يسمح للزاحف بالعناوين الخاصة. ممنوع بالإنتاج.
    allow_private_networks: bool = field(default_factory=lambda: _bool("SUMER_ALLOW_PRIVATE_NETWORKS"))
    trusted_proxy: bool = field(default_factory=lambda: _bool("SUMER_TRUSTED_PROXY"))
    cookie_secure: bool = field(default_factory=lambda: _bool("SUMER_COOKIE_SECURE", True))
    cors_origins: tuple = field(default_factory=lambda: tuple(
        o for o in os.getenv("SUMER_CORS_ORIGINS", "http://localhost:3000").split(",") if o))
    version: str = "1.0.0"

    def validate(self):
        if self.env == "production":
            if len(self.app_secret) < 32:
                raise RuntimeError("SUMER_APP_SECRET يجب أن يكون 32 حرفاً على الأقل بالإنتاج")
            if self.allow_private_networks:
                raise RuntimeError("SUMER_ALLOW_PRIVATE_NETWORKS ممنوع بالإنتاج")
        return self

    @property
    def secret_bytes(self) -> bytes:
        return (self.app_secret or "dev-only-insecure-secret-change-me-now!").encode()


settings = Settings().validate()
