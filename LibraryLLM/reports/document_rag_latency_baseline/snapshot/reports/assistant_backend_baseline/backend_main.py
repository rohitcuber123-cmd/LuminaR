from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.auth import router as auth_router
from backend.routes.staff import router as staff_router
from backend.routes.books import router as books_router
from backend.routes.issues import router as issues_router
from backend.routes.reservations import router as reservations_router
from backend.routes.fines import router as fines_router
from backend.routes.activity import router as activity_router
from backend.routes.reading_list import router as reading_list_router
from backend.routes.know_more import router as know_more_router

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
    version="1.0.0"
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

app.include_router(
    books_router
)
app.include_router(know_more_router)

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
