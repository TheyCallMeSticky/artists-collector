from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app.db.database import get_db
from app.services.collection_scheduler import CollectionScheduler
from app.services.scoring_service import ScoringService
from app.services.artist_service import ArtistService
from pydantic import BaseModel
import asyncio
import logging

logger = logging.getLogger(__name__)

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

@router.post("/calculate-pending")
async def calculate_pending_scores(limit: int = 400, db: Session = Depends(get_db)):
    """Calculer les scores pour tous les artistes en attente (needs_scoring=True)"""
    try:
        from app.models.artist import Artist
        from app.services.collection_scheduler import CollectionScheduler
        
        # Récupérer les artistes en attente de scoring par ordre de priorité
        artists_to_score = db.query(Artist).filter(
            Artist.needs_scoring == True
        ).order_by(
            # Priorité : nouveaux artistes d'abord, puis par date d'apparition récente
            Artist.score.is_(None).desc(),  # NULL score = nouveau (priorité max)
            Artist.most_recent_appearance.desc(),  # Plus récent = plus prioritaire
            Artist.created_at.asc()  # Plus ancien en création = priorité backlog
        ).limit(limit).all()
        
        if not artists_to_score:
            return {
                "message": "Aucun artiste en attente de scoring",
                "artists_processed": 0
            }
        
        scheduler = CollectionScheduler(db)
        processed_count = 0
        errors = []
        
        logger.info(f"Début du calcul de scores pour {len(artists_to_score)} artistes")
        
        for artist in artists_to_score:
            try:
                # Calculer le score TubeBuddy
                await scheduler._calculate_and_save_score(artist.id)
                
                # Marquer comme traité
                artist.needs_scoring = False
                db.commit()
                
                processed_count += 1
                logger.info(f"Score calculé pour {artist.name} (ID: {artist.id})")
                
            except Exception as e:
                error_msg = f"Erreur scoring {artist.name}: {str(e)}"
                errors.append(error_msg)
                logger.warning(error_msg)
                continue
        
        return {
            "message": f"Calcul des scores terminé",
            "artists_processed": processed_count,
            "total_requested": len(artists_to_score),
            "errors_count": len(errors),
            "errors": errors[:10]  # Limiter les erreurs affichées
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du calcul des scores en attente: {str(e)}")

@router.get("/pending-count")
def get_pending_count(db: Session = Depends(get_db)):
    """Récupérer le nombre d'artistes en attente de scoring"""
    try:
        from app.models.artist import Artist
        
        total_pending = db.query(Artist).filter(Artist.needs_scoring == True).count()
        new_artists = db.query(Artist).filter(
            Artist.needs_scoring == True,
            Artist.score.is_(None)
        ).count()
        
        return {
            "total_pending": total_pending,
            "new_artists": new_artists,
            "existing_to_update": total_pending - new_artists
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du comptage: {str(e)}")

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
