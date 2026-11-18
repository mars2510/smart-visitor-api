from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.visit_schema import VisitRegisterSchema, VisitLainnyaSchema
from app.services.visit_service import VisitService

router = APIRouter()

@router.post("/Registrasi/submit")
async def submit_registrasi(data: VisitRegisterSchema, db: AsyncSession = Depends(get_db)):
    try:
        service = VisitService(db)
        visit = await service.register_visit(data.model_dump(), is_lainnya=False)
        return {"message": "Registrasi berhasil", "barcode": visit.kode_qr, "id_kunjungan": visit.id_kunjungan, "nama": data.nama, "jenis": data.jenis, "nomor_polisi": data.nomor_polisi}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/kunjungan/lainnya")
async def submit_lainnya(data: VisitLainnyaSchema, db: AsyncSession = Depends(get_db)):
    try:
        service = VisitService(db)
        payload = {"nama": data.nama_lengkap, "keterangan": data.keterangan, "status_kunjungan": data.status, "jenis": data.jenis, "nomor_polisi": data.nomor_polisi}
        visit = await service.register_visit(payload, is_lainnya=True)
        return {"message": "Registrasi berhasil", "barcode": visit.kode_qr, "id_kunjungan": visit.id_kunjungan, "nama_lengkap": data.nama_lengkap, "jenis": data.jenis, "nomor_polisi": data.nomor_polisi}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
