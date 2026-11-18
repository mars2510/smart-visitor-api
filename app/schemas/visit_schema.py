# app/schemas/visit_schema.py
from pydantic import BaseModel
from typing import List, Optional

# --- SCHEMA REGISTRASI ---
class TujuanKunjunganSchema(BaseModel):
    pos_id: int
    bertemu_dengan: Optional[str] = None
    bagian: Optional[str] = None
    keperluan: Optional[str] = None

class VisitRegisterSchema(BaseModel):
    nama: str
    telepon: Optional[str] = None
    status_kunjungan: str
    jumlah: int = 1
    nama_lain: Optional[str] = None
    alamat: Optional[str] = None
    jenis: Optional[str] = None
    nomor_polisi: Optional[str] = None
    perusahaan_id: Optional[int] = None
    tujuan_kunjungan: List[TujuanKunjunganSchema] = []

class VisitLainnyaSchema(BaseModel):
    nama_lengkap: str
    keterangan: Optional[str] = None
    status: str
    jenis: Optional[str] = None
    nomor_polisi: Optional[str] = None
    tujuan_kunjungan: List[TujuanKunjunganSchema] = []

# --- SCHEMA SCAN ---
class ScanConfirmRequest(BaseModel):
    kode_qr: str
    aksi: str # "TERIMA" atau "TOLAK"
    id_pos_security: int
    alasan_tolak: Optional[str] = None

class ScanLocationRequest(BaseModel):
    kode_qr: str
    id_pos_scanner: int

class ScanGateOutRequest(BaseModel):
    kode_qr: str
    id_pos_security: int