import os
from dataclasses import dataclass, field


def _flag(name: str) -> bool:
    return os.getenv(name, "").lower() in ("1", "true", "yes")


@dataclass(frozen=True)
class Settings:
    redis_url: str = field(default_factory=lambda: os.getenv("SUMERMAIL_REDIS_URL", "redis://localhost:6379/2"))
    # يُستخدم لاشتقاق معرّفات الجلسات في Redis (HMAC) — ليس مفتاح تشفير البيانات
    secret: str = field(default_factory=lambda: os.getenv("SUMERMAIL_SECRET", ""))
    env: str = field(default_factory=lambda: os.getenv("SUMERMAIL_ENV", "production"))
    cookie_secure: bool = field(default_factory=lambda: os.getenv("SUMERMAIL_COOKIE_SECURE", "1") != "0")
    session_idle_s: int = field(default_factory=lambda: int(os.getenv("SUMERMAIL_SESSION_IDLE", str(12 * 3600))))
    session_max_s: int = field(default_factory=lambda: int(os.getenv("SUMERMAIL_SESSION_MAX", str(7 * 24 * 3600))))
    # للاختبارات والتطوير فقط: السماح بخوادم على الشبكة المحلية وبشهادات غير موثّقة
    allow_private: bool = field(default_factory=lambda: _flag("SUMERMAIL_ALLOW_PRIVATE_NETWORKS"))
    insecure_tls: bool = field(default_factory=lambda: _flag("SUMERMAIL_INSECURE_TLS"))
    max_accounts: int = 8
    list_limit: int = 30
    full_fetch_max_bytes: int = 1_500_000
    attachment_max_bytes: int = 25_000_000
    imap_timeout: float = 20.0
    trusted_proxy: bool = field(default_factory=lambda: _flag("SUMERMAIL_TRUSTED_PROXY"))

    def check(self):
        if self.env == "production":
            if len(self.secret) < 32:
                raise RuntimeError("SUMERMAIL_SECRET must be at least 32 characters")
            if self.insecure_tls or self.allow_private:
                raise RuntimeError("Insecure TLS / private networks are for development only")


settings = Settings()
