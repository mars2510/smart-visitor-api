import asyncio
import random
import uuid
from datetime import datetime, timedelta, timezone
from app.core.database import AsyncSessionLocal
from app.models.visitor import Visitor, Pos, MitraPerusahaan, Vehicle
from app.models.visit import Visit, VisitDestination

async def seed_data():
    async with AsyncSessionLocal() as db:
        print("Memulai proses seeding...")
        
        # 0. BERSIHKAN DATA LAMA (Agar tidak menumpuk)
        print("Membersihkan data lama...")
        from sqlalchemy import delete
        await db.execute(delete(VisitDestination))
        await db.execute(delete(Visit))
        await db.execute(delete(Visitor))
        await db.execute(delete(Vehicle))
        await db.execute(delete(Pos))
        await db.execute(delete(MitraPerusahaan))
        await db.commit()

        # 1. Buat POS
        pos_list = ["Gedung A - HRD", "Gedung B - IT", "Gedung C - Finance"]
        pos_objects = []
        for p_name in pos_list:
            pos = Pos(nama_pos=p_name)
            db.add(pos)
            await db.flush()
            pos_objects.append(pos)

        # 2. Buat Mitra Perusahaan
        pt = MitraPerusahaan(nama_perusahaan="PT Teknologi Maju")
        db.add(pt)
        await db.flush()

        # 3. Buat Data Pengunjung & Kunjungan
        names = ["Andi Wijaya", "Siti Aminah", "Rudi Hartono", "Dewi Lestari", "Agus Setiawan"]
        statuses = ["DRAFT", "DALAM_KUNJUNGAN", "DALAM_LOKASI"]
        
        # Timezone WIB
        wib = timezone(timedelta(hours=7))

        for i, name in enumerate(names):
            # Buat Visitor
            visitor = Visitor(nama=name, telepon=f"0812345678{i}", alamat="Jakarta")
            db.add(visitor)
            await db.flush()

            # Buat Kendaraan
            vehicle = Vehicle(nomor_polisi=f"B {1000+i} ABC", jenis_kendaraan="Mobil")
            db.add(vehicle)
            await db.flush()

            # Buat Kunjungan
            visit_id = f"VIS-{uuid.uuid4().hex[:8].upper()}"
            qr_code = f"ADR-{uuid.uuid4().hex[:6].upper()}" 
            status = random.choice(statuses)

            # Tentukan waktu masuk (jika statusnya bukan DRAFT)
            check_in = None
            if status != "DRAFT":
                # Anggap masuk beberapa jam yang lalu
                check_in = datetime.now(wib) - timedelta(hours=random.randint(1, 3))

            new_visit = Visit(
                id_kunjungan=visit_id,
                id_pengunjung=visitor.id_pengunjung,
                id_kendaraan=vehicle.id_kendaraan,
                id_perusahaan=pt.id_perusahaan,
                tipe_kunjungan="Tamu Umum",
                status=status,
                kode_qr=qr_code,
                check_in_time=check_in, # <-- MENGISI WAKTU MASUK GERBANG
                jumlah_pengunjung=1,
                created_at=datetime.now(wib) - timedelta(hours=5) # Daftar 5 jam lalu
            )
            db.add(new_visit)
            await db.flush()

            # Buat Tujuan Kunjungan
            tujuan_status = "MENUNGGU"
            waktu_masuk_tujuan = None
            
            # Jika status DALAM_LOKASI, berarti dia sudah scan masuk ke divisi tujuan
            if status == "DALAM_LOKASI":
                tujuan_status = "DIDALAM"
                waktu_masuk_tujuan = check_in + timedelta(minutes=10) # Masuk divisi 10 menit setelah masuk gerbang

            tujuan = VisitDestination(
                id_kunjungan=visit_id,
                id_pos=random.choice(pos_objects).id_pos,
                orang_yang_ditemui="Manager",
                tujuan="Meeting Bisnis",
                status=tujuan_status,
                waktu_masuk=waktu_masuk_tujuan
            )
            db.add(tujuan)

        await db.commit()
        print(f"Berhasil memasukkan {len(names)} data pengunjung dummy (dengan relasi dan waktu masuk)!")
        print("Silakan refresh halaman Admin Anda.")

if __name__ == "__main__":
    asyncio.run(seed_data())