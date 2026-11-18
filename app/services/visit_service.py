# app/services/visit_service.py
import uuid
import random
import string
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.visit_repo import VisitRepository
from app.models.visit import Visit, VisitDestination
from app.models.visitor import Visitor, Vehicle

class VisitService:
    def __init__(self, db: AsyncSession):
        self.repo = VisitRepository(db)
        self.db = db

    def _generate_short_code(self) -> str:
        characters = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789" 
        random_str = ''.join(random.choices(characters, k=6))
        return f"ADR-{random_str}"

    async def register_visit(self, data: dict, is_lainnya: bool = False) -> Visit:
        nama = data.get("nama") or data.get("nama_lengkap")
        telepon = data.get("telepon")
        alamat = data.get("alamat") or data.get("keterangan")

        # 1. Handle Visitor
        visitor = await self.repo.get_visitor_by_name_phone(nama, telepon)
        if not visitor:
            visitor = await self.repo.create_visitor(Visitor(nama=nama, telepon=telepon, alamat=alamat))

        # 2. Handle Vehicle
        kendaraan_id = None
        if data.get("nomor_polisi"):
            vehicle = await self.repo.get_vehicle_by_plate(data["nomor_polisi"])
            if not vehicle:
                vehicle = await self.repo.create_vehicle(Vehicle(nomor_polisi=data["nomor_polisi"], jenis_kendaraan=data.get("jenis")))
            kendaraan_id = vehicle.id_kendaraan

        # 3. Handle Visit
        visit_id = f"VIS-{uuid.uuid4().hex[:8].upper()}"
        qr_code = self._generate_short_code()
        
        new_visit = Visit(
            id_kunjungan=visit_id,
            id_pengunjung=visitor.id_pengunjung,
            id_kendaraan=kendaraan_id,
            id_perusahaan=data.get("perusahaan_id"),
            tipe_kunjungan=data.get("status_kunjungan") or data.get("status"),
            jumlah_pengunjung=data.get("jumlah", 1),
            nama_lainnya=data.get("nama_lain"),
            status="DRAFT",
            kode_qr=qr_code,
            catatan=data.get("keterangan") if is_lainnya else None
        )
        await self.repo.create_visit(new_visit)
        
        # PENTING: Flush agar ID Visit benar-benar ada di database sebelum insert tujuan
        await self.db.flush()

        # 4. Handle Tujuan Kunjungan
        tujuan_data = data.get("tujuan_kunjungan", [])
        
        # Debugging: Print ke terminal untuk melihat apa yang diterima
        print(f"DEBUG: Tujuan diterima -> {tujuan_data}")

        if not is_lainnya and tujuan_data:
            for tuj in tujuan_data:
                # Pastikan tuj adalah dict
                if isinstance(tuj, dict):
                    pos_id = tuj.get("pos_id")
                    bertemu = tuj.get("bertemu_dengan")
                    keperluan = tuj.get("keperluan")
                else:
                    pos_id = getattr(tuj, "pos_id", None)
                    bertemu = getattr(tuj, "bertemu_dengan", None)
                    keperluan = getattr(tuj, "keperluan", None)

                if pos_id: # Hanya simpan jika pos_id tidak kosong
                    dest = VisitDestination(
                        id_kunjungan=visit_id,
                        id_pos=pos_id,
                        orang_yang_ditemui=bertemu,
                        tujuan=keperluan,
                        status="MENUNGGU"
                    )
                    await self.repo.create_destination(dest)

        await self.db.commit()
        await self.db.refresh(new_visit)
        return new_visit