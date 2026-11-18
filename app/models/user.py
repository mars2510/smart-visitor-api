from sqlalchemy import Column, ForeignKey, Integer, String
from app.core.database import Base

class User(Base):
    __tablename__ = "pengguna"
    id_pengguna = Column(Integer, primary_key=True, index=True)
    nama = Column(String, nullable=False)
    peran = Column(String, nullable=False)
    password = Column(String, nullable=False)
    user_name = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    id_pos = Column(Integer, ForeignKey("pos.id_pos"), nullable=True)