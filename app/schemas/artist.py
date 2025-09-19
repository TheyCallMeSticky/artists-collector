from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ArtistBase(BaseModel):
    name: str
    spotify_id: Optional[str] = None
    youtube_channel_id: Optional[str] = None
    genre: str = "hip-hop"
    country: Optional[str] = None

class ArtistCreate(ArtistBase):
    pass

class ArtistUpdate(BaseModel):
    name: Optional[str] = None
    spotify_followers: Optional[int] = None
    spotify_popularity: Optional[int] = None
    monthly_listeners: Optional[int] = None
    youtube_subscribers: Optional[int] = None
    youtube_views: Optional[int] = None
    youtube_videos_count: Optional[int] = None
    score: Optional[float] = None
    is_active: Optional[bool] = None

class Artist(ArtistBase):
    id: int
    spotify_followers: int
    spotify_popularity: int
    monthly_listeners: int
    youtube_subscribers: int
    youtube_views: int
    youtube_videos_count: int
    score: float
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class CollectionLogCreate(BaseModel):
    artist_id: int
    collection_type: str
    status: str
    error_message: Optional[str] = None
    data_collected: Optional[str] = None

class CollectionLog(CollectionLogCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class ScoreCreate(BaseModel):
    artist_id: int
    score_value: float
    score_breakdown: Optional[str] = None

class Score(ScoreCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
