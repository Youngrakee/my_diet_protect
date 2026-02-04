# database.py
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import pytz

KST = pytz.timezone('Asia/Seoul')

def get_kst_now():
    return datetime.now(KST)
import os
from dotenv import load_dotenv

load_dotenv()

# DB 연결 경로 (환경 변수에서 가져오되, 없으면 SQLite 사용)
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./diet_log.db")

# SQLAlchemy 1.4+ 및 2.0에서는 'postgres://' 대신 'postgresql://'을 사용해야 함
# 또한 명시적으로 'psycopg2' 드라이버를 지정하여 연결 시도
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif SQLALCHEMY_DATABASE_URL.startswith("postgresql://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

# PostgreSQL의 경우 connect_args가 필요 없음
if "postgresql" in SQLALCHEMY_DATABASE_URL:
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
else:
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    
    # [기본 정보]
    gender = Column(String, nullable=True)      # 성별
    age = Column(Integer, nullable=True)        # 나이
    height = Column(Float, nullable=True)       # 키
    weight = Column(Float, nullable=True)       # 몸무게

    # [건강 상태]
    diabetes_type = Column(String, nullable=True)   # 당뇨 상태 (없음/전단계/1형/2형)
    fasting_sugar = Column(Integer, nullable=True)  # 공복 혈당 (선택)
    hba1c = Column(Float, nullable=True)            # 당화혈색소 (선택)

    # [생활 패턴]
    activity_level = Column(String, nullable=True)  # 활동 수준

    # [목표]
    health_goal = Column(String, nullable=True)     # 목표 (감량/안정/유지/근육)
    
    # 관계 설정
    logs = relationship("FoodLog", back_populates="owner")
    health_logs = relationship("HealthLog", back_populates="owner")

class FoodLog(Base):
    __tablename__ = "food_logs"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=get_kst_now)
    input_type = Column(String)
    food_description = Column(String)
    blood_sugar_impact = Column(String)
    summary = Column(Text)
    action_guide = Column(Text)
    detailed_action_guide = Column(Text)  # [NEW] 상세 행동 가이드
    carbs_ratio = Column(Float)           # [NEW] 탄수화물 비율
    protein_ratio = Column(Float)         # [NEW] 단백질 비율
    fat_ratio = Column(Float)             # [NEW] 지방 비율
    alternatives = Column(Text)
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="logs")

class HealthLog(Base):
    __tablename__ = "health_logs"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=get_kst_now)
    sugar_level = Column(Integer)
    note = Column(String, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="health_logs")

def init_db():
    Base.metadata.create_all(bind=engine)