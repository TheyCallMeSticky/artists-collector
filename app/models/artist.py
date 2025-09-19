from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.sql import func
from app.db.database import Base

class Artist(Base):
    __tablename__ = "artists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    spotify_id = Column(String, unique=True, index=True)
    youtube_channel_id = Column(String, unique=True, index=True)
    
    # Métriques Spotify
    spotify_followers = Column(Integer, default=0)
    spotify_popularity = Column(Integer, default=0)
    monthly_listeners = Column(Integer, default=0)
    
    # Métriques YouTube
    youtube_subscribers = Column(Integer, default=0)
    youtube_views = Column(Integer, default=0)
    youtube_videos_count = Column(Integer, default=0)
    
    # Score calculé
    score = Column(Float, default=0.0)
    
    # Métadonnées
    genre = Column(String, default="hip-hop")
    country = Column(String)
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class CollectionLog(Base):
    __tablename__ = "collection_logs"

    id = Column(Integer, primary_key=True, index=True)
    artist_id = Column(Integer, index=True)
    collection_type = Column(String)  # 'spotify' ou 'youtube'
    status = Column(String)  # 'success', 'error', 'skipped'
    error_message = Column(Text)
    data_collected = Column(Text)  # JSON des données collectées
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Score(Base):
    __tablename__ = "scores"

    id = Column(Integer, primary_key=True, index=True)
    artist_id = Column(Integer, index=True)
    score_value = Column(Float, nullable=False)
    score_breakdown = Column(Text)  # JSON avec le détail du calcul
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
