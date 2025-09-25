"""
Processeur asynchrone pour le scoring TubeBuddy
"""

from app.services.base_async_processor import BaseAsyncProcessor
from app.services.scoring_service import ScoringService
from app.services.artist_service import ArtistService
from app.models.artist import Artist
from app.schemas.artist import ScoreCreate
from typing import Dict, Any
import asyncio

class TubeBuddyProcessor(BaseAsyncProcessor):
    """Processeur pour le scoring TubeBuddy"""

    def get_process_type(self) -> str:
        return "tubebuddy"

    def get_total_sources(self) -> int:
        """Calculer le nombre total d'artistes à scorer"""
        try:
            artist_service = ArtistService(self.db)
            return artist_service.count_artists_needing_scoring()
        except Exception as e:
            self.log_progress(f"Erreur calcul artistes: {e}")
            return 0

    async def execute_process(self) -> Dict[str, Any]:
        """Exécuter le scoring TubeBuddy"""
        self.set_current_step("Initialisation du scoring TubeBuddy...")
        
        # Services
        artist_service = ArtistService(self.db)
        scoring_service = ScoringService()
        
        # Récupérer les artistes en attente de scoring
        pending_artists = artist_service.get_artists_needing_scoring()
        
        if not pending_artists:
            self.set_current_step("Aucun artiste en attente de scoring")
            return {
                "message": "Aucun artiste en attente de calcul TubeBuddy",
                "total_artists": 0,
                "completed": 0,
                "remaining": 0,
                "artists_found": 0,
                "artists_saved": 0
            }

        # Mettre à jour le total
        self.update_progress(total_sources=len(pending_artists))
        
        self.set_current_step("Calcul des scores TubeBuddy en cours...")
        
        # Traiter par batch pour éviter surcharge mémoire
        batch_size = 20
        completed_count = 0
        errors = []

        for i in range(0, len(pending_artists), batch_size):
            batch = pending_artists[i:i + batch_size]
            
            self.set_current_step(f"Traitement batch {i//batch_size + 1}/{(len(pending_artists)-1)//batch_size + 1}")
            
            # Traiter le batch
            batch_results = await self._process_batch(batch, scoring_service, artist_service)
            
            completed_count += batch_results["completed"]
            errors.extend(batch_results["errors"])
            
            # Mettre à jour la progression
            self.update_progress(
                sources_processed=min(i + batch_size, len(pending_artists)),
                artists_processed=completed_count,
                artists_saved=completed_count,
                errors_count=len(errors)
            )
            
            self.log_progress(f"Batch terminé: {batch_results['completed']}/{len(batch)} artistes scorés")

        self.set_current_step("Scoring TubeBuddy terminé")
        
        result = {
            "message": "Calculs TubeBuddy terminés",
            "total_artists": len(pending_artists),
            "completed": completed_count,
            "remaining": len(pending_artists) - completed_count,
            "errors_count": len(errors),
            "errors": errors[:10],  # Limiter les erreurs affichées
            "artists_found": len(pending_artists),
            "artists_saved": completed_count
        }
        
        self.log_progress(f"TubeBuddy terminé: {completed_count}/{len(pending_artists)} artistes scorés")
        
        return result

    async def _process_batch(self, batch: list[Artist], scoring_service: ScoringService, artist_service: ArtistService) -> Dict[str, Any]:
        """Traiter un batch d'artistes"""
        completed = 0
        errors = []
        
        for artist in batch:
            try:
                self.set_current_source(f"Scoring: {artist.name}")
                
                # Calculer le score TubeBuddy
                score_data = await scoring_service.score_artist(artist.name)
                
                if "error" not in score_data:
                    # Créer et sauvegarder le score
                    score_create = ScoreCreate(
                        artist_id=artist.id,
                        algorithm_name="TubeBuddy",
                        search_volume_score=int(score_data.get("search_volume_score", 0)),
                        competition_score=int(score_data.get("competition_score", 0)),
                        optimization_score=int(score_data.get("optimization_score", 0)),
                        overall_score=int(score_data.get("overall_score", 0)),
                        score_data=score_data
                    )
                    artist_service.create_score(score_create)

                    # Marquer comme traité
                    artist.needs_scoring = False
                    self.db.commit()
                    
                    completed += 1
                    self.log_progress(f"Score calculé pour {artist.name}: {score_data.get('overall_score', 0)}")
                else:
                    error_msg = f"Erreur scoring {artist.name}: {score_data.get('error', 'Erreur inconnue')}"
                    errors.append(error_msg)
                    self.log_progress(error_msg)

            except Exception as e:
                error_msg = f"Erreur scoring {artist.name}: {str(e)}"
                errors.append(error_msg)
                self.log_progress(error_msg)
                
                # En cas d'erreur quota, arrêter le traitement
                if "quota" in str(e).lower() or "rate limit" in str(e).lower():
                    self.log_progress("Quota épuisé, arrêt du batch")
                    break

        return {
            "completed": completed,
            "errors": errors
        }
