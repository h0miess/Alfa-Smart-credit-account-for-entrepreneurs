from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from core.logging import request_id

HEADER = b"x-request-id"


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        incoming = dict(scope["headers"]).get(HEADER, b"").decode()[:64]
        current = incoming or uuid4().hex
        token = request_id.set(current)

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).append((HEADER, current.encode()))
            await send(message)

        try:
            await self._app(scope, receive, send_with_id)
        finally:
            request_id.reset(token)
