from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from app.db.database import get_db
from app.services.artist_service import ArtistService
from app.services.scoring_service import ScoringService
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

@router.get("/count")
def count_artists(db: Session = Depends(get_db)):
    service = ArtistService(db)
    total = service.count_artists()
    return {"total": total}

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

@router.get("/opportunities")
async def get_artist_opportunities(
    min_followers: Optional[int] = Query(1000, description="Minimum Spotify followers"),
    max_followers: Optional[int] = Query(100000, description="Maximum Spotify followers"),
    max_monthly_listeners: Optional[int] = Query(500000, description="Maximum monthly listeners"),
    min_score: Optional[float] = Query(50.0, description="Minimum TubeBuddy score"),
    limit: Optional[int] = Query(20, description="Maximum number of results"),
    db: Session = Depends(get_db)
):
    """
    Endpoint TubeBuddy - Retourner les meilleures opportunités d'artistes pour type beats
    Applique les filtres de validation et calcule les scores TubeBuddy
    """
    try:
        artist_service = ArtistService(db)
        scoring_service = ScoringService()

        # 1. Récupérer tous les artistes qui correspondent aux critères de base
        artists = artist_service.get_artists_by_criteria(
            min_followers=min_followers,
            max_followers=max_followers,
            max_monthly_listeners=max_monthly_listeners,
            limit=limit * 3  # Récupérer plus d'artistes pour avoir des options après scoring
        )

        if not artists:
            return {
                "opportunities": [],
                "total_candidates": 0,
                "filters_applied": {
                    "min_followers": min_followers,
                    "max_followers": max_followers,
                    "max_monthly_listeners": max_monthly_listeners,
                    "min_score": min_score
                }
            }

        # 2. Calculer les scores TubeBuddy pour chaque artiste
        artist_names = [artist.name for artist in artists]
        scores = await scoring_service.batch_score_artists(artist_names)

        # 3. Fusionner les données d'artistes avec leurs scores
        opportunities = []
        for artist, score_data in zip(artists, scores):
            if score_data.get("overall_score", 0) >= min_score:
                opportunities.append({
                    "artist_id": artist.id,
                    "artist_name": artist.name,
                    "spotify_followers": artist.spotify_followers,
                    "spotify_monthly_listeners": artist.spotify_monthly_listeners,
                    "spotify_popularity": artist.spotify_popularity,
                    "tubebuddy_score": score_data.get("overall_score", 0),
                    "search_volume_score": score_data.get("search_volume_score", 0),
                    "competition_score": score_data.get("competition_score", 0),
                    "optimization_score": score_data.get("optimization_score", 0),
                    "score_interpretation": scoring_service.get_score_interpretation(
                        score_data.get("overall_score", 0)
                    ),
                    "last_seen": artist.last_seen_date.isoformat() if artist.last_seen_date else None
                })

        # 4. Trier par score TubeBuddy (meilleur score en premier)
        opportunities.sort(key=lambda x: x["tubebuddy_score"], reverse=True)

        # 5. Limiter au nombre demandé
        opportunities = opportunities[:limit]

        return {
            "opportunities": opportunities,
            "total_candidates": len(artists),
            "total_opportunities": len(opportunities),
            "filters_applied": {
                "min_followers": min_followers,
                "max_followers": max_followers,
                "max_monthly_listeners": max_monthly_listeners,
                "min_score": min_score
            },
            "algorithm": "TubeBuddy: Search Volume (40%) + Competition (40%) + Optimization (20%)"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors du calcul des opportunités: {str(e)}"
        )

class ArtistScoreRequest(BaseModel):
    artist_names: List[str]

@router.post("/batch-score")
async def calculate_batch_tubebuddy_scores(request: ArtistScoreRequest):
    """
    Calculer les scores TubeBuddy pour une liste d'artistes en batch
    Endpoint indépendant pour tester l'algorithme sur plusieurs artistes
    """
    try:
        scoring_service = ScoringService()

        if not request.artist_names:
            raise HTTPException(
                status_code=400,
                detail="La liste d'artistes ne peut pas être vide"
            )

        if len(request.artist_names) > 50:
            raise HTTPException(
                status_code=400,
                detail="Maximum 50 artistes par batch"
            )

        # Calculer les scores en batch
        scores = await scoring_service.batch_score_artists(request.artist_names)

        # Ajouter l'interprétation pour chaque résultat
        for score_result in scores:
            if "error" not in score_result:
                overall_score = score_result.get("overall_score", 0)
                interpretation = scoring_service.get_score_interpretation(overall_score)
                score_result["score_interpretation"] = interpretation

        # Calculer les statistiques du batch
        successful_scores = [s for s in scores if "error" not in s]
        failed_scores = [s for s in scores if "error" in s]

        if successful_scores:
            avg_search_volume = sum(s.get("search_volume_score", 0) for s in successful_scores) / len(successful_scores)
            avg_competition = sum(s.get("competition_score", 0) for s in successful_scores) / len(successful_scores)
            avg_optimization = sum(s.get("optimization_score", 0) for s in successful_scores) / len(successful_scores)
            avg_overall = sum(s.get("overall_score", 0) for s in successful_scores) / len(successful_scores)
        else:
            avg_search_volume = avg_competition = avg_optimization = avg_overall = 0

        return {
            "total_artists": len(request.artist_names),
            "successful_calculations": len(successful_scores),
            "failed_calculations": len(failed_scores),
            "batch_statistics": {
                "avg_search_volume_score": round(avg_search_volume),
                "avg_competition_score": round(avg_competition),
                "avg_optimization_score": round(avg_optimization),
                "avg_overall_score": round(avg_overall)
            },
            "artist_scores": scores,
            "algorithm": "TubeBuddy: Search Volume (40%) + Competition (40%) + Optimization (20%)"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors du calcul batch des scores TubeBuddy: {str(e)}"
        )
