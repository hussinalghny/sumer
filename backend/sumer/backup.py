"""نسخ احتياطي مشفّر (AES-256-GCM) لقاعدة البيانات باستخدام pg_dump.

الاستعادة متعمدة عبر سطر الأوامر فقط (sumer restore)، لأنها تمسح البيانات الحالية.
"""

import base64
import hashlib
import os
import shutil
import subprocess
from datetime import datetime, timezone

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from . import db
from .config import settings

MAGIC = b"SUMERBK1"


def backup_dir():
    d = settings.data_dir / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _key() -> bytes | None:
    if not settings.backup_key:
        return None
    raw = settings.backup_key.encode()
    try:
        k = base64.b64decode(raw, validate=True)
        if len(k) == 32:
            return k
    except Exception:
        pass
    return hashlib.sha256(raw).digest()


def encryption_status() -> dict:
    return {"configured": _key() is not None, "algorithm": "AES-256-GCM",
            "pg_dump_available": shutil.which("pg_dump") is not None}


def run_backup(backup_id: int | None = None, admin_id=None) -> dict:
    key = _key()
    if backup_id is None:
        backup_id = db.fetchone("INSERT INTO backups (file_name, encrypted, status, created_by) VALUES ('', %s, 'running', %s) "
                                "RETURNING id", (key is not None, admin_id))["id"]
    name = f"sumer-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{backup_id}.dump" + (".enc" if key else "")
    path = backup_dir() / name
    try:
        if key is None:
            raise RuntimeError("SUMER_BACKUP_KEY غير مضبوط: النسخ غير المشفّر ممنوع")
        dump = subprocess.run(["pg_dump", "--format=custom", "--no-owner", settings.database_url],
                              capture_output=True, check=True, timeout=3600).stdout
        nonce = os.urandom(12)
        blob = MAGIC + nonce + AESGCM(key).encrypt(nonce, dump, MAGIC)
        path.write_bytes(blob)
        os.chmod(path, 0o600)
        digest = hashlib.sha256(blob).hexdigest()
        db.execute("UPDATE backups SET file_name = %s, bytes = %s, sha256 = %s, status = 'ok', finished_at = now() "
                   "WHERE id = %s", (name, len(blob), digest, backup_id))
        return {"id": backup_id, "file": name, "bytes": len(blob)}
    except Exception as e:
        err = e.stderr.decode()[:500] if isinstance(e, subprocess.CalledProcessError) else str(e)
        db.execute("UPDATE backups SET file_name = %s, status = 'failed', error = %s, finished_at = now() WHERE id = %s",
                   (name, err, backup_id))
        raise


def decrypt_backup(path) -> bytes:
    key = _key()
    blob = open(path, "rb").read()
    if not blob.startswith(MAGIC):
        raise ValueError("ليس ملف نسخة سومر")
    nonce = blob[len(MAGIC):len(MAGIC) + 12]
    return AESGCM(key).decrypt(nonce, blob[len(MAGIC) + 12:], MAGIC)


def verify(path) -> bool:
    try:
        decrypt_backup(path)
        return True
    except Exception:
        return False
