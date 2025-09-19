from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any
from app.db.database import get_db
from app.services.data_collector import DataCollector
from app.services.youtube_service import YouTubeService
from pydantic import BaseModel

router = APIRouter(prefix="/collection", tags=["collection"])

class CollectArtistRequest(BaseModel):
    artist_name: str

class CollectArtistResponse(BaseModel):
    success: bool
    artist_name: str
    artist_id: int = None
    spotify_data_collected: bool
    youtube_data_collected: bool
    errors: list = []

@router.post("/artist", response_model=CollectArtistResponse)
def collect_artist_data(request: CollectArtistRequest, db: Session = Depends(get_db)):
    """Collecter les données d'un artiste depuis Spotify et YouTube"""
    collector = DataCollector(db)
    
    try:
        result = collector.collect_and_save_artist(request.artist_name)
        
        return CollectArtistResponse(
            success=result['success'],
            artist_name=result['artist_name'],
            artist_id=result.get('artist_id'),
            spotify_data_collected=bool(result.get('spotify_data')),
            youtube_data_collected=bool(result.get('youtube_data')),
            errors=result.get('errors', [])
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la collecte: {str(e)}")

@router.post("/artist/background")
def collect_artist_data_background(
    request: CollectArtistRequest, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Collecter les données d'un artiste en arrière-plan"""
    def collect_task():
        collector = DataCollector(db)
        collector.collect_and_save_artist(request.artist_name)
    
    background_tasks.add_task(collect_task)
    return {"message": f"Collecte en arrière-plan démarrée pour {request.artist_name}"}

@router.get("/quota/youtube")
def get_youtube_quota_usage():
    """Récupérer l'utilisation des quotas YouTube"""
    try:
        youtube_service = YouTubeService()
        return youtube_service.get_quota_usage()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des quotas: {str(e)}")

@router.post("/test/spotify")
def test_spotify_connection(request: CollectArtistRequest, db: Session = Depends(get_db)):
    """Tester la connexion Spotify avec un artiste"""
    collector = DataCollector(db)
    
    try:
        spotify_data = collector.spotify_service.collect_artist_data(request.artist_name)
        return {
            "success": bool(spotify_data),
            "data": spotify_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur Spotify: {str(e)}")

@router.post("/test/youtube")
def test_youtube_connection(request: CollectArtistRequest, db: Session = Depends(get_db)):
    """Tester la connexion YouTube avec un artiste"""
    collector = DataCollector(db)
    
    try:
        youtube_data = collector.youtube_service.collect_artist_data(request.artist_name)
        return {
            "success": bool(youtube_data),
            "data": youtube_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur YouTube: {str(e)}")
