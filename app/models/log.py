from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class ActivityLog(Base):
    __tablename__ = "log_aktivitas"
    id_log = Column(Integer, primary_key=True, index=True)
    id_kunjungan = Column(String, ForeignKey("kunjungan.id_kunjungan"))
    id_pengguna = Column(Integer, ForeignKey("pengguna.id_pengguna"))
    id_pos = Column(Integer, ForeignKey("pos.id_pos"))
    jenis_aksi = Column(String, nullable=False)
    status_hasil = Column(String, default="SUKSES")
    keterangan = Column(Text)
    waktu_scan = Column(DateTime(timezone=True), server_default=func.now())
    kunjungan = relationship("Visit", back_populates="logs")