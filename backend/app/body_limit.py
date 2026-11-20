"""Request body size limit, enforced before routing and authentication.

FastAPI reads (and spools) a multipart body before dependencies such as the
login check run, so an unauthenticated client could otherwise stream
gigabytes to an upload route. This pure ASGI middleware refuses bodies over the
limit from Content-Length, and counts streamed bytes for chunked or lying
clients, answering 413 application/problem+json.
"""

import json
import re

UPLOAD_PATH = re.compile(r"^/api/v1/lawyer/cases/[^/]+/documents/?$")
UPLOAD_LIMIT = 21 * 1024 * 1024  # 20 MB file plus multipart overhead
DEFAULT_LIMIT = 2 * 1024 * 1024


def _problem(status: int, title: str, detail: str) -> tuple[dict, dict]:
    body = json.dumps({"type": "about:blank", "title": title, "status": status, "detail": detail}).encode()
    start = {"type": "http.response.start", "status": status,
             "headers": [(b"content-type", b"application/problem+json"),
                         (b"content-length", str(len(body)).encode()), (b"connection", b"close")]}
    return start, {"type": "http.response.body", "body": body}


class BodySizeLimitMiddleware:
    def __init__(self, app, default_limit: int = DEFAULT_LIMIT, upload_limit: int = UPLOAD_LIMIT):
        self.app = app
        self.default_limit = default_limit
        self.upload_limit = upload_limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self.upload_limit if UPLOAD_PATH.match(scope.get("path", "")) else self.default_limit
        declared = dict(scope.get("headers") or []).get(b"content-length")
        if declared is not None:
            try:
                too_large = int(declared) > limit
            except ValueError:
                await self._send(send, 400, "Bad Request", "Invalid Content-Length.")
                return
            if too_large:
                await self._send(send, 413, "Payload Too Large", f"Request body exceeds {limit} bytes.")
                return

        state = {"received": 0, "exceeded": False, "started": False}

        async def limited_receive():
            if state["exceeded"]:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                state["received"] += len(message.get("body", b""))
                if state["received"] > limit:
                    state["exceeded"] = True
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message):
            if state["exceeded"]:
                return  # the 413 below replaces whatever the app tries to send
            if message["type"] == "http.response.start":
                state["started"] = True
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except Exception:
            if not state["exceeded"]:
                raise
        if state["exceeded"] and not state["started"]:
            await self._send(send, 413, "Payload Too Large", f"Request body exceeds {limit} bytes.")

    @staticmethod
    async def _send(send, status: int, title: str, detail: str) -> None:
        start, body = _problem(status, title, detail)
        await send(start)
        await send(body)
