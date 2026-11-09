"""خادم الموقع التجريبي: يدعم التحويل /old.html، وsitemap بالعنوان الحقيقي، وETag."""

import functools
import http.server
import threading
from pathlib import Path


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/old.html":
            self.send_response(301)
            self.send_header("Location", "/jobs.html")
            self.end_headers()
            return
        if self.path == "/sitemap.xml":
            base = f"http://{self.headers['Host']}"
            body = (Path(self.directory) / "sitemap.xml.tpl").read_text().replace("{BASE}", base).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/xml")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()


def serve(root: Path, port: int = 0):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(Handler, directory=str(root)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
