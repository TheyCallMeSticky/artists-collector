"""
Processeur asynchrone pour la Phase 2 - Extraction hebdomadaire
"""

from app.services.base_async_processor import BaseAsyncProcessor
from app.services.source_extractor import SourceExtractor
from typing import Dict, Any
import asyncio

class Phase2Processor(BaseAsyncProcessor):
    """Processeur pour la Phase 2 - Extraction hebdomadaire"""

    def get_process_type(self) -> str:
        return "phase2"

    def get_total_sources(self) -> int:
        """Calculer le nombre total de sources à traiter"""
        try:
            extractor = SourceExtractor(self.db)
            sources = extractor.sources_config
            
            spotify_count = len(sources.get("spotify_playlists", []))
            youtube_count = len(sources.get("youtube_channels", []))
            
            return spotify_count + youtube_count
        except Exception as e:
            self.log_progress(f"Erreur calcul sources: {e}")
            return 0

    async def execute_process(self) -> Dict[str, Any]:
        """Exécuter la Phase 2 - Extraction hebdomadaire"""
        self.set_current_step("Initialisation de l'extraction hebdomadaire...")
        
        # Créer l'extracteur
        extractor = SourceExtractor(self.db)
        
        # Configurer les callbacks pour le suivi de progression
        extractor.set_progress_callback(self._on_source_progress)
        extractor.set_artist_callback(self._on_artist_progress)
        
        self.set_current_step("Extraction des nouveautés en cours...")
        
        # Exécuter l'extraction hebdomadaire
        results = extractor.run_weekly_extraction()
        
        self.set_current_step("Finalisation...")
        
        # Mettre à jour les statistiques finales
        self.update_progress(
            artists_saved=results.get("artists_saved", 0),
            new_artists=results.get("new_artists", 0),
            updated_artists=results.get("updated_artists", 0),
            current_step="Extraction hebdomadaire terminée"
        )
        
        self.log_progress(f"Phase 2 terminée: {results.get('artists_found', 0)} artistes trouvés")
        
        return results

    def _on_source_progress(self, source_name: str, source_type: str):
        """Callback appelé quand une source commence à être traitée"""
        self.set_current_source(f"{source_type}: {source_name}")
        self.increment_sources_processed()
        self.log_progress(f"Traitement de {source_type}: {source_name}")

    def _on_artist_progress(self, artist_name: str, is_new: bool, is_updated: bool):
        """Callback appelé quand un artiste est traité"""
        self.increment_artists_processed()
        
        if is_new:
            self.increment_new_artists()
            self.increment_artists_saved()
        elif is_updated:
            self.increment_updated_artists()
            self.increment_artists_saved()
