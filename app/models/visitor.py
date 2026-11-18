from sqlalchemy import Column, Integer, String, Text
from app.core.database import Base

class Visitor(Base):
    __tablename__ = "pengunjung"
    id_pengunjung = Column(Integer, primary_key=True, index=True)
    nama = Column(String, nullable=False)
    alamat = Column(Text)
    telepon = Column(String)

class Vehicle(Base):
    __tablename__ = "kendaraan"
    id_kendaraan = Column(Integer, primary_key=True, index=True)
    nomor_polisi = Column(String, unique=True, index=True)
    jenis_kendaraan = Column(String)

class Pos(Base):
    __tablename__ = "pos"
    id_pos = Column(Integer, primary_key=True, index=True)
    nama_pos = Column(String, nullable=False)

class MitraPerusahaan(Base):
    __tablename__ = "mitra_perusahaan"
    id_perusahaan = Column(Integer, primary_key=True, index=True)
    nama_perusahaan = Column(String, nullable=False)