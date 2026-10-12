"""Bound only canonical library PDF upload bodies before multipart disk spooling."""
from starlette.formparsers import MultiPartException
from starlette.responses import JSONResponse

MAX_FILE_BYTES = 64 * 1024 * 1024  # Accepted personal document pipeline budget.


class LibraryAssetUploadLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        if (scope['type'] != 'http' or scope.get('method') != 'POST'
                or not path.startswith('/libraries/') or not path.endswith('/assets')):
            return await self.app(scope, receive, send)
        limit = MAX_FILE_BYTES + 128 * 1024
        try:
            length = int(dict(scope.get('headers', [])).get(b'content-length', b'0'))
        except ValueError:
            length = limit + 1
        if length < 0 or length > limit:
            return await JSONResponse({'detail': 'Document exceeds the 64 MiB upload limit.'}, status_code=413)(scope, receive, send)
        consumed = 0
        exceeded = False

        async def bounded_receive():
            nonlocal consumed, exceeded
            message = await receive()
            consumed += len(message.get('body', b''))
            if consumed > limit:
                exceeded = True
                raise MultiPartException('Document exceeds the 64 MiB upload limit.')
            return message

        async def bounded_send(message):
            if exceeded and message['type'] == 'http.response.start':
                message = {**message, 'status': 413}
            await send(message)

        return await self.app(scope, bounded_receive, bounded_send)
