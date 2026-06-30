"""
PressureLab AI - Database Setup
SQLAlchemy models and database connection handling.
Supports PostgreSQL with SQLite fallback.
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, JSON, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql import func
import logging

from config import settings

logger = logging.getLogger(__name__)

# Determine if we need to use SQLite specific connect args
connect_args = {}
if settings.effective_database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    logger.info("Using SQLite fallback database")
else:
    logger.info("Using PostgreSQL database")

engine = create_engine(
    settings.effective_database_url,
    connect_args=connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# --- Database Models ---

class DBUser(Base):
    """Stub for user tracking if needed"""
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)

class DBMatch(Base):
    """Stores match metadata"""
    __tablename__ = "matches"
    
    id = Column(Integer, primary_key=True, index=True)
    statsbomb_id = Column(Integer, unique=True, index=True)
    home_team = Column(String, index=True)
    away_team = Column(String, index=True)
    home_score = Column(Integer)
    away_score = Column(Integer)
    competition = Column(String)
    season = Column(String)
    match_date = Column(String)
    venue = Column(String)

class DBEvent(Base):
    """Stores raw match events"""
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, index=True)
    event_type = Column(String, index=True)
    minute = Column(Integer, index=True)
    second = Column(Integer)
    player_name = Column(String)
    player_id = Column(Integer, index=True)
    team = Column(String)
    location_x = Column(Float, nullable=True)
    location_y = Column(Float, nullable=True)
    outcome = Column(String, nullable=True)
    under_pressure = Column(Boolean, default=False)
    details = Column(JSON, default=dict)

class DBExplanation(Base):
    """Caches AI explanations to save API calls"""
    __tablename__ = "explanations"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, index=True, nullable=True)
    player_id = Column(Integer, index=True, nullable=True)
    minute = Column(Integer, index=True, nullable=True)
    explanation_type = Column(String) # 'event', 'replay', 'prediction', 'simulator'
    level = Column(String)
    content = Column(JSON)
    model_used = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# --- Database Utilities ---

def init_db():
    """Create all tables in the database."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")

def get_db():
    """Dependency to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
