from backend.routes.platform import router as platform_router, access_router as platform_access_router
from backend.routes.library_catalogue_experience import router as catalogue_experience_router
from backend.services.library_catalogue_experience import ensure_indexes as ensure_catalogue_experience_indexes
from backend.platform_dependencies import ensure_indexes as ensure_platform_indexes
from backend.services.platform_library_service import ensure_indexes as ensure_platform_library_indexes
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from asyncio import to_thread
from backend.routes.notifications import router as notification_router, admin_router as operations_router, platform_router as platform_operations_router
from backend.services.notification_service import ensure_indexes
from backend.services.notification_worker import DueWorker
from backend.routes.institutions import router as institution_router
from backend.services.institution_repository import ensure_indexes as ensure_institution_indexes
from backend.routes.library_inventory import router as institution_inventory_router
from backend.services.library_catalogue_repository import ensure_indexes as ensure_inventory_indexes
from backend.services.inventory_upload_limit import InventoryUploadLimit
from backend.routes.library_lending import router as library_lending_router
from backend.services.library_lending_journal import ensure_indexes as ensure_lending_indexes, RecoveryRequired
from backend.routes.library_reservations_fees import router as library_v2c_router
from backend.services.library_reservation_service import ensure_indexes as ensure_v2c_indexes
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import JSONResponse


@asynccontextmanager
async def lifespan(app):
    await to_thread(ensure_catalogue_experience_indexes)
    await to_thread(ensure_platform_indexes)
    await to_thread(ensure_platform_library_indexes)
    await to_thread(ensure_institution_indexes)
    await to_thread(ensure_inventory_indexes)
    await to_thread(ensure_lending_indexes)
    await to_thread(ensure_v2c_indexes)
    await to_thread(ensure_indexes)
    await to_thread(ensure_event_indexes)
    worker = DueWorker()
    worker.start()
    try:
        yield
    finally:
        worker.stop()

from backend.routes.auth import router as auth_router
from backend.routes.staff import router as staff_router
from backend.routes.events import router as event_router, staff_router as staff_event_router
from backend.services.event_service import ensure_indexes as ensure_event_indexes
from backend.routes.books import router as books_router
from backend.routes.issues import router as issues_router
from backend.routes.renewals import router as renewal_router, admin_router as renewal_admin_router
from backend.routes.reservations import router as reservations_router
from backend.routes.fines import router as fines_router
from backend.routes.activity import router as activity_router
from backend.routes.reading_list import router as reading_list_router
from backend.routes.know_more import router as know_more_router
from backend.routes.assistant_catalogue import router as assistant_catalogue_router
from backend.routes.knowledge_graph import router as knowledge_graph_router
from backend.routes.knowledge_graph import product_router as related_books_router

# Inventory router exists in the current backend
try:
    from backend.routes.inventory import router as inventory_router
except ImportError:
    inventory_router = None


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="LuminaR Library API",
    version="1.0.0",
    lifespan=lifespan
)
app.include_router(institution_inventory_router)
app.include_router(catalogue_experience_router)
app.include_router(library_lending_router)
app.include_router(library_v2c_router)
app.add_middleware(InventoryUploadLimit)


@app.exception_handler(RecoveryRequired)
async def lending_recovery_required(request, error):
    return JSONResponse(status_code=503, content={'detail': 'RECOVERY_REQUIRED: circulation is blocked until an operator reconciles the durable journal.'})


@app.exception_handler(RequestValidationError)
async def secret_safe_validation(request, error):
    if request.url.path.startswith(('/libraries', '/invitations')):
        # FastAPI's default validation output includes submitted secrets in `input`.
        return JSONResponse(status_code=422, content={'detail': [
            {'loc': list(e['loc']), 'msg': 'Invalid value.' if any(k in e['loc'] for k in ('access_code', 'token')) else e['msg'], 'type': e['type']}
            for e in error.errors()
        ]})
    return await request_validation_exception_handler(request, error)


# ============================================================
# CORS
# ============================================================

# Frontend development origins
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",

    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


app.add_middleware(
    CORSMiddleware,

    allow_origins=ALLOWED_ORIGINS,

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],
)


# ============================================================
# ROUTES
# ============================================================

app.include_router(
    auth_router
)
app.include_router(staff_router)
app.include_router(platform_router)
app.include_router(platform_access_router)
app.include_router(institution_router)
app.include_router(event_router)
app.include_router(staff_event_router)
app.include_router(notification_router)
app.include_router(operations_router)
app.include_router(platform_operations_router)
app.include_router(renewal_router)
app.include_router(renewal_admin_router)

app.include_router(
    books_router
)
app.include_router(know_more_router)
app.include_router(assistant_catalogue_router)
app.include_router(knowledge_graph_router)
app.include_router(related_books_router)

app.include_router(
    issues_router
)

app.include_router(
    reservations_router
)

app.include_router(
    fines_router
)

app.include_router(
    activity_router
)

app.include_router(
    reading_list_router
)


# Inventory
if inventory_router is not None:

    app.include_router(
        inventory_router
    )


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "system": "LuminaR",
        "service": "Core Library API",
        "status": "ready"
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "healthy",
        "system": "LuminaR",
        "service": "core",
        "port": 8002
    }
