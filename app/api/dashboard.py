"""
Dashboard API JSON pour la gestion manuelle des processus de production
API pure pour déclencher les phases d'extraction et scoring
"""

from datetime import datetime
from typing import Any, Dict

from app.db.database import get_db
from app.services.artist_service import ArtistService
from app.services.scoring_service import ScoringService
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.post("/resume-tubebuddy-scoring")
def resume_tubebuddy_scoring(
    background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    """Reprendre les calculs TubeBuddy pour les artistes marqués needs_scoring=True"""
    try:
        import asyncio

        from app.services.process_manager import ProcessManager
        from app.services.tubebuddy_processor import TubeBuddyProcessor

        # Vérifier qu'aucun processus n'est en cours
        process_manager = ProcessManager(db)
        if process_manager.has_running_process():
            running = process_manager.get_running_process()
            raise HTTPException(
                status_code=409,
                detail=f"Un processus {running.process_type} est déjà en cours depuis {running.started_at}",
            )

        # Démarrer en arrière-plan
        async def tubebuddy_task():
            processor = TubeBuddyProcessor(db)
            await processor.run_async()

        background_tasks.add_task(lambda: asyncio.run(tubebuddy_task()))

        return {
            "message": "Calculs TubeBuddy démarrés en arrière-plan",
            "type": "tubebuddy",
            "status": "started",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erreur reprise calculs TubeBuddy: {str(e)}"
        )


@router.post("/stop-process")
def stop_current_process(db: Session = Depends(get_db)):
    """Arrêter le processus en cours et redémarrer le container"""
    try:
        import os
        import subprocess

        from app.services.process_manager import ProcessManager

        process_manager = ProcessManager(db)

        # Vérifier s'il y a un processus en cours
        if not process_manager.has_running_process():
            return {"message": "Aucun processus en cours", "status": "no_process"}

        running_process = process_manager.get_running_process()

        # Marquer le processus comme erreur en base
        process_manager.mark_process_failed(
            error_message="Processus arrêté manuellement par l'utilisateur"
        )

        print(f"[STOP] Processus {running_process.process_type} arrêté manuellement")

        return {
            "message": f"Processus {running_process.process_type} arrêté avec succès",
            "status": "stopped",
            "process_type": running_process.process_type,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur arrêt processus: {str(e)}")


@router.get("/process-status")
def get_process_status(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Récupérer le statut des processus de scoring"""
    try:
        from app.services.process_manager import ProcessManager

        artist_service = ArtistService(db)
        process_manager = ProcessManager(db)

        total_artists = artist_service.count_all_artists()
        artists_with_scores = artist_service.count_artists_with_scores()
        pending_scoring = artist_service.count_artists_needing_scoring()
        high_opportunities = artist_service.count_high_opportunities()

        current_process = process_manager.get_running_process()
        current_process_info = None
        if current_process:
            current_process_info = f"{current_process.process_type} ({current_process.progress_percentage}%)"

        return {
            "total_artists": total_artists,
            "artists_with_scores": artists_with_scores,
            "pending_scoring": pending_scoring,
            "high_opportunities": high_opportunities,
            "current_process": current_process_info,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erreur statut processus: {str(e)}"
        )


@router.get("/system-status")
def get_system_status(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Récupérer le statut général du système"""
    try:
        artist_service = ArtistService(db)

        # Top 5 artistes par score TubeBuddy
        top_artists = artist_service.get_top_artists_by_score(limit=10)
        total_artists = artist_service.count_all_artists()

        return {
            "top_artists": [
                {
                    "name": artist.name,
                    "overall_score": max(
                        [score.overall_score for score in artist.scores], default=0
                    ),
                }
                for artist in top_artists
            ],
            "total_artists": total_artists,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur statut système: {str(e)}")
