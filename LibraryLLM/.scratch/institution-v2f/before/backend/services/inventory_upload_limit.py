"""Cap multipart bodies before spooling; applies only to the new inventory preview route."""
from starlette.formparsers import MultiPartException
from starlette.responses import JSONResponse


class InventoryUploadLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        if scope['type'] != 'http' or scope.get('method') != 'POST' or not (path.startswith('/libraries/') and path.endswith('/inventory/imports/preview')):
            return await self.app(scope, receive, send)
        limit = 5 * 1024 * 1024 + 128 * 1024
        headers = dict(scope.get('headers', []))
        try:
            length = int(headers.get(b'content-length', b'0'))
        except ValueError:
            length = limit + 1
        if length > limit:
            return await JSONResponse({'detail': 'Inventory upload exceeds the 5 MiB file budget.'}, status_code=413)(scope, receive, send)
        consumed = 0; exceeded = False

        async def bounded_receive():
            nonlocal consumed, exceeded
            message = await receive()
            consumed += len(message.get('body', b''))
            if consumed > limit:
                exceeded = True
                # Starlette closes partial upload temp files for MultiPartException.
                raise MultiPartException('Inventory upload exceeds the 5 MiB file budget.')
            return message

        async def bounded_send(message):
            if exceeded and message['type'] == 'http.response.start':
                message = {**message, 'status': 413}
            await send(message)

        return await self.app(scope, bounded_receive, bounded_send)
