from fastapi import APIRouter
from app.api.v1.endpoints import auth, visits, scan, anomaly, pos, admin, mitra, mobile

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(visits.router, prefix="/api", tags=["Registrasi & Master"])
api_router.include_router(scan.router, prefix="/scan", tags=["Scan"])
api_router.include_router(pos.router, prefix="/api/pos", tags=["Master POS"])
api_router.include_router(anomaly.router, prefix="/anomaly", tags=["Anomaly Detection"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin Dashboard"])
api_router.include_router(scan.router, prefix="/scan", tags=["Scan"])
api_router.include_router(mitra.router, prefix="/api/mitra", tags=["Master Mitra"])
api_router.include_router(mobile.router, prefix="/mobile", tags=["Mobile Security"])