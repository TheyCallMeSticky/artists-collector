"""
Service de gestion des processus asynchrones
Gère le statut, la progression et la coordination des processus d'extraction et scoring
"""

from sqlalchemy.orm import Session
from app.models.process_status import ProcessStatus
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class ProcessManager:
    def __init__(self, db: Session):
        self.db = db

    def start_process(self, process_type: str, total_sources: int = 0) -> ProcessStatus:
        """Démarrer un nouveau processus"""
        # Vérifier qu'aucun processus n'est en cours
        if self.has_running_process():
            running = self.get_running_process()
            raise ValueError(f"Un processus {running.process_type} est déjà en cours")

        # Créer le nouveau processus
        process = ProcessStatus(
            process_type=process_type,
            status="running",
            current_step="Initialisation...",
            total_sources=total_sources,
            sources_processed=0,
            artists_processed=0,
            artists_saved=0,
            new_artists=0,
            updated_artists=0,
            errors_count=0
        )
        
        self.db.add(process)
        self.db.commit()
        self.db.refresh(process)
        
        logger.info(f"Processus {process_type} démarré (ID: {process.id})")
        return process

    def get_running_process(self) -> Optional[ProcessStatus]:
        """Récupérer le processus en cours"""
        return ProcessStatus.get_running_process(self.db)

    def has_running_process(self) -> bool:
        """Vérifier s'il y a un processus en cours"""
        return ProcessStatus.has_running_process(self.db)

    def update_progress(self, process_id: int, **kwargs) -> ProcessStatus:
        """Mettre à jour la progression d'un processus"""
        process = self.db.query(ProcessStatus).filter(ProcessStatus.id == process_id).first()
        if not process:
            raise ValueError(f"Processus {process_id} non trouvé")

        process.update_progress(self.db, **kwargs)
        return process

    def complete_process(self, process_id: int, result_data: Dict[str, Any] = None, error_message: str = None) -> ProcessStatus:
        """Marquer un processus comme terminé"""
        process = self.db.query(ProcessStatus).filter(ProcessStatus.id == process_id).first()
        if not process:
            raise ValueError(f"Processus {process_id} non trouvé")

        process.complete(self.db, result_data=result_data, error_message=error_message)
        logger.info(f"Processus {process.process_type} terminé (ID: {process.id})")
        return process

    def cancel_process(self, process_id: int) -> ProcessStatus:
        """Annuler un processus"""
        process = self.db.query(ProcessStatus).filter(ProcessStatus.id == process_id).first()
        if not process:
            raise ValueError(f"Processus {process_id} non trouvé")

        process.status = "cancelled"
        process.current_step = "Annulé"

    def mark_process_failed(self, error_message: str = None) -> Optional[ProcessStatus]:
        """Marquer le processus en cours comme échoué"""
        process = self.get_running_process()
        if not process:
            return None

        process.complete(self.db, error_message=error_message or "Processus arrêté manuellement")
        logger.info(f"Processus {process.process_type} marqué comme échoué (ID: {process.id})")
        return process

    def get_process_status(self, process_id: int = None) -> Optional[ProcessStatus]:
        """Récupérer le statut d'un processus (ou le processus en cours si pas d'ID)"""
        if process_id:
            return self.db.query(ProcessStatus).filter(ProcessStatus.id == process_id).first()
        else:
            return self.get_running_process()

    def get_latest_process(self, process_type: str = None) -> Optional[ProcessStatus]:
        """Récupérer le dernier processus (optionnellement d'un type spécifique)"""
        query = self.db.query(ProcessStatus).order_by(ProcessStatus.started_at.desc())
        
        if process_type:
            query = query.filter(ProcessStatus.process_type == process_type)
            
        return query.first()

    def get_process_history(self, limit: int = 10) -> list[ProcessStatus]:
        """Récupérer l'historique des processus"""
        return self.db.query(ProcessStatus).order_by(
            ProcessStatus.started_at.desc()
        ).limit(limit).all()

    def cleanup_old_processes(self, keep_days: int = 7):
        """Nettoyer les anciens processus"""
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        
        deleted = self.db.query(ProcessStatus).filter(
            ProcessStatus.started_at < cutoff_date,
            ProcessStatus.status.in_(["completed", "error", "cancelled"])
        ).delete()
        
        self.db.commit()
        logger.info(f"Nettoyage: {deleted} anciens processus supprimés")
        return deleted
