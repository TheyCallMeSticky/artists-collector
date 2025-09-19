from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app.db.database import get_db
from app.services.collection_scheduler import CollectionScheduler
from app.services.scoring_service import ScoringService
from app.services.artist_service import ArtistService
from pydantic import BaseModel
import asyncio

router = APIRouter(prefix="/scoring", tags=["scoring"])

class BatchCollectionRequest(BaseModel):
    artist_names: List[str]

class ScoreCalculationRequest(BaseModel):
    artist_id: int

class OpportunitiesResponse(BaseModel):
    total_opportunities: int
    opportunities: List[Dict[str, Any]]

@router.post("/calculate/{artist_id}")
async def calculate_artist_score(artist_id: int, db: Session = Depends(get_db)):
    """Calculer le score d'un artiste spécifique"""
    try:
        scheduler = CollectionScheduler(db)
        await scheduler._calculate_and_save_score(artist_id)
        
        # Récupérer l'artiste mis à jour
        artist_service = ArtistService(db)
        artist = artist_service.get_artist(artist_id)
        
        if not artist:
            raise HTTPException(status_code=404, detail="Artiste non trouvé")
        
        scoring_service = ScoringService()
        interpretation = scoring_service.get_score_interpretation(artist.score)
        
        return {
            "artist_id": artist_id,
            "artist_name": artist.name,
            "score": artist.score,
            "interpretation": interpretation
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du calcul du score: {str(e)}")

@router.post("/batch-collect")
async def batch_collect_artists(request: BatchCollectionRequest, db: Session = Depends(get_db)):
    """Collecter un lot d'artistes et calculer leurs scores"""
    try:
        scheduler = CollectionScheduler(db)
        results = await scheduler.collect_artists_batch(request.artist_names)
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la collecte en lot: {str(e)}")

@router.post("/batch-collect/background")
def batch_collect_artists_background(
    request: BatchCollectionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Collecter un lot d'artistes en arrière-plan"""
    async def collect_task():
        scheduler = CollectionScheduler(db)
        await scheduler.collect_artists_batch(request.artist_names)
    
    background_tasks.add_task(lambda: asyncio.run(collect_task()))
    return {
        "message": f"Collecte en arrière-plan démarrée pour {len(request.artist_names)} artistes",
        "artist_count": len(request.artist_names)
    }

@router.get("/opportunities", response_model=OpportunitiesResponse)
def get_top_opportunities(limit: int = 20, db: Session = Depends(get_db)):
    """Récupérer les meilleures opportunités d'artistes"""
    try:
        scheduler = CollectionScheduler(db)
        opportunities = scheduler.get_top_opportunities(limit=limit)
        
        return OpportunitiesResponse(
            total_opportunities=len(opportunities),
            opportunities=opportunities
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des opportunités: {str(e)}")

@router.post("/refresh/{artist_id}")
async def refresh_artist_data(artist_id: int, db: Session = Depends(get_db)):
    """Rafraîchir les données et le score d'un artiste"""
    try:
        scheduler = CollectionScheduler(db)
        result = await scheduler.refresh_artist_data(artist_id)
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result.get('error', 'Erreur inconnue'))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du rafraîchissement: {str(e)}")

@router.post("/update-all-scores")
async def update_all_scores(limit: int = 100, db: Session = Depends(get_db)):
    """Mettre à jour les scores de tous les artistes existants"""
    try:
        scheduler = CollectionScheduler(db)
        results = await scheduler.update_existing_artists_scores(limit=limit)
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la mise à jour des scores: {str(e)}")

@router.post("/update-all-scores/background")
def update_all_scores_background(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    limit: int = 100
):
    """Mettre à jour les scores de tous les artistes en arrière-plan"""
    async def update_task():
        scheduler = CollectionScheduler(db)
        await scheduler.update_existing_artists_scores(limit=limit)
    
    background_tasks.add_task(lambda: asyncio.run(update_task()))
    return {
        "message": f"Mise à jour des scores en arrière-plan démarrée (limite: {limit} artistes)"
    }

@router.get("/score-interpretation/{score}")
def get_score_interpretation(score: float):
    """Obtenir l'interprétation d'un score"""
    try:
        scoring_service = ScoringService()
        interpretation = scoring_service.get_score_interpretation(score)
        return interpretation
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'interprétation du score: {str(e)}")

@router.get("/weights")
def get_scoring_weights():
    """Récupérer les poids utilisés dans l'algorithme de scoring"""
    try:
        scoring_service = ScoringService()
        return {
            "weights": scoring_service.weights,
            "thresholds": scoring_service.thresholds
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des poids: {str(e)}")
