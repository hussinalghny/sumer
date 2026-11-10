"""إعدادات جاهزة لمزودي البريد الشائعين. كلها IMAP عبر TLS على 993."""

PROVIDERS = {
    "gmail": {"name": "Gmail", "imap": ("imap.gmail.com", 993), "smtp": ("smtp.gmail.com", 465),
              "domains": ["gmail.com", "googlemail.com"], "app_password": True,
              "help_ar": "فعّل التحقق بخطوتين بحساب Google، وبعدها سوِّ «كلمة مرور للتطبيقات» واستخدمها هنا.",
              "help_url": "https://myaccount.google.com/apppasswords", "saves_sent": True},
    "yahoo": {"name": "Yahoo", "imap": ("imap.mail.yahoo.com", 993), "smtp": ("smtp.mail.yahoo.com", 465),
              "domains": ["yahoo.com", "ymail.com"], "app_password": True,
              "help_ar": "من إعدادات أمان Yahoo سوِّ «كلمة مرور للتطبيق» واستخدمها هنا.",
              "help_url": "https://login.yahoo.com/account/security", "saves_sent": True},
    "icloud": {"name": "iCloud", "imap": ("imap.mail.me.com", 993), "smtp": ("smtp.mail.me.com", 587),
               "domains": ["icloud.com", "me.com", "mac.com"], "app_password": True,
               "help_ar": "من appleid.apple.com سوِّ «كلمة مرور خاصة بالتطبيق» واستخدمها هنا.",
               "help_url": "https://appleid.apple.com", "saves_sent": False},
    "outlook": {"name": "Outlook", "imap": ("outlook.office365.com", 993), "smtp": ("smtp-mail.outlook.com", 587),
                "domains": ["outlook.com", "hotmail.com", "live.com", "msn.com"], "app_password": False,
                "oauth_only": True,
                "help_ar": "Microsoft تطلب تسجيل دخول OAuth لحسابات Outlook الشخصية. هذا الخيار قيد التطوير.",
                "help_url": "", "saves_sent": True},
    "custom": {"name": "بريد آخر", "imap": ("", 993), "smtp": ("", 465), "domains": [], "app_password": False,
               "help_ar": "بريد الجامعة أو المؤسسة: اسأل قسم تقنية المعلومات عن عنوان خادم IMAP وSMTP.",
               "help_url": "", "saves_sent": False},
}


def detect(email: str) -> str:
    domain = email.rsplit("@", 1)[-1].lower()
    for key, p in PROVIDERS.items():
        if domain in p["domains"]:
            return key
    return "custom"


def public_list() -> list[dict]:
    return [{"id": k, "name": v["name"], "app_password": v["app_password"], "oauth_only": v.get("oauth_only", False),
             "help_ar": v["help_ar"], "help_url": v["help_url"], "imap_host": v["imap"][0], "smtp_host": v["smtp"][0],
             "smtp_port": v["smtp"][1]} for k, v in PROVIDERS.items()]
