from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from asyncio import to_thread
from backend.routes.notifications import router as notification_router, admin_router as operations_router
from backend.services.notification_service import ensure_indexes
from backend.services.notification_worker import DueWorker


@asynccontextmanager
async def lifespan(app):
    await to_thread(ensure_indexes)
    worker = DueWorker()
    worker.start()
    try:
        yield
    finally:
        worker.stop()

from backend.routes.auth import router as auth_router
from backend.routes.staff import router as staff_router
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
app.include_router(notification_router)
app.include_router(operations_router)
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
