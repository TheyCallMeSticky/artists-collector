"""
Classe de base pour les processus asynchrones d'extraction et scoring
Factorisation du code commun entre Phase 1, Phase 2 et TubeBuddy
"""

from abc import ABC, abstractmethod
from sqlalchemy.orm import Session
from app.services.process_manager import ProcessManager
from app.models.process_status import ProcessStatus
from typing import Dict, Any, Optional
import logging
import asyncio

logger = logging.getLogger(__name__)

class BaseAsyncProcessor(ABC):
    """Classe de base pour tous les processus asynchrones"""
    
    def __init__(self, db: Session):
        self.db = db
        self.process_manager = ProcessManager(db)
        self.current_process: Optional[ProcessStatus] = None

    @abstractmethod
    def get_process_type(self) -> str:
        """Retourner le type de processus (phase1, phase2, tubebuddy)"""
        pass

    @abstractmethod
    async def execute_process(self) -> Dict[str, Any]:
        """Exécuter la logique métier du processus"""
        pass

    @abstractmethod
    def get_total_sources(self) -> int:
        """Retourner le nombre total de sources à traiter"""
        pass

    async def run_async(self) -> Dict[str, Any]:
        """Point d'entrée principal pour exécuter le processus de manière asynchrone"""
        try:
            # Vérifier qu'aucun processus n'est en cours
            if self.process_manager.has_running_process():
                running = self.process_manager.get_running_process()
                raise ValueError(f"Un processus {running.process_type} est déjà en cours depuis {running.started_at}")

            # Démarrer le processus
            self.current_process = self.process_manager.start_process(
                process_type=self.get_process_type(),
                total_sources=self.get_total_sources()
            )

            # Exécuter la logique métier
            result = await self.execute_process()

            # Marquer comme terminé avec succès
            self.process_manager.complete_process(
                self.current_process.id,
                result_data=result
            )

            return {
                "success": True,
                "process_id": self.current_process.id,
                "process_type": self.get_process_type(),
                **result
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Erreur dans {self.get_process_type()}: {error_msg}")

            # Marquer comme erreur si le processus a été créé
            if self.current_process:
                self.process_manager.complete_process(
                    self.current_process.id,
                    error_message=error_msg
                )

            return {
                "success": False,
                "error": error_msg,
                "process_id": self.current_process.id if self.current_process else None,
                "process_type": self.get_process_type()
            }

    def update_progress(self, **kwargs):
        """Mettre à jour la progression du processus en cours"""
        if self.current_process:
            self.process_manager.update_progress(self.current_process.id, **kwargs)

    def set_current_step(self, step: str):
        """Mettre à jour l'étape actuelle"""
        self.update_progress(current_step=step)

    def set_current_source(self, source: str):
        """Mettre à jour la source en cours de traitement"""
        self.update_progress(current_source=source)

    def increment_sources_processed(self):
        """Incrémenter le nombre de sources traitées"""
        if self.current_process:
            self.update_progress(sources_processed=self.current_process.sources_processed + 1)

    def increment_artists_processed(self, count: int = 1):
        """Incrémenter le nombre d'artistes traités"""
        if self.current_process:
            self.update_progress(artists_processed=self.current_process.artists_processed + count)

    def refresh_process_status(self):
        """Rafraîchir le statut du processus depuis la base de données"""
        if self.current_process:
            self.current_process = self.process_manager.get_process_status(self.current_process.id)

    @property
    def process_status(self) -> Optional[ProcessStatus]:
        """Getter pour accéder au statut du processus"""
        return self.current_process

    def increment_artists_saved(self, count: int = 1):
        """Incrémenter le nombre d'artistes sauvés"""
        if self.current_process:
            self.update_progress(artists_saved=self.current_process.artists_saved + count)

    def increment_new_artists(self, count: int = 1):
        """Incrémenter le nombre de nouveaux artistes"""
        if self.current_process:
            self.update_progress(new_artists=self.current_process.new_artists + count)

    def increment_updated_artists(self, count: int = 1):
        """Incrémenter le nombre d'artistes mis à jour"""
        if self.current_process:
            self.update_progress(updated_artists=self.current_process.updated_artists + count)

    def increment_errors(self, count: int = 1):
        """Incrémenter le nombre d'erreurs"""
        if self.current_process:
            self.update_progress(errors_count=self.current_process.errors_count + count)

    def log_progress(self, message: str):
        """Logger la progression avec le contexte du processus"""
        process_info = f"[{self.get_process_type().upper()}]"
        if self.current_process:
            process_info += f"[ID:{self.current_process.id}]"
        logger.info(f"{process_info} {message}")

    def get_current_status(self) -> Optional[Dict[str, Any]]:
        """Récupérer le statut actuel du processus"""
        if self.current_process:
            # Rafraîchir depuis la base
            self.db.refresh(self.current_process)
            return self.current_process.to_dict()
        return None
