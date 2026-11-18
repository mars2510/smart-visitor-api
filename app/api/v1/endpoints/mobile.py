from datetime import datetime, time, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.log import ActivityLog
from app.models.user import User
from app.models.visit import Visit, VisitDestination
from app.models.visitor import Pos, Vehicle, Visitor
from app.api.v1.endpoints.scan import check_expiration

router = APIRouter()
WIB = timezone(timedelta(hours=7))
MAIN_POS_ID = settings.MAIN_POS_ID


class BarcodeRequest(BaseModel):
    barcode: str


class StatusRequest(BarcodeRequest):
    action: str
    destination_id: Optional[int] = None
    alasan_selesai: Optional[str] = None


def _require_security_pos(user: User) -> int:
    if user.peran not in {"security", "admin"} or user.id_pos is None:
        raise HTTPException(
            status_code=403,
            detail="Akun belum memiliki akses security dan penugasan pos.",
        )
    return user.id_pos


async def _load_visit(db: AsyncSession, barcode: str):
    result = await db.execute(
        select(Visit, Visitor, Vehicle)
        .join(Visitor, Visit.id_pengunjung == Visitor.id_pengunjung)
        .outerjoin(Vehicle, Visit.id_kendaraan == Vehicle.id_kendaraan)
        .options(selectinload(Visit.tujuan), selectinload(Visit.logs))
        .where(Visit.kode_qr == barcode)
    )
    return result.first()


async def _pos_names(db: AsyncSession, destinations: list[VisitDestination]):
    pos_ids = {destination.id_pos for destination in destinations if destination.id_pos}
    if not pos_ids:
        return {}
    result = await db.execute(select(Pos).where(Pos.id_pos.in_(pos_ids)))
    return {pos.id_pos: pos.nama_pos for pos in result.scalars().all()}


def _mobile_status(status: str) -> str:
    return {
        "DRAFT": "masuk",
        "DALAM_KUNJUNGAN": "dalam kunjungan",
        "DALAM_LOKASI": "dalam tujuan",
        "DITOLAK": "data ditolak",
        "SELESAI": "selesai",
        "HILANG": "hilang",
    }.get(status, (status or "").lower())


def _destination_status(destination: VisitDestination) -> str:
    return (destination.status or "").upper()


def _visitor_payload(visit: Visit, visitor: Visitor, vehicle: Optional[Vehicle], pos_names):
    destinations = sorted(visit.tujuan, key=lambda item: item.id_tujuan)
    completion_logs = [
        log for log in visit.logs if log.jenis_aksi == "SELESAI_MANUAL_POS1"
    ]
    completion_reason = completion_logs[-1].keterangan if completion_logs else None
    return {
        "id": visitor.id_pengunjung,
        "id_kunjungan": visit.id_kunjungan,
        "nama": visitor.nama,
        "nama_lainnya": visit.nama_lainnya,
        "telepon": visitor.telepon,
        "status_kunjungan": visit.tipe_kunjungan or "Tamu Umum",
        "status": _mobile_status(visit.status),
        "barcode": visit.kode_qr,
        "waktu_masuk": visit.created_at.isoformat() if visit.created_at else None,
        "waktu_keluar": visit.check_out_time.isoformat() if visit.check_out_time else None,
        "jenis_kendaraan": vehicle.jenis_kendaraan if vehicle else None,
        "nomor_kendaraan": vehicle.nomor_polisi if vehicle else None,
        "alamat_pt": visitor.alamat,
        "jumlah_pengunjung": visit.jumlah_pengunjung or 1,
        "keterangan": visit.catatan,
        "alasan_selesai": completion_reason,
        "tujuan": [pos_names.get(item.id_pos, "") for item in destinations],
        "destinations": [
            {
                "id": item.id_tujuan,
                "pos_id": item.id_pos,
                "pos": pos_names.get(item.id_pos, ""),
                "bertemu_dengan": item.orang_yang_ditemui,
                "keperluan": item.tujuan,
                "status": {
                    "MENUNGGU": "menunggu",
                    "DIDALAM": "dalam tujuan",
                    "SELESAI": "selesai",
                }.get(_destination_status(item), (item.status or "").lower()),
            }
            for item in destinations
        ],
    }


def _add_log(
    db: AsyncSession,
    visit: Visit,
    user: User,
    pos_id: int,
    action: str,
    result: str,
    detail: str,
):
    db.add(
        ActivityLog(
            id_kunjungan=visit.id_kunjungan,
            id_pengguna=user.id_pengguna,
            id_pos=pos_id,
            jenis_aksi=action,
            status_hasil=result,
            keterangan=detail,
        )
    )


@router.get("/pos")
async def get_positions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Pos).order_by(Pos.id_pos))
    return {
        "status": "success",
        "data": [
            {"id": pos.id_pos, "nama": pos.nama_pos}
            for pos in result.scalars().all()
        ],
    }


@router.get("/visitors")
async def get_today_visitors(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_security_pos(user)
    now = datetime.now(WIB)
    start = datetime.combine(now.date(), time.min, tzinfo=WIB)
    expiration_cutoff = now - timedelta(hours=24)
    result = await db.execute(
        select(Visit, Visitor, Vehicle)
        .join(Visitor, Visit.id_pengunjung == Visitor.id_pengunjung)
        .outerjoin(Vehicle, Visit.id_kendaraan == Vehicle.id_kendaraan)
        .options(selectinload(Visit.tujuan), selectinload(Visit.logs))
        .where(
            and_(
                Visit.created_at >= expiration_cutoff,
                or_(
                    Visit.created_at >= start,
                    Visit.status.in_(["DRAFT", "DALAM_KUNJUNGAN", "DALAM_LOKASI"]),
                ),
            )
        )
        .order_by(Visit.created_at.desc())
    )
    rows = result.all()
    destinations = [destination for visit, _, _ in rows for destination in visit.tujuan]
    names = await _pos_names(db, destinations)
    return {
        "status": "success",
        "data": [
            _visitor_payload(visit, visitor, vehicle, names)
            for visit, visitor, vehicle in rows
        ],
    }


@router.post("/scans")
async def preview_mobile_scan(
    data: BarcodeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pos_id = _require_security_pos(user)
    row = await _load_visit(db, data.barcode.strip())
    if not row:
        raise HTTPException(status_code=404, detail="Pengunjung tidak ditemukan")
    visit, visitor, vehicle = row
    names = await _pos_names(db, visit.tujuan)
    now = datetime.now(WIB)
    try:
        check_expiration(visit.created_at)
        if pos_id == MAIN_POS_ID:
            if visit.status not in {"DRAFT", "DALAM_KUNJUNGAN"}:
                raise HTTPException(
                    status_code=409,
                    detail=f"Status kunjungan tidak dapat diproses di Pos 1: {visit.status}",
                )
        elif visit.status == "DALAM_KUNJUNGAN":
            unfinished = [
                item for item in sorted(visit.tujuan, key=lambda item: item.id_tujuan)
                if _destination_status(item) != "SELESAI"
            ]
            active = [
                item for item in visit.tujuan
                if _destination_status(item) == "DIDALAM"
            ]
            if active or not unfinished or unfinished[0].id_pos != pos_id:
                correct = (
                    names.get(active[0].id_pos, "") if active
                    else names.get(unfinished[0].id_pos, "") if unfinished
                    else "Pos 1"
                )
                raise HTTPException(
                    status_code=409,
                    detail=f"Pos tujuan tidak sesuai. Pengunjung harus menuju: {correct}",
                )
            target = unfinished[0]
            if _destination_status(target) != "MENUNGGU":
                raise HTTPException(
                    status_code=409,
                    detail="Tujuan tidak berada dalam status yang dapat diproses.",
                )
            target.status = "DIDALAM"
            target.waktu_masuk = now
            visit.status = "DALAM_LOKASI"
            _add_log(
                db,
                visit,
                user,
                pos_id,
                "LOKASI_IN",
                "SUKSES",
                "Pengunjung masuk ke lokasi tujuan melalui validasi barcode.",
            )
        elif visit.status == "DALAM_LOKASI":
            target = next(
                (
                    item
                    for item in visit.tujuan
                    if item.id_pos == pos_id
                    and _destination_status(item) == "DIDALAM"
                ),
                None,
            )
            if target is None:
                correct = next(
                    (
                        names.get(item.id_pos, "")
                        for item in visit.tujuan
                        if _destination_status(item) == "DIDALAM"
                    ),
                    "Pos 1",
                )
                raise HTTPException(
                    status_code=409,
                    detail=f"Pos tujuan tidak sesuai. Pengunjung sedang berada di: {correct}",
                )
            target.status = "SELESAI"
            target.waktu_keluar = now
            visit.status = "DALAM_KUNJUNGAN"
            _add_log(
                db,
                visit,
                user,
                pos_id,
                "LOKASI_OUT",
                "SUKSES",
                "Pengunjung keluar dari lokasi tujuan melalui validasi barcode.",
            )
        else:
            raise HTTPException(
                status_code=409,
                detail=f"Status kunjungan saat ini {visit.status} dan tidak dapat diproses.",
            )
    except HTTPException as error:
        message = str(error.detail)
        _add_log(db, visit, user, pos_id, "SCAN_BARCODE", "GAGAL", message)
        await db.commit()
        raise

    _add_log(db, visit, user, pos_id, "SCAN_BARCODE", "SUKSES", "Barcode dipindai.")
    await db.commit()
    return {
        "status": "success",
        "data": _visitor_payload(visit, visitor, vehicle, names),
    }


@router.post("/status")
async def update_mobile_status(
    data: StatusRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pos_id = _require_security_pos(user)
    row = await _load_visit(db, data.barcode.strip())
    if not row:
        raise HTTPException(status_code=404, detail="Pengunjung tidak ditemukan")
    visit, _, _ = row
    main_post = pos_id == MAIN_POS_ID
    now = datetime.now(WIB)
    action = data.action
    log_result = "SUKSES"

    try:
        check_expiration(visit.created_at)
        if action in {"checkin_main", "tolak_main"}:
            if not main_post or visit.status != "DRAFT":
                raise HTTPException(status_code=409, detail="Kunjungan tidak dapat diproses di Pos 1")
            visit.status = "DALAM_KUNJUNGAN" if action == "checkin_main" else "DITOLAK"
            visit.check_in_time = now
            log_action = "GERBANG_IN_TERIMA" if action == "checkin_main" else "GERBANG_IN_TOLAK"
            if action == "tolak_main":
                log_result = "GAGAL"
            detail = "Pengunjung diterima di Pos 1." if action == "checkin_main" else (
                f"Data ditolak: {data.alasan_selesai or 'Data tidak sesuai.'}"
            )
        elif action == "checkin_dest":
            if main_post or data.destination_id is None:
                raise HTTPException(status_code=403, detail="Aksi ini hanya untuk pos tujuan")
            ordered = sorted(visit.tujuan, key=lambda item: item.id_tujuan)
            active = [
                item for item in ordered if _destination_status(item) == "DIDALAM"
            ]
            unfinished = [
                item for item in ordered if _destination_status(item) != "SELESAI"
            ]
            target = next(
                (item for item in ordered if item.id_tujuan == data.destination_id),
                None,
            )
            if target is None or target.id_pos != pos_id:
                raise HTTPException(status_code=409, detail="Tujuan ini bukan untuk pos Anda")
            if (
                visit.status != "DALAM_KUNJUNGAN"
                or active
                or not unfinished
                or unfinished[0].id_tujuan != target.id_tujuan
                or _destination_status(target) != "MENUNGGU"
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Tujuan harus diproses berurutan dan satu per satu.",
                )
            target.status = "DIDALAM"
            target.waktu_masuk = now
            visit.status = "DALAM_LOKASI"
            log_action, detail = "LOKASI_IN", "Pengunjung masuk ke lokasi tujuan."
        elif action == "complete_dest":
            if main_post or data.destination_id is None:
                raise HTTPException(status_code=403, detail="Aksi ini hanya untuk pos tujuan")
            target = next(
                (item for item in visit.tujuan if item.id_tujuan == data.destination_id),
                None,
            )
            if (
                target is None
                or target.id_pos != pos_id
                or _destination_status(target) != "DIDALAM"
                or visit.status != "DALAM_LOKASI"
            ):
                raise HTTPException(status_code=409, detail="Tujuan ini tidak sedang aktif di pos Anda")
            target.status = "SELESAI"
            target.waktu_keluar = now
            visit.status = "DALAM_KUNJUNGAN"
            log_action, detail = "LOKASI_OUT", "Pengunjung keluar dari lokasi tujuan."
        elif action in {"checkout_main", "complete_main"}:
            if not main_post or visit.status != "DALAM_KUNJUNGAN":
                raise HTTPException(status_code=409, detail="Kunjungan tidak dapat diselesaikan di Pos 1")
            if any(
                _destination_status(item) == "DIDALAM" for item in visit.tujuan
            ):
                raise HTTPException(status_code=409, detail="Pengunjung masih berada di pos tujuan")
            if action == "checkout_main" and any(
                _destination_status(item) != "SELESAI" for item in visit.tujuan
            ):
                raise HTTPException(status_code=409, detail="Selesaikan semua tujuan sebelum keluar komplek")
            if action == "complete_main" and not (data.alasan_selesai or "").strip():
                raise HTTPException(status_code=400, detail="Alasan menyelesaikan kunjungan wajib diisi")
            visit.status = "SELESAI"
            visit.check_out_time = now
            if action == "checkout_main":
                log_action, detail = "GERBANG_OUT", "Pengunjung keluar dari gerbang utama."
            else:
                log_action = "SELESAI_MANUAL_POS1"
                detail = (data.alasan_selesai or "").strip()
        else:
            raise HTTPException(status_code=400, detail="Aksi status tidak dikenal")
    except HTTPException as error:
        _add_log(db, visit, user, pos_id, action.upper(), "GAGAL", str(error.detail))
        await db.commit()
        raise

    _add_log(db, visit, user, pos_id, log_action, log_result, detail)
    await db.commit()
    return {
        "status": "success",
        "message": "Berhasil",
        "new_status": _mobile_status(visit.status),
    }
