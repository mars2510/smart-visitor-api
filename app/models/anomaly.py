from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base

class AnomalyResult(Base):
    __tablename__ = "hasil_anomali"
    id = Column(Integer, primary_key=True, index=True)
    id_kunjungan = Column(String, ForeignKey("kunjungan.id_kunjungan"))
    anomaly_score = Column(Float)
    is_anomaly = Column(Boolean, default=False)
    analysis_month = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())