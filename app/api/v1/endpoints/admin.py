import csv
from datetime import date
from io import BytesIO, StringIO

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from starlette.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc
from datetime import datetime, timezone, timedelta
from app.core.database import get_db
from app.models.visit import Visit, VisitDestination
from app.models.log import ActivityLog
from app.models.anomaly import AnomalyResult
from app.models.visitor import Visitor, Pos, Vehicle
from sqlalchemy.orm import selectinload
from app.core.dependencies import get_current_admin
from app.models.user import User

router = APIRouter()


class ExpiredVisitResolution(BaseModel):
    status: str
    catatan: str


def _is_expired(created_at: datetime) -> bool:
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return created_at < datetime.now(timezone.utc) - timedelta(hours=24)


def _visitor_date_bounds(
    period: str,
    date_filter: str | None,
    month_filter: str | None,
) -> tuple[datetime, datetime] | None:
    wib = timezone(timedelta(hours=7))
    today = datetime.now(wib).date()
    try:
        if period == "day":
            selected = date.fromisoformat(date_filter) if date_filter else today
            start_local = datetime.combine(selected, datetime.min.time(), tzinfo=wib)
            end_local = start_local + timedelta(days=1)
        elif period == "month":
            month = month_filter or today.strftime("%Y-%m")
            start_date = date.fromisoformat(f"{month}-01")
            next_month = (
                date(start_date.year + 1, 1, 1)
                if start_date.month == 12
                else date(start_date.year, start_date.month + 1, 1)
            )
            start_local = datetime.combine(start_date, datetime.min.time(), tzinfo=wib)
            end_local = datetime.combine(next_month, datetime.min.time(), tzinfo=wib)
        elif period == "all":
            return None
        else:
            raise HTTPException(status_code=400, detail="Filter periode tidak valid.")
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail="Format tanggal/periode tidak valid.",
        ) from error
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _apply_visitor_filters(stmt, search: str | None, bounds):
    if search:
        search_filter = f"%{search}%"
        stmt = stmt.where(
            (Visitor.nama.ilike(search_filter))
            | (Visitor.telepon.ilike(search_filter))
            | (Visit.kode_qr.ilike(search_filter))
            | (Visitor.alamat.ilike(search_filter))
        )
    if bounds:
        start, end = bounds
        stmt = stmt.where(Visit.created_at >= start, Visit.created_at < end)
    return stmt


def _visitor_query(search: str | None, bounds):
    stmt = (
        select(Visit, Visitor, Vehicle)
        .join(Visitor, Visit.id_pengunjung == Visitor.id_pengunjung)
        .outerjoin(Vehicle, Visit.id_kendaraan == Vehicle.id_kendaraan)
        .options(selectinload(Visit.tujuan))
    )
    return _apply_visitor_filters(stmt, search, bounds)


def _visitor_export_values(visit: Visit, visitor: Visitor, vehicle: Vehicle | None):
    return [
        visitor.nama or "",
        visitor.telepon or "",
        visitor.alamat or "",
        visit.kode_qr or "",
        visit.tipe_kunjungan or "",
        visit.status or "",
        f"{vehicle.jenis_kendaraan or ''} ({vehicle.nomor_polisi or ''})"
        if vehicle
        else "",
        to_wib(visit.created_at),
    ]


# ==========================================
# FUNGSI BANTUAN (HELPER)
# ==========================================
def to_wib(dt: datetime, format_str: str = "%Y-%m-%d %H:%M"):
    """Mengubah waktu UTC (database) ke Waktu Indonesia Barat (WIB / UTC+7)"""
    if not dt:
        return "-"
    # Pastikan datetime memiliki timezone (aware)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    # Konversi ke WIB
    wib_time = dt.astimezone(timezone(timedelta(hours=7)))
    return wib_time.strftime(format_str)


# ==========================================
# 1. ENDPOINT DASHBOARD STATISTIK
# ==========================================
@router.get("/dashboard/stats")
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    wib = timezone(timedelta(hours=7))
    today = datetime.now(wib).date()
    start = datetime.combine(today, datetime.min.time(), tzinfo=wib).astimezone(timezone.utc)
    end = (datetime.combine(today, datetime.min.time(), tzinfo=wib) + timedelta(days=1)).astimezone(timezone.utc)

    stmt_total = select(func.count(Visit.id_kunjungan)).where(
        Visit.check_in_time >= start,
        Visit.check_in_time < end,
    )
    total = (await db.execute(stmt_total)).scalar() or 0

    stmt_in_loc = select(func.count(Visit.id_kunjungan)).where(
        Visit.status == "DALAM_LOKASI",
        Visit.check_in_time >= start,
        Visit.check_in_time < end,
    )
    in_loc = (await db.execute(stmt_in_loc)).scalar() or 0

    stmt_in_visit = select(func.count(Visit.id_kunjungan)).where(
        Visit.status == "DALAM_KUNJUNGAN",
        Visit.check_in_time >= start,
        Visit.check_in_time < end,
    )
    in_visit = (await db.execute(stmt_in_visit)).scalar() or 0

    completed_today = (
        await db.execute(
            select(func.count(Visit.id_kunjungan)).where(
                Visit.status == "SELESAI",
                Visit.check_out_time >= start,
                Visit.check_out_time < end,
            )
        )
    ).scalar() or 0
    rejected_today = (
        await db.execute(
            select(func.count(Visit.id_kunjungan)).where(
                Visit.status == "DITOLAK",
                Visit.check_in_time >= start,
                Visit.check_in_time < end,
            )
        )
    ).scalar() or 0

    current_month = datetime.now().strftime("%Y-%m")
    stmt_anom = select(func.count(AnomalyResult.id)).where(
        AnomalyResult.is_anomaly == True,
        AnomalyResult.analysis_month == current_month
    )
    anom = (await db.execute(stmt_anom)).scalar() or 0

    return {
        "total_today": total,
        "in_location": in_loc,
        "in_visit": in_visit,
        "completed_today": completed_today,
        "rejected_today": rejected_today,
        "anomaly_month": anom
    }


# ==========================================
# 2. ENDPOINT LIVE MONITORING
# ==========================================
@router.get("/dashboard/live-monitoring")
async def get_live_monitoring(db: AsyncSession = Depends(get_db)):
    # Ambil kunjungan yang statusnya DRAFT, DALAM_KUNJUNGAN, atau DALAM_LOKASI
    stmt = (
        select(Visit, Visitor, Pos)
        .join(Visitor, Visit.id_pengunjung == Visitor.id_pengunjung)
        # Gunakan outerjoin agar data DRAFT yang belum punya tujuan tetap muncul
        .outerjoin(VisitDestination, Visit.id_kunjungan == VisitDestination.id_kunjungan)
        .outerjoin(Pos, VisitDestination.id_pos == Pos.id_pos)
        .where(Visit.status.in_(["DRAFT", "DALAM_KUNJUNGAN", "DALAM_LOKASI"]))
        .order_by(desc(Visit.created_at))
        .limit(50)
    )
    
    result = await db.execute(stmt)
    rows = result.all()

    data = []
    for visit, visitor, pos in rows:
        # Ambil nama POS, jika tidak ada tampilkan strip
        nama_pos = pos.nama_pos if pos else "-"
        
        # Format Waktu Masuk (Gunakan check_in_time, jika kosong "-")
        waktu_masuk = to_wib(visit.check_in_time, "%H:%M") if visit.check_in_time else "-"

        is_expired = _is_expired(visit.created_at)
        data.append({
            "kode": visit.kode_qr,
            "nama": visitor.nama,
            "tujuan": nama_pos,
            "waktu": waktu_masuk,
            "status": visit.status
        })
    return data
async def get_live_monitoring(db: AsyncSession = Depends(get_db)):
    # Ambil kunjungan yang statusnya belum SELESAI
    stmt = (
        select(Visit, Visitor, Pos)
        .join(Visitor, Visit.id_pengunjung == Visitor.id_pengunjung)
        .outerjoin(VisitDestination, Visit.id_kunjungan == VisitDestination.id_kunjungan)
        .outerjoin(Pos, VisitDestination.id_pos == Pos.id_pos)
        .where(Visit.status.in_(["DRAFT", "DALAM_KUNJUNGAN", "DALAM_LOKASI"]))
        .order_by(desc(Visit.created_at))
        .limit(50)
    )
    
    result = await db.execute(stmt)
    rows = result.all()

    data = []
    for visit, visitor, pos in rows:
        # Perbaikan: Ambil nama_pos dengan aman
        nama_pos = "Tujuan Belum Diisi"
        if pos is not None:
            nama_pos = pos.nama_pos
        
        # Perbaikan: Format waktu yang aman
        waktu_masuk = "Belum Masuk"
        if visit.check_in_time:
            waktu_masuk = to_wib(visit.check_in_time, "%H:%M")

        data.append({
            "kode": visit.kode_qr,
            "nama": visitor.nama,
            "tujuan": nama_pos,
            "waktu": waktu_masuk,
            "status": visit.status
        })
    return data
    # Ambil kunjungan yang statusnya belum SELESAI
    stmt = (
        select(Visit, Visitor, Pos)
        .join(Visitor, Visit.id_pengunjung == Visitor.id_pengunjung)
        .outerjoin(VisitDestination, Visit.id_kunjungan == VisitDestination.id_kunjungan)
        .outerjoin(Pos, VisitDestination.id_pos == Pos.id_pos)
        .where(Visit.status.in_(["DRAFT", "DALAM_KUNJUNGAN", "DALAM_LOKASI"]))
        .order_by(desc(Visit.created_at))
        .limit(50)
    )
    
    result = await db.execute(stmt)
    rows = result.all()

    data = []
    for visit, visitor, pos in rows:
        nama_pos = pos.nama_pos if pos else "Tujuan Belum Diisi"
        
        # Ambil jam masuk gerbang (format HH:MM)
        waktu_masuk = to_wib(visit.check_in_time, "%H:%M") if visit.check_in_time else "Belum Masuk"
        
        data.append({
            "kode": visit.kode_qr,
            "nama": visitor.nama,
            "tujuan": nama_pos,
            "waktu": waktu_masuk,
            "status": visit.status
        })
    return data


# ==========================================
# 3. ENDPOINT DATA PENGUNJUNG (Riwayat & Pagination)
# ==========================================
@router.get("/visitors")
async def get_all_visitors(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: str = Query(None),
    period: str = Query("all", pattern="^(day|month|all)$"),
    date_filter: str | None = Query(None),
    month_filter: str | None = Query(None),
    db: AsyncSession = Depends(get_db)
):
    offset = (page - 1) * limit
    bounds = _visitor_date_bounds(period, date_filter, month_filter)
    stmt = _visitor_query(search, bounds)
    count_stmt = _apply_visitor_filters(
        select(func.count(Visit.id_kunjungan)).join(
            Visitor, Visit.id_pengunjung == Visitor.id_pengunjung
        ),
        search,
        bounds,
    )

    # Eksekusi Count
    total_data = (await db.execute(count_stmt)).scalar()
    total_pages = (total_data + limit - 1) // limit if total_data > 0 else 1

    # Eksekusi Data dengan Pagination & Urutkan dari yang terbaru
    stmt = stmt.order_by(desc(Visit.created_at)).offset(offset).limit(limit)
    result = await db.execute(stmt)
    rows = result.all()

    data = []
    for visit, visitor, vehicle in rows:
        # Data Tujuan (tetap dipertahankan untuk info tambahan)
        tujuan_info = "-"
        if visit.tujuan:
            tujuan_info = visit.tujuan[0].tujuan or "-"

        # Susun data kendaraan
        info_kendaraan = "-"
        if vehicle:
            info_kendaraan = f"{vehicle.jenis_kendaraan} ({vehicle.nomor_polisi})"

        is_expired = _is_expired(visit.created_at)
        data.append({
            "id_kunjungan": visit.id_kunjungan,
            "kode_qr": visit.kode_qr,
            "nama": visitor.nama,
            "telepon": visitor.telepon,
            "alamat": visitor.alamat or "-",          # <-- Tambah Alamat
            "kendaraan": info_kendaraan,              # <-- Tambah Kendaraan
            "tipe_kunjungan": visit.tipe_kunjungan,   # <-- Tipe Kunjungan
            "status": visit.status,
            "waktu_daftar": to_wib(visit.created_at),
            "can_resolve_expired": is_expired and visit.status in {
                "DRAFT",
                "DALAM_KUNJUNGAN",
                "DALAM_LOKASI",
            },
        })

    return {
        "data": data,
        "meta": {
            "page": page,
            "limit": limit,
            "total_data": total_data,
            "total_pages": total_pages
        }
    }


@router.get("/visitors/export")
async def export_visitors(
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
    search: str | None = Query(None),
    period: str = Query("day", pattern="^(day|month|all)$"),
    date_filter: str | None = Query(None),
    month_filter: str | None = Query(None),
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    bounds = _visitor_date_bounds(period, date_filter, month_filter)
    rows = (await db.execute(_visitor_query(search, bounds).order_by(desc(Visit.created_at)))).all()
    headers = [
        "Nama",
        "Telepon",
        "Alamat / PT",
        "Barcode",
        "Tipe Kunjungan",
        "Status",
        "Kendaraan",
        "Waktu Daftar (WIB)",
    ]
    values = [_visitor_export_values(visit, visitor, vehicle) for visit, visitor, vehicle in rows]
    values = [
        [
            f"'{value}"
            if isinstance(value, str) and value.startswith(("=", "+", "-", "@"))
            else value
            for value in row
        ]
        for row in values
    ]
    period_label = (
        date_filter
        if period == "day" and date_filter
        else month_filter
        if period == "month" and month_filter
        else period
    )
    filename = f"data-pengunjung-{period_label}"

    if format == "csv":
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows(values)
        return Response(
            content="\ufeff" + output.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
        )

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Pengunjung"
    worksheet.append(headers)
    for cell in worksheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1769AA")
        cell.alignment = Alignment(horizontal="center")
    for row in values:
        worksheet.append(row)
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions
    for column, width in {
        "A": 28,
        "B": 18,
        "C": 34,
        "D": 18,
        "E": 20,
        "F": 20,
        "G": 28,
        "H": 22,
    }.items():
        worksheet.column_dimensions[column].width = width

    output = BytesIO()
    workbook.save(output)
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'},
    )


@router.post("/visitors/{visit_id}/resolve-expired")
async def resolve_expired_visit(
    visit_id: str,
    data: ExpiredVisitResolution,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    resolution = data.status.strip().upper()
    note = data.catatan.strip()
    if resolution not in {"HILANG", "SELESAI"}:
        raise HTTPException(status_code=400, detail="Status harus HILANG atau SELESAI.")
    if not note:
        raise HTTPException(status_code=400, detail="Catatan admin wajib diisi.")

    visit = await db.get(Visit, visit_id)
    if visit is None:
        raise HTTPException(status_code=404, detail="Kunjungan tidak ditemukan.")
    if not _is_expired(visit.created_at):
        raise HTTPException(status_code=409, detail="Barcode kunjungan belum kedaluwarsa.")
    if visit.status not in {"DRAFT", "DALAM_KUNJUNGAN", "DALAM_LOKASI"}:
        raise HTTPException(status_code=409, detail="Status kunjungan sudah tidak aktif.")

    visit.status = resolution
    visit.check_out_time = datetime.now(timezone(timedelta(hours=7)))
    db.add(
        ActivityLog(
            id_kunjungan=visit.id_kunjungan,
            id_pengguna=admin.id_pengguna,
            id_pos=admin.id_pos,
            jenis_aksi=f"EXPIRED_{resolution}",
            status_hasil="SUKSES",
            keterangan=f"Dicatat oleh admin {admin.nama}. Catatan: {note}",
        )
    )
    await db.commit()
    return {"status": "success", "new_status": visit.status}


# ==========================================
# 4. ENDPOINT HASIL ANOMALI (Untuk halaman Deteksi Anomali)
# ==========================================
@router.get("/anomalies")
async def get_anomalies(month: str, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(AnomalyResult, Visit, Visitor)
        .join(Visit, AnomalyResult.id_kunjungan == Visit.id_kunjungan)
        .join(Visitor, Visit.id_pengunjung == Visitor.id_pengunjung)
        .where(AnomalyResult.analysis_month == month)
        .order_by(AnomalyResult.anomaly_score.asc()) # Skor terendah (paling anomali) di atas
    )
    result = await db.execute(stmt)
    rows = result.all()

    data = []
    for anomaly, visit, visitor in rows:
        data.append({
            "kode": visit.kode_qr,
            "nama": visitor.nama,
            "skor": round(anomaly.anomaly_score, 2),
            "is_anomaly": anomaly.is_anomaly
        })
    return data



@router.get("/mobile/visitors")
async def get_mobile_visitors_data(
    date_filter: str = Query(None, description="Format: YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint khusus Mobile App.
    Mengembalikan data summary (angka di atas) dan list pengunjung yang dikelompokkan.
    """
    # 1. Tentukan filter tanggal (default: hari ini WIB)
    wib = timezone(timedelta(hours=7))
    if date_filter:
        target_date = datetime.strptime(date_filter, "%Y-%m-%d").date()
    else:
        target_date = datetime.now(wib).date()

    # 2. Ambil semua data kunjungan pada tanggal tersebut (Join dengan Visitor & Vehicle)
    # Kita gunakan filter berdasarkan check_in_time atau created_at jika belum check-in
    # Untuk simplifikasi, kita filter berdasarkan created_at pada tanggal tersebut
    stmt = (
        select(Visit, Visitor, Vehicle)
        .join(Visitor, Visit.id_pengunjung == Visitor.id_pengunjung)
        .outerjoin(Vehicle, Visit.id_kendaraan == Vehicle.id_kendaraan)
        .options(selectinload(Visit.tujuan))
        .where(func.date(Visit.created_at) == target_date)
        .order_by(desc(Visit.created_at))
    )
    
    result = await db.execute(stmt)
    rows = result.all()

    # 3. Siapkan variabel untuk menampung data & summary
    summary = {
        "all": len(rows),
        "area_kompleks": 0,
        "tujuan": 0,
        "selesai": 0,
        "tolak": 0
    }
    
    grouped_data = {
        "dalam_kunjungan": [], # Status DALAM_KUNJUNGAN
        "dalam_pos_tujuan": [], # Status DALAM_LOKASI
        "ditolak": [],          # Status DITOLAK
        "selesai": []           # Status SELESAI
    }

    for visit, visitor, vehicle in rows:
        # Hitung Summary
        if visit.status == "DALAM_KUNJUNGAN": summary["area_kompleks"] += 1
        elif visit.status == "DALAM_LOKASI": summary["tujuan"] += 1
        elif visit.status == "SELESAI": summary["selesai"] += 1
        elif visit.status == "DITOLAK": summary["tolak"] += 1

        # Format Data
        info_kendaraan = f"{vehicle.jenis_kendaraan} {vehicle.nomor_polisi}" if vehicle else "-"
        
        # Ambil tujuan pertama
        tujuan_str = "-"
        if visit.tujuan:
            tuj = visit.tujuan[0]
            # Gabungkan nama POS (jika ada) dan nama perusahaan (asumsi disimpan di 'tujuan')
            # Karena kita belum join ke tabel Pos di query ini, kita gunakan nama dari field 'tujuan' saja
            tujuan_str = tuj.tujuan or "-"
            
        item_data = {
            "id_kunjungan": visit.id_kunjungan,
            "nama": visitor.nama,
            "alamat": visitor.alamat or "-",
            "kendaraan": info_kendaraan,
            "tujuan": tujuan_str,
            "status": visit.status,
            "waktu": to_wib(visit.check_in_time, "%H:%M") if visit.check_in_time else "-"
        }

        # Masukkan ke grup yang sesuai
        if visit.status == "DALAM_KUNJUNGAN":
            grouped_data["dalam_kunjungan"].append(item_data)
        elif visit.status == "DALAM_LOKASI":
            grouped_data["dalam_pos_tujuan"].append(item_data)
        elif visit.status == "DITOLAK":
            grouped_data["ditolak"].append(item_data)
        elif visit.status == "SELESAI":
            grouped_data["selesai"].append(item_data)

    # 4. Return Response
    return {
        "tanggal": target_date.strftime("%Y-%m-%d"),
        "summary": summary,
        "data": grouped_data
    }


# LOG AKTIVITAS 
from app.models.log import ActivityLog
from app.models.user import User
from app.models.visitor import Pos, Visitor


@router.get("/logs")
async def get_activity_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str = Query(None, description="Cari Nama Pengunjung / Kode QR / Nama Security"),
    aksi: str = Query(None, description="Filter Jenis Aksi (misal: LOKASI_IN)"),
    status: str = Query(None, description="Filter Status (SUKSES / GAGAL)"),
    db: AsyncSession = Depends(get_db)
):
    offset = (page - 1) * limit

    # Base Query: Join Log dengan Visit, Visitor, User (Security), dan Pos
    stmt = (
        select(ActivityLog, Visit, Visitor, User, Pos)
        .join(Visit, ActivityLog.id_kunjungan == Visit.id_kunjungan)
        .join(Visitor, Visit.id_pengunjung == Visitor.id_pengunjung)
        .join(User, ActivityLog.id_pengguna == User.id_pengguna)
        .outerjoin(Pos, ActivityLog.id_pos == Pos.id_pos) # Outerjoin jika Pos dihapus
    )
    
    # Filter Pencarian
    if search:
        search_filter = f"%{search}%"
        stmt = stmt.where(
            (Visitor.nama.ilike(search_filter)) | 
            (Visit.kode_qr.ilike(search_filter)) |
            (User.nama.ilike(search_filter))
        )

    # Filter Aksi & Status
    if aksi:
        stmt = stmt.where(ActivityLog.jenis_aksi == aksi)
    if status:
        stmt = stmt.where(ActivityLog.status_hasil == status)

    # Paginate by visit so one visitor's activity is never split across pages.
    matching_visits = (
        select(
            Visit.id_kunjungan,
            func.max(ActivityLog.waktu_scan).label("last_activity"),
        )
        .select_from(ActivityLog)
        .join(Visit, ActivityLog.id_kunjungan == Visit.id_kunjungan)
        .join(Visitor, Visit.id_pengunjung == Visitor.id_pengunjung)
        .join(User, ActivityLog.id_pengguna == User.id_pengguna)
        .group_by(Visit.id_kunjungan)
    )
    if stmt.whereclause is not None:
        matching_visits = matching_visits.where(stmt.whereclause)
    total_data = (
        await db.execute(
            select(func.count()).select_from(matching_visits.subquery())
        )
    ).scalar() or 0
    total_pages = (total_data + limit - 1) // limit if total_data > 0 else 1

    page_visit_ids = (
        await db.execute(
            matching_visits
            .order_by(desc("last_activity"))
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()
    stmt = (
        stmt.where(ActivityLog.id_kunjungan.in_(page_visit_ids))
        .order_by(desc(ActivityLog.waktu_scan))
    )
    result = await db.execute(stmt)
    rows = result.all()

    data = []
    for log, visit, visitor, user, pos in rows:
        data.append({
            "id_log": log.id_log,
            "waktu_scan": to_wib(log.waktu_scan),
            "nama_pengunjung": visitor.nama,
            "kode_qr": visit.kode_qr,
            "security": user.nama,
            "lokasi_pos": pos.nama_pos if pos else "-",
            "jenis_aksi": log.jenis_aksi,
            "status_hasil": log.status_hasil,
            "keterangan": log.keterangan or "-"
        })

    return {
        "data": data,
        "meta": {
            "page": page,
            "limit": limit,
            "total_data": total_data,
            "total_pages": total_pages
        }
    }


# app/api/v1/endpoints/admin.py
from sqlalchemy import func, desc
from app.models.visitor import Visitor, Vehicle, Pos
from app.models.visit import Visit, VisitDestination

@router.get("/mobile/visitors")
async def get_mobile_visitors_data(
    date_filter: str = Query(None, description="Format: YYYY-MM-DD (default: hari ini)"),
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint khusus Mobile App untuk halaman Data Pengunjung.
    Mengembalikan summary (angka di atas) dan list dikelompokkan berdasarkan status.
    """
    # 1. Tentukan tanggal (Default: hari ini WIB)
    wib = timezone(timedelta(hours=7))
    if date_filter:
        target_date = datetime.strptime(date_filter, "%Y-%m-%d").date()
    else:
        target_date = datetime.now(wib).date()

    # 2. Query Data (Join dengan Visitor dan Vehicle)
    stmt = (
        select(Visit, Visitor, Vehicle)
        .join(Visitor, Visit.id_pengunjung == Visitor.id_pengunjung)
        .outerjoin(Vehicle, Visit.id_kendaraan == Vehicle.id_kendaraan)
        .options(selectinload(Visit.tujuan))
        .where(func.date(Visit.created_at) == target_date)
        .order_by(desc(Visit.created_at))
    )
    
    result = await db.execute(stmt)
    rows = result.all()

    # 3. Inisialisasi Summary
    summary = {
        "all": len(rows),
        "area_kompleks": 0, # DALAM_KUNJUNGAN
        "tujuan": 0,        # DALAM_LOKASI
        "selesai": 0,       # SELESAI
        "tolak": 0          # DITOLAK
    }
    
    # 4. Inisialisasi Grouping (Sesuai UI Mobile)
    grouped_data = {
        "dalam_kunjungan": [], 
        "dalam_pos_tujuan": [], 
        "ditolak": [],          
        "selesai": []           
    }

    # 5. Loop Data & Masukkan ke Grup
    for visit, visitor, vehicle in rows:
        # -- Hitung Summary --
        if visit.status == "DALAM_KUNJUNGAN": summary["area_kompleks"] += 1
        elif visit.status == "DALAM_LOKASI": summary["tujuan"] += 1
        elif visit.status == "SELESAI": summary["selesai"] += 1
        elif visit.status == "DITOLAK": summary["tolak"] += 1

        # -- Format Data --
        info_kendaraan = f"{vehicle.jenis_kendaraan} {vehicle.nomor_polisi}" if vehicle else "-"
        
        # Ambil Tujuan (POS)
        tujuan_str = "-"
        if visit.tujuan:
            tuj = visit.tujuan[0]
            # Ambil nama POS dari tabel Pos (bisa juga di-join langsung di query utama)
            pos_stmt = select(Pos).where(Pos.id_pos == tuj.id_pos)
            pos_data = (await db.execute(pos_stmt)).scalars().first()
            
            if pos_data:
                tujuan_str = f"{pos_data.nama_pos}"
            if tuj.tujuan:
                tujuan_str += f" - {tuj.tujuan}"

        item_data = {
            "id_kunjungan": visit.id_kunjungan,
            "nama": visitor.nama,
            "alamat": visitor.alamat or "-",
            "kendaraan": info_kendaraan,
            "tujuan": tujuan_str,
            "status": visit.status,
            # Tambahan info waktu jika dibutuhkan mobile
            "waktu_masuk": to_wib(visit.check_in_time, "%H:%M") if visit.check_in_time else "-"
        }

        # -- Masukkan ke Grup --
                # Anggap DRAFT dan DALAM_KUNJUNGAN sebagai area kompleks/antrian
        if visit.status in ["DRAFT", "DALAM_KUNJUNGAN"]:
            grouped_data["dalam_kunjungan"].append(item_data)
        elif visit.status == "DALAM_LOKASI":
            grouped_data["dalam_pos_tujuan"].append(item_data)
        elif visit.status == "DITOLAK":
            grouped_data["ditolak"].append(item_data)
        elif visit.status == "SELESAI":
            grouped_data["selesai"].append(item_data)

    # 6. Return Response
    return {
        "tanggal": target_date.strftime("%Y-%m-%d"),
        "summary": summary,
        "data": grouped_data
    }