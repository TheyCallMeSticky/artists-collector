"""
API d'extraction refactorisée avec processeurs asynchrones
"""

import asyncio
from typing import Any, Dict, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.phase1_processor import Phase1Processor
from app.services.phase2_processor import Phase2Processor
from app.services.tubebuddy_processor import TubeBuddyProcessor
from app.services.process_manager import ProcessManager
from app.services.youtube_service import YouTubeService

router = APIRouter(prefix="/extraction", tags=["extraction"])

class ProcessStatusResponse(BaseModel):
    """Réponse de statut de processus"""
    id: Optional[int] = None
    process_type: Optional[str] = None
    status: str
    progress_percentage: int = 0
    current_step: Optional[str] = None
    sources_processed: int = 0
    total_sources: int = 0
    artists_processed: int = 0
    artists_saved: int = 0
    new_artists: int = 0
    updated_artists: int = 0
    errors_count: int = 0
    current_source: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    last_update: Optional[str] = None
    is_active: bool = False

class YouTubeQuotaResponse(BaseModel):
    """Réponse de statut quota YouTube"""
    status: str
    current_key_index: int
    total_keys: int
    quota_exceeded: bool
    last_reset: Optional[str] = None

@router.get("/status", response_model=ProcessStatusResponse)
def get_extraction_status(db: Session = Depends(get_db)):
    """Récupérer le statut actuel de l'extraction"""
    try:
        process_manager = ProcessManager(db)
        current_process = process_manager.get_running_process()
        
        if current_process:
            return ProcessStatusResponse(**current_process.to_dict())
        else:
            # Récupérer le dernier processus terminé
            latest = process_manager.get_latest_process()
            if latest:
                return ProcessStatusResponse(**latest.to_dict())
            else:
                return ProcessStatusResponse(status="idle")
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur récupération statut: {str(e)}")

@router.post("/phase1-background")
def run_phase1_background(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    🚀 PHASE 1 COMPLÈTE en arrière-plan:
    - Extraction des 50 dernières vidéos de chaque chaîne YouTube
    - Extraction totale des playlists Spotify
    - Collecte métadonnées Spotify enrichies
    """
    try:
        # Vérifier qu'aucun processus n'est en cours
        process_manager = ProcessManager(db)
        if process_manager.has_running_process():
            running = process_manager.get_running_process()
            raise HTTPException(
                status_code=409, 
                detail=f"Un processus {running.process_type} est déjà en cours depuis {running.started_at}"
            )

        # Démarrer en arrière-plan
        async def phase1_task():
            processor = Phase1Processor(db)
            await processor.run_async()

        background_tasks.add_task(lambda: asyncio.run(phase1_task()))
        
        return {
            "message": "Phase 1 complète démarrée en arrière-plan",
            "type": "phase1",
            "status": "started"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erreur lors du démarrage de la Phase 1: {str(e)}"
        )

@router.post("/phase2-background")
def run_phase2_background(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    🔄 PHASE 2 HEBDOMADAIRE en arrière-plan:
    - Extraction incrémentale des nouveaux contenus (7 derniers jours)
    - Re-scoring intelligent des artistes avec nouveau contenu
    - Mise à jour des métriques Spotify/YouTube
    """
    try:
        # Vérifier qu'aucun processus n'est en cours
        process_manager = ProcessManager(db)
        if process_manager.has_running_process():
            running = process_manager.get_running_process()
            raise HTTPException(
                status_code=409, 
                detail=f"Un processus {running.process_type} est déjà en cours depuis {running.started_at}"
            )

        # Démarrer en arrière-plan
        async def phase2_task():
            processor = Phase2Processor(db)
            await processor.run_async()

        background_tasks.add_task(lambda: asyncio.run(phase2_task()))
        
        return {
            "message": "Phase 2 hebdomadaire démarrée en arrière-plan",
            "type": "phase2",
            "status": "started"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erreur lors du démarrage de la Phase 2: {str(e)}"
        )

@router.post("/resume-tubebuddy")
def resume_tubebuddy_background(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    📊 REPRENDRE SCORING TUBEBUDDY en arrière-plan:
    - Calcul des scores pour les artistes en attente
    - Traitement par batch pour éviter surcharge
    - Gestion automatique des quotas API
    """
    try:
        # Vérifier qu'aucun processus n'est en cours
        process_manager = ProcessManager(db)
        if process_manager.has_running_process():
            running = process_manager.get_running_process()
            raise HTTPException(
                status_code=409, 
                detail=f"Un processus {running.process_type} est déjà en cours depuis {running.started_at}"
            )

        # Démarrer en arrière-plan
        async def tubebuddy_task():
            processor = TubeBuddyProcessor(db)
            await processor.run_async()

        background_tasks.add_task(lambda: asyncio.run(tubebuddy_task()))
        
        return {
            "message": "Scoring TubeBuddy démarré en arrière-plan",
            "type": "tubebuddy",
            "status": "started"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erreur lors du démarrage TubeBuddy: {str(e)}"
        )

@router.get("/youtube-quota", response_model=YouTubeQuotaResponse)
def get_youtube_quota_status():
    """Récupérer le statut du quota YouTube"""
    try:
        youtube_service = YouTubeService()
        status = youtube_service.get_quota_status()
        
        return YouTubeQuotaResponse(
            status="ok" if not status.get("quota_exceeded", False) else "quota_exceeded",
            current_key_index=status.get("current_key_index", 0),
            total_keys=status.get("total_keys", 1),
            quota_exceeded=status.get("quota_exceeded", False),
            last_reset=status.get("last_reset")
        )
        
    except Exception as e:
        return YouTubeQuotaResponse(
            status="error",
            current_key_index=0,
            total_keys=0,
            quota_exceeded=True
        )

@router.post("/youtube-reset")
def reset_youtube_keys():
    """Réinitialiser les clés YouTube"""
    try:
        youtube_service = YouTubeService()
        youtube_service.reset_quota()
        
        return {
            "message": "Clés YouTube réinitialisées",
            "status": "reset"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erreur lors de la réinitialisation: {str(e)}"
        )

@router.post("/cancel/{process_id}")
def cancel_process(process_id: int, db: Session = Depends(get_db)):
    """Annuler un processus en cours"""
    try:
        process_manager = ProcessManager(db)
        process = process_manager.cancel_process(process_id)
        
        return {
            "message": f"Processus {process.process_type} annulé",
            "process_id": process_id,
            "status": "cancelled"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erreur lors de l'annulation: {str(e)}"
        )

@router.get("/history")
def get_process_history(limit: int = 10, db: Session = Depends(get_db)):
    """Récupérer l'historique des processus"""
    try:
        process_manager = ProcessManager(db)
        history = process_manager.get_process_history(limit=limit)
        
        return {
            "history": [process.to_dict() for process in history],
            "total": len(history)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erreur récupération historique: {str(e)}"
        )
