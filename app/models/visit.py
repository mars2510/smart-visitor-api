from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class Visit(Base):
    __tablename__ = "kunjungan"
    id_kunjungan = Column(String, primary_key=True, index=True)
    id_pengunjung = Column(Integer, ForeignKey("pengunjung.id_pengunjung"))
    id_kendaraan = Column(Integer, ForeignKey("kendaraan.id_kendaraan"), nullable=True)
    id_perusahaan = Column(Integer, ForeignKey("mitra_perusahaan.id_perusahaan"), nullable=True)
    tipe_kunjungan = Column(String)
    status = Column(String, default="DRAFT")
    kode_qr = Column(String, unique=True, index=True)
    catatan = Column(Text)
    nama_lainnya = Column(Text, nullable=True)
    jumlah_pengunjung = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    check_in_time = Column(DateTime(timezone=True), nullable=True)
    check_out_time = Column(DateTime(timezone=True), nullable=True)

    tujuan = relationship("VisitDestination", back_populates="kunjungan")
    logs = relationship("ActivityLog", back_populates="kunjungan")

class VisitDestination(Base):
    __tablename__ = "tujuan_kunjungan"
    id_tujuan = Column(Integer, primary_key=True, index=True)
    id_kunjungan = Column(String, ForeignKey("kunjungan.id_kunjungan"))
    id_pos = Column(Integer, ForeignKey("pos.id_pos"))
    orang_yang_ditemui = Column(String)
    tujuan = Column(Text)
    status = Column(String, default="MENUNGGU")
    waktu_masuk = Column(DateTime(timezone=True), nullable=True)
    waktu_keluar = Column(DateTime(timezone=True), nullable=True)

    kunjungan = relationship("Visit", back_populates="tujuan")