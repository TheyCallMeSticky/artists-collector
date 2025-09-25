"""
Processeur asynchrone pour la Phase 1 - Extraction complète
"""

from app.services.base_async_processor import BaseAsyncProcessor
from app.services.source_extractor import SourceExtractor
from typing import Dict, Any
import asyncio

class Phase1Processor(BaseAsyncProcessor):
    """Processeur pour la Phase 1 - Extraction complète"""

    def get_process_type(self) -> str:
        return "phase1"

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
        """Exécuter la Phase 1 - Extraction complète"""
        self.set_current_step("Initialisation de l'extraction complète...")
        
        # Créer l'extracteur
        extractor = SourceExtractor(self.db)
        
        # Configurer les callbacks pour le suivi de progression
        extractor.set_progress_callback(self._on_source_progress)
        extractor.set_artist_callback(self._on_artist_progress)
        
        # Étape 1 : Extraction des sources (0-80%)
        self.set_current_step("Extraction des sources...")

        # Exécuter l'extraction complète
        results = extractor.run_full_extraction(limit_priority=400)

        # Étape 2 : Sauvegarde en base (80-90%)
        self.update_progress(
            progress_percentage=80,
            current_step="Sauvegarde en base de données..."
        )

        # Étape 3 : Enrichissement Spotify (90-100%)
        self.update_progress(
            progress_percentage=90,
            current_step="Enrichissement des métadonnées Spotify..."
        )

        # Étape finale : Terminé (100%)
        self.update_progress(
            progress_percentage=100,
            artists_saved=results.get("artists_saved", 0),
            new_artists=results.get("new_artists", 0),
            updated_artists=results.get("updated_artists", 0),
            current_step="Extraction complète terminée"
        )
        
        self.log_progress(f"Phase 1 terminée: {results.get('artists_found', 0)} artistes trouvés")
        
        return results

    def _on_source_progress(self, source_name: str, source_type: str):
        """Callback appelé quand une source commence à être traitée"""
        self.set_current_source(f"{source_type}: {source_name}")

        # Incrémenter et calculer le pourcentage jusqu'à 80% max pour l'extraction
        if self.current_process:
            new_sources_processed = self.current_process.sources_processed + 1
            total_sources = self.get_total_sources()

            # Limiter la progression de l'extraction à 80%
            extraction_progress = min(80, int((new_sources_processed / total_sources) * 80))

            self.update_progress(
                sources_processed=new_sources_processed,
                progress_percentage=extraction_progress
            )

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
