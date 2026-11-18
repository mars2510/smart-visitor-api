# app/main.py
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.api import api_router
from app.core.dependencies import get_current_admin # Import proteksi

app = FastAPI(title=settings.PROJECT_NAME, openapi_url=f"{settings.API_V1_STR}/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount folder static
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup Templates
templates = Jinja2Templates(directory="templates")

# ==========================================
# ROUTE LOGIN (Bisa diakses publik)
# ==========================================
@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="login.html", 
        context={"title": "Login"}
    )

# ==========================================
# ROUTE ADMIN (Diproteksi)
# ==========================================

@app.get("/admin")
async def admin_dashboard(request: Request, admin=Depends(get_current_admin)):
    return templates.TemplateResponse(
        request=request, 
        name="admin_dashboard.html", 
        context={"title": "Dashboard", "user": admin}
    )

@app.get("/admin/anomaly")
async def admin_anomaly(request: Request, admin=Depends(get_current_admin)):
    return templates.TemplateResponse(
        request=request, 
        name="admin_anomaly.html", 
        context={"title": "Anomaly Detection", "user": admin}
    )

@app.get("/admin/visitors")
async def admin_visitors(request: Request, admin=Depends(get_current_admin)):
    return templates.TemplateResponse(
        request=request, 
        name="admin_visitors.html", 
        context={"title": "Data Pengunjung", "user": admin}
    )

@app.get("/admin/logs")
async def admin_logs(request: Request, admin=Depends(get_current_admin)):
    return templates.TemplateResponse(
        request=request, 
        name="admin_logs.html", 
        context={"title": "Log Aktivitas", "user": admin}
    )

@app.get("/admin/pos")
async def admin_pos(request: Request, admin=Depends(get_current_admin)):
    return templates.TemplateResponse(
        request=request, 
        name="admin_pos.html", 
        context={"title": "Manajemen POS", "user": admin}
    )

@app.get("/admin/mitra")
async def admin_mitra(request: Request, admin=Depends(get_current_admin)):
    return templates.TemplateResponse(
        request=request, 
        name="admin_mitra.html", 
        context={"title": "Manajemen Mitra", "user": admin}
    )

@app.get("/admin/users")
async def admin_users(request: Request, admin=Depends(get_current_admin)):
    return templates.TemplateResponse(
        request=request, 
        name="admin_users.html", 
        context={"title": "Manajemen Pengguna", "user": admin}
    )

# Daftarkan API Router
app.include_router(api_router, prefix=settings.API_V1_STR)
