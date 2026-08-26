#!/usr/bin/env python3
"""Local feedback sidecar for the thesis site.

The rendered site is static, so the in-page note widget and the
Feedback console page talk to this tiny server instead:

    GET  /feedback  -> current FEEDBACK.md (text/markdown)
    POST /feedback  -> append a note; JSON body {page, path, note}
    GET  /          -> plain-text status line

Notes are appended as bullets under "### <page> `<path>`" headers in
the "## Open" section of FEEDBACK.md, merging into an existing header
for the same page. Local-only: binds 127.0.0.1:4211. Started via the
.claude/launch.json entry "thesis-feedback-server", or by hand:

    python scripts/feedback_server.py
"""
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEEDBACK = ROOT / "FEEDBACK.md"
HOST, PORT = "127.0.0.1", 4211
MAX_BODY = 64 * 1024


def append_note(page: str, path: str, note: str) -> None:
    text = FEEDBACK.read_text(encoding="utf-8")
    header = f"### {page}" + (f" `{path}`" if path else "")
    lines = [l.rstrip() for l in note.strip().splitlines() if l.strip()]
    bullet = "\n".join(["- " + lines[0]] + ["  " + l for l in lines[1:]])

    open_m = re.search(r"(?m)^## Open[ \t]*$", text)
    if not open_m:
        raise ValueError("FEEDBACK.md has no '## Open' section")
    open_start = open_m.end()
    applied_m = re.search(r"(?m)^## Applied[ \t]*$", text[open_start:])
    open_end = open_start + (applied_m.start() if applied_m else len(text) - open_start)
    block = text[open_start:open_end]

    existing = re.search(r"(?m)^" + re.escape(header) + r"[ \t]*$", block)
    if existing:
        rest = block[existing.end():]
        nxt = re.search(r"(?m)^### ", rest)
        ins = open_start + existing.end() + (nxt.start() if nxt else len(rest))
        new = text[:ins].rstrip() + "\n" + bullet + "\n\n" + text[ins:].lstrip("\n")
    else:
        ins = open_end
        new = text[:ins].rstrip() + "\n\n" + header + "\n" + bullet + "\n\n" + text[ins:].lstrip("\n")
    FEEDBACK.write_text(new, encoding="utf-8", newline="\n")


class Handler(BaseHTTPRequestHandler):
    def _headers(self, code: int, ctype: str = "text/plain; charset=utf-8", length: int | None = None):
        self.send_response(code)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Type", ctype)
        if length is not None:
            self.send_header("Content-Length", str(length))
        self.end_headers()

    def do_OPTIONS(self):
        self._headers(204)

    def do_GET(self):
        route = self.path.split("?")[0].rstrip("/")
        if route == "":
            body = b"thesis feedback server: running\n"
            self._headers(200, length=len(body))
            self.wfile.write(body)
        elif route == "/feedback":
            try:
                body = FEEDBACK.read_text(encoding="utf-8").encode("utf-8")
            except FileNotFoundError:
                body = b"FEEDBACK.md not found"
                self._headers(500, length=len(body))
                self.wfile.write(body)
                return
            self._headers(200, "text/markdown; charset=utf-8", len(body))
            self.wfile.write(body)
        else:
            self._headers(404, length=0)

    def do_POST(self):
        if self.path.split("?")[0].rstrip("/") != "/feedback":
            self._headers(404, length=0)
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            if n <= 0 or n > MAX_BODY:
                raise ValueError("bad content length")
            data = json.loads(self.rfile.read(n).decode("utf-8"))
            note = (data.get("note") or "").strip()
            page = (data.get("page") or "site").strip() or "site"
            path = (data.get("path") or "").strip()
            if not note:
                raise ValueError("empty note")
            append_note(page, path, note)
        except Exception as exc:
            body = json.dumps({"ok": False, "error": str(exc)}).encode("utf-8")
            self._headers(400, "application/json; charset=utf-8", len(body))
            self.wfile.write(body)
            return
        body = json.dumps({"ok": True}).encode("utf-8")
        self._headers(200, "application/json; charset=utf-8", len(body))
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    print(f"feedback server on http://{HOST}:{PORT} -> {FEEDBACK}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
