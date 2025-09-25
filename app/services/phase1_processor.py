"""
Processeur asynchrone pour la Phase 1 - Extraction complète
"""

from app.services.base_async_processor import BaseAsyncProcessor
from app.services.source_extractor import SourceExtractor
from typing import Dict, Any

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
        extractor.set_artist_callback(self._on_artist_found)
        extractor.set_save_progress_callback(self._on_save_progress)
        
        # Étape 1 : Extraction des sources (0-80%)
        self.set_current_step("Extraction des sources...")

        # Exécuter l'extraction complète
        results = extractor.run_full_extraction(limit_priority=400)

        # Les stats finales sont déjà mises à jour par les callbacks pendant l'exécution

        self.log_progress(f"Phase 1 terminée: {results.get('artists_found', 0)} artistes trouvés, {results.get('artists_saved', 0)} traités en base")

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

    def _on_artist_found(self, artist_name: str, is_new: bool, is_updated: bool):
        """Callback appelé quand un artiste est découvert (pendant extraction) ou sauvé (pendant sauvegarde)"""
        # Ne compter que les artistes trouvés pendant l'extraction (is_new=False, is_updated=False)
        # Les stats de sauvegarde sont gérées par _on_save_progress pour éviter trop de commits DB
        if not is_new and not is_updated:
            # Artiste trouvé pendant l'extraction des sources
            self.increment_artists_processed()

    def _on_save_progress(self, current: int, total: int, progress_percentage: int, batch_stats: dict = None):
        """Callback appelé pendant la sauvegarde des artistes"""
        update_data = {
            "progress_percentage": progress_percentage,
            "current_step": f"Sauvegarde et enrichissement ({current}/{total} artistes)..."
        }

        # Mettre à jour les statistiques d'artistes si fournies
        if batch_stats:
            if "artists_processed" in batch_stats:
                update_data["artists_processed"] = batch_stats["artists_processed"]
            if "artists_saved" in batch_stats:
                update_data["artists_saved"] = batch_stats["artists_saved"]
            if "new_artists" in batch_stats:
                update_data["new_artists"] = batch_stats["new_artists"]
            if "updated_artists" in batch_stats:
                update_data["updated_artists"] = batch_stats["updated_artists"]

        self.update_progress(**update_data)
