# app/api/v1/endpoints/scan.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone, timedelta
from app.core.database import get_db
from app.models.visit import Visit, VisitDestination
from app.models.visitor import Visitor, Vehicle, Pos
from app.models.log import ActivityLog
from app.schemas.visit_schema import (
    ScanConfirmRequest, 
    ScanLocationRequest, 
    ScanGateOutRequest
)

router = APIRouter()

# Fungsi bantuan untuk mengecek kedaluwarsa 24 jam
def check_expiration(created_at: datetime):
    wib = timezone(timedelta(hours=7))
    sekarang = datetime.now(wib)
    
    # Pastikan created_at memiliki timezone
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
        
    if (sekarang - created_at) > timedelta(hours=24):
        raise HTTPException(
            status_code=400, 
            detail="Barcode sudah kedaluwarsa (lebih dari 24 jam). Silakan daftar ulang."
        )

# ==========================================
# 1. ENDPOINT PREVIEW SCAN (Munculkan Pop-up)
# ==========================================
@router.get("/preview/{kode_qr}")
async def preview_scan(kode_qr: str, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Visit, Visitor, Vehicle)
        .join(Visitor, Visit.id_pengunjung == Visitor.id_pengunjung)
        .outerjoin(Vehicle, Visit.id_kendaraan == Vehicle.id_kendaraan)
        .options(selectinload(Visit.tujuan))
        .where(Visit.kode_qr == kode_qr)
    )
    result = await db.execute(stmt)
    row = result.first()

    if not row:
        raise HTTPException(status_code=404, detail="Barcode tidak ditemukan atau tidak valid.")
    
    visit, visitor, vehicle = row

    # 1. Cek Kedaluwarsa
    check_expiration(visit.created_at)

    # 2. Cek Status
    if visit.status != "DRAFT":
        raise HTTPException(
            status_code=400, 
            detail=f"Status kunjungan saat ini adalah {visit.status}. Tidak bisa melakukan scan masuk."
        )

    # Ambil data tujuan
    tujuan_info = {"pos": "-", "bertemu": "-", "bagian": "-", "keperluan": "-"}
    if visit.tujuan:
        tuj = visit.tujuan[0]
        pos_stmt = select(Pos).where(Pos.id_pos == tuj.id_pos)
        pos_res = await db.execute(pos_stmt)
        pos_data = pos_res.scalars().first()
        
        tujuan_info = {
            "pos": pos_data.nama_pos if pos_data else "-",
            "bertemu": tuj.orang_yang_ditemui or "-",
            "bagian": "-", 
            "keperluan": tuj.tujuan or "-",
        }

    kendaraan_str = f"{vehicle.jenis_kendaraan} {vehicle.nomor_polisi}" if vehicle else "-"

    return {
        "id_kunjungan": visit.id_kunjungan,
        "kode_qr": visit.kode_qr,
        "nama": visitor.nama,
        "alamat": visitor.alamat or "-",
        "kendaraan": kendaraan_str,
        "jumlah": visit.jumlah_pengunjung,
        "tipe_kunjungan": visit.tipe_kunjungan,
        "tujuan_pos": tujuan_info["pos"],
        "bertemu": tujuan_info["bertemu"],
        "bagian": tujuan_info["bagian"],
        "keperluan": tujuan_info["keperluan"],
        "status_saat_ini": visit.status
    }


# ==========================================
# 2. ENDPOINT KONFIRMASI (Tombol Terima/Tolak)
# ==========================================
@router.post("/confirm")
async def confirm_scan(data: ScanConfirmRequest, db: AsyncSession = Depends(get_db)):
    stmt = select(Visit).where(Visit.kode_qr == data.kode_qr)
    visit = (await db.execute(stmt)).scalars().first()

    if not visit:
        raise HTTPException(status_code=404, detail="Data tidak ditemukan.")

    # 1. Cek Kedaluwarsa
    check_expiration(visit.created_at)

    # 2. Cek Status
    if visit.status != "DRAFT":
        raise HTTPException(status_code=400, detail="Barcode sudah digunakan atau tidak valid.")

    wib = timezone(timedelta(hours=7))
    now_wib = datetime.now(wib)

    if data.aksi == "TERIMA":
        visit.status = "DALAM_KUNJUNGAN"
        visit.check_in_time = now_wib
        log_status = "SUKSES"
        log_ket = "Pengunjung diizinkan masuk oleh Security."
    elif data.aksi == "TOLAK":
        visit.status = "DITOLAK"
        visit.check_in_time = now_wib
        log_status = "GAGAL"
        log_ket = f"Ditolak: {data.alasan_tolak or 'Tidak ada alasan'}"
    else:
        raise HTTPException(status_code=400, detail="Aksi tidak valid (Gunakan TERIMA atau TOLAK)")

    new_log = ActivityLog(
        id_kunjungan=visit.id_kunjungan,
        id_pengguna=1, # TODO: Ganti dengan ID dari JWT
        id_pos=data.id_pos_security,
        jenis_aksi=f"GERBANG_IN_{data.aksi}",
        status_hasil=log_status,
        keterangan=log_ket
    )
    db.add(new_log)
    await db.commit()

    return {"message": f"Kunjungan berhasil di-{data.aksi.lower()}.", "status_baru": visit.status}


# ==========================================
# 3. ENDPOINT SCAN MASUK LOKASI TUJUAN
# ==========================================
@router.post("/location/in")
async def scan_location_in(data: ScanLocationRequest, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Visit)
        .options(selectinload(Visit.tujuan))
        .where(Visit.kode_qr == data.kode_qr)
    )
    visit = (await db.execute(stmt)).scalars().first()

    if not visit:
        raise HTTPException(status_code=404, detail="Barcode tidak valid.")

    # 1. Cek Kedaluwarsa
    check_expiration(visit.created_at)

    # 2. Cek Status
    if visit.status != "DALAM_KUNJUNGAN":
        raise HTTPException(status_code=400, detail=f"Status tidak valid. Saat ini: {visit.status}")

    # 3. Cek Kecocokan POS Tujuan
    target_tujuan = None
    tujuan_sebenarnya = []
    
    for tuj in visit.tujuan:
        pos_stmt = select(Pos).where(Pos.id_pos == tuj.id_pos)
        pos_data = (await db.execute(pos_stmt)).scalars().first()
        nama_pos_asli = pos_data.nama_pos if pos_data else "Lokasi tidak diketahui"
        tujuan_sebenarnya.append(nama_pos_asli)

        if tuj.id_pos == data.id_pos_scanner and tuj.status == "MENUNGGU":
            target_tujuan = tuj
            break

    if not target_tujuan:
        pesan_error = f"SCAN GAGAL: Anda salah lokasi. Tujuan Anda seharusnya di: {', '.join(tujuan_sebenarnya)}."
        raise HTTPException(status_code=400, detail=pesan_error)

    # Eksekusi Masuk Lokasi
    wib = timezone(timedelta(hours=7))
    target_tujuan.status = "DIDALAM"
    target_tujuan.waktu_masuk = datetime.now(wib)
    visit.status = "DALAM_LOKASI"

    log = ActivityLog(
        id_kunjungan=visit.id_kunjungan,
        id_pengguna=1, 
        id_pos=data.id_pos_scanner,
        jenis_aksi="LOKASI_IN",
        status_hasil="SUKSES",
        keterangan="Pengunjung masuk ke lokasi tujuan."
    )
    db.add(log)
    await db.commit()

    return {"message": "Berhasil masuk lokasi tujuan.", "status": visit.status}


# ==========================================
# 4. ENDPOINT SCAN KELUAR LOKASI TUJUAN
# ==========================================
@router.post("/location/out")
async def scan_location_out(data: ScanLocationRequest, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Visit)
        .options(selectinload(Visit.tujuan))
        .where(Visit.kode_qr == data.kode_qr)
    )
    visit = (await db.execute(stmt)).scalars().first()

    if not visit:
        raise HTTPException(status_code=404, detail="Barcode tidak valid.")
        
    # Cek Kedaluwarsa (Opsional: Jika ingin tetap validasi meski sudah di dalam)
    check_expiration(visit.created_at)

    if visit.status != "DALAM_LOKASI":
        raise HTTPException(status_code=400, detail=f"Status tidak valid. Saat ini: {visit.status}")

    target_tujuan = None
    for tuj in visit.tujuan:
        if tuj.id_pos == data.id_pos_scanner and tuj.status == "DIDALAM":
            target_tujuan = tuj
            break

    if not target_tujuan:
        raise HTTPException(status_code=400, detail="Anda belum masuk ke lokasi ini.")

    wib = timezone(timedelta(hours=7))
    target_tujuan.status = "SELESAI"
    target_tujuan.waktu_keluar = datetime.now(wib)
    visit.status = "DALAM_KUNJUNGAN"

    log = ActivityLog(
        id_kunjungan=visit.id_kunjungan,
        id_pengguna=1, 
        id_pos=data.id_pos_scanner,
        jenis_aksi="LOKASI_OUT",
        status_hasil="SUKSES",
        keterangan="Pengunjung keluar dari lokasi tujuan."
    )
    db.add(log)
    await db.commit()

    return {"message": "Berhasil keluar dari lokasi tujuan.", "status": visit.status}


# ==========================================
# 5. ENDPOINT SCAN KELUAR GERBANG UTAMA
# ==========================================
@router.post("/gate/out")
async def scan_gate_out(data: ScanGateOutRequest, db: AsyncSession = Depends(get_db)):
    stmt = select(Visit).where(Visit.kode_qr == data.kode_qr)
    visit = (await db.execute(stmt)).scalars().first()

    if not visit:
        raise HTTPException(status_code=404, detail="Barcode tidak valid.")
    
    # Cek Kedaluwarsa (Opsional: Jika ingin tetap validasi saat keluar)
    check_expiration(visit.created_at)

    if visit.status != "DALAM_KUNJUNGAN":
        raise HTTPException(
            status_code=400, 
            detail=f"Tidak bisa keluar. Pastikan Anda sudah keluar dari lokasi tujuan. Status saat ini: {visit.status}"
        )

    wib = timezone(timedelta(hours=7))
    visit.status = "SELESAI"
    visit.check_out_time = datetime.now(wib)

    log = ActivityLog(
        id_kunjungan=visit.id_kunjungan,
        id_pengguna=1, 
        id_pos=data.id_pos_security,
        jenis_aksi="GERBANG_OUT",
        status_hasil="SUKSES",
        keterangan="Pengunjung keluar dari gerbang utama."
    )
    db.add(log)
    await db.commit()

    return {"message": "Kunjungan selesai. Terima kasih.", "status": visit.status}