from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.database import get_db
from app.services.artist_service import ArtistService
from app.schemas.artist import Artist, ArtistCreate, ArtistUpdate, CollectionLog, Score

router = APIRouter(prefix="/artists", tags=["artists"])

@router.post("/", response_model=Artist)
def create_artist(artist: ArtistCreate, db: Session = Depends(get_db)):
    service = ArtistService(db)
    return service.create_artist(artist)

@router.get("/", response_model=List[Artist])
def read_artists(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    service = ArtistService(db)
    return service.get_artists(skip=skip, limit=limit)

@router.get("/top", response_model=List[Artist])
def get_top_artists(limit: int = 50, db: Session = Depends(get_db)):
    service = ArtistService(db)
    return service.get_top_artists_by_score(limit=limit)

@router.get("/{artist_id}", response_model=Artist)
def read_artist(artist_id: int, db: Session = Depends(get_db)):
    service = ArtistService(db)
    artist = service.get_artist(artist_id)
    if artist is None:
        raise HTTPException(status_code=404, detail="Artist not found")
    return artist

@router.put("/{artist_id}", response_model=Artist)
def update_artist(artist_id: int, artist_update: ArtistUpdate, db: Session = Depends(get_db)):
    service = ArtistService(db)
    artist = service.update_artist(artist_id, artist_update)
    if artist is None:
        raise HTTPException(status_code=404, detail="Artist not found")
    return artist

@router.delete("/{artist_id}")
def delete_artist(artist_id: int, db: Session = Depends(get_db)):
    service = ArtistService(db)
    success = service.delete_artist(artist_id)
    if not success:
        raise HTTPException(status_code=404, detail="Artist not found")
    return {"message": "Artist deleted successfully"}

@router.get("/{artist_id}/scores", response_model=List[Score])
def get_artist_scores(artist_id: int, db: Session = Depends(get_db)):
    service = ArtistService(db)
    return service.get_artist_scores(artist_id)
