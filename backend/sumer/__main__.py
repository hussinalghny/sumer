"""سطر الأوامر:

  python -m sumer migrate
  python -m sumer create-admin --email a@b.iq --name "..." [--role super_admin]   (كلمة المرور من SUMER_ADMIN_PASSWORD أو تُطلب)
  python -m sumer seed https://example.gov.iq/ [...]
  python -m sumer worker [--concurrency 8]
  python -m sumer api [--host 0.0.0.0 --port 8000]
  python -m sumer rebuild-index | refresh-terms | compute-authority | retention
  python -m sumer backup
  python -m sumer restore FILE --yes
"""

import argparse
import asyncio
import getpass
import os
import subprocess
import sys


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sumer")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate")
    a = sub.add_parser("create-admin")
    a.add_argument("--email", required=True)
    a.add_argument("--name", required=True)
    a.add_argument("--role", default="super_admin")
    s = sub.add_parser("seed")
    s.add_argument("urls", nargs="+")
    w = sub.add_parser("worker")
    w.add_argument("--concurrency", type=int)
    w.add_argument("--once", action="store_true")
    p = sub.add_parser("api")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--workers", type=int, default=2)
    for c in ("rebuild-index", "refresh-terms", "compute-authority", "retention", "backup"):
        sub.add_parser(c)
    r = sub.add_parser("restore")
    r.add_argument("file")
    r.add_argument("--yes", action="store_true")
    args = ap.parse_args(argv)

    from . import db
    if args.cmd == "migrate":
        print("طُبّق:", db.migrate() or "لا شيء جديد")
    elif args.cmd == "create-admin":
        from . import auth
        pw = os.getenv("SUMER_ADMIN_PASSWORD") or getpass.getpass("كلمة المرور: ")
        try:
            uid = auth.create_admin(args.email, args.name, pw, args.role)
        except ValueError as e:
            sys.exit(str(e))
        print(f"أُنشئ المشرف رقم {uid}. فعّل التحقق بخطوتين من لوحة التحكم.")
    elif args.cmd == "seed":
        from . import crawler
        with db.pool().connection() as c:
            for u in args.urls:
                print(crawler.add_seed(c, u))
    elif args.cmd == "worker":
        from .crawler import Worker
        asyncio.run(Worker(concurrency=args.concurrency, once=args.once).run())
    elif args.cmd == "api":
        import uvicorn
        uvicorn.run("sumer.app:app", host=args.host, port=args.port, workers=args.workers, access_log=False,
                    proxy_headers=True, server_header=False)
    elif args.cmd == "rebuild-index":
        from .crawler import rebuild_index
        rebuild_index()
    elif args.cmd == "refresh-terms":
        from .crawler import refresh_terms
        refresh_terms()
    elif args.cmd == "compute-authority":
        from .crawler import compute_authority
        compute_authority()
    elif args.cmd == "retention":
        from .crawler import apply_retention
        apply_retention()
    elif args.cmd == "backup":
        from .backup import run_backup
        print(run_backup())
    elif args.cmd == "restore":
        if not args.yes:
            sys.exit("الاستعادة تستبدل قاعدة البيانات الحالية. أعد الأمر مع --yes للتأكيد.")
        from .backup import decrypt_backup
        from .config import settings
        dump = decrypt_backup(args.file)
        subprocess.run(["pg_restore", "--clean", "--if-exists", "--no-owner", "-d", settings.database_url],
                       input=dump, check=True)
        print("تمت الاستعادة.")


if __name__ == "__main__":
    main()
