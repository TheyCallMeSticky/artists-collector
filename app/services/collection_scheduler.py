import asyncio
import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.services.data_collector import DataCollector
from app.services.scoring_service import ScoringService
from app.services.artist_service import ArtistService
from app.schemas.artist import ScoreCreate
import json

logger = logging.getLogger(__name__)

class CollectionScheduler:
    def __init__(self, db: Session):
        self.db = db
        self.data_collector = DataCollector(db)
        self.scoring_service = ScoringService()
        self.artist_service = ArtistService(db)

    async def collect_artists_batch(self, artist_names: List[str]) -> Dict[str, Any]:
        """Collecter un lot d'artistes de manière asynchrone"""
        results = {
            'total_artists': len(artist_names),
            'successful_collections': 0,
            'failed_collections': 0,
            'artists_processed': [],
            'errors': []
        }
        
        logger.info(f"Début de la collecte pour {len(artist_names)} artistes")
        
        for artist_name in artist_names:
            try:
                # Collecter les données
                collection_result = self.data_collector.collect_and_save_artist(artist_name)
                
                if collection_result['success'] and collection_result.get('artist_id'):
                    # Calculer et sauvegarder le score
                    await self._calculate_and_save_score(collection_result['artist_id'])
                    results['successful_collections'] += 1
                    
                    results['artists_processed'].append({
                        'name': artist_name,
                        'artist_id': collection_result['artist_id'],
                        'status': 'success',
                        'spotify_collected': bool(collection_result.get('spotify_data')),
                        'youtube_collected': bool(collection_result.get('youtube_data'))
                    })
                else:
                    results['failed_collections'] += 1
                    results['artists_processed'].append({
                        'name': artist_name,
                        'status': 'failed',
                        'errors': collection_result.get('errors', [])
                    })
                
                # Pause entre les collectes pour respecter les limites d'API
                await asyncio.sleep(2)
                
            except Exception as e:
                error_msg = f"Erreur lors de la collecte de {artist_name}: {str(e)}"
                logger.error(error_msg)
                results['failed_collections'] += 1
                results['errors'].append(error_msg)
                
                results['artists_processed'].append({
                    'name': artist_name,
                    'status': 'error',
                    'error': str(e)
                })
        
        logger.info(f"Collecte terminée: {results['successful_collections']} succès, {results['failed_collections']} échecs")
        return results

    async def _calculate_and_save_score(self, artist_id: int):
        """Calculer et sauvegarder le score d'un artiste"""
        try:
            # Récupérer les données de l'artiste
            artist = self.artist_service.get_artist(artist_id)
            if not artist:
                logger.error(f"Artiste {artist_id} non trouvé")
                return
            
            # Préparer les données pour le scoring
            artist_data = {
                'spotify_popularity': artist.spotify_popularity,
                'spotify_followers': artist.spotify_followers,
                'youtube_subscribers': artist.youtube_subscribers,
                'youtube_views': artist.youtube_views,
                'youtube_videos_count': artist.youtube_videos_count
            }
            
            # Calculer le score
            score_result = await self.scoring_service.calculate_artist_score(artist_data['name'])
            final_score = score_result['final_score']
            
            # Mettre à jour le score de l'artiste
            from app.schemas.artist import ArtistUpdate
            artist_update = ArtistUpdate(score=final_score)
            self.artist_service.update_artist(artist_id, artist_update)
            
            # Sauvegarder le détail du score
            score_create = ScoreCreate(
                artist_id=artist_id,
                score_value=final_score,
                score_breakdown=json.dumps(score_result)
            )
            self.artist_service.create_score(score_create)
            
            logger.info(f"Score calculé pour l'artiste {artist_id}: {final_score}")
            
        except Exception as e:
            logger.error(f"Erreur lors du calcul du score pour l'artiste {artist_id}: {str(e)}")

    async def update_existing_artists_scores(self, limit: int = 100) -> Dict[str, Any]:
        """Mettre à jour les scores des artistes existants"""
        results = {
            'total_artists': 0,
            'updated_scores': 0,
            'errors': []
        }
        
        try:
            # Récupérer les artistes actifs
            artists = self.artist_service.get_artists(limit=limit)
            results['total_artists'] = len(artists)
            
            for artist in artists:
                try:
                    await self._calculate_and_save_score(artist.id)
                    results['updated_scores'] += 1
                    
                    # Pause entre les calculs
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    error_msg = f"Erreur mise à jour score artiste {artist.id}: {str(e)}"
                    logger.error(error_msg)
                    results['errors'].append(error_msg)
            
            logger.info(f"Mise à jour des scores terminée: {results['updated_scores']} artistes mis à jour")
            
        except Exception as e:
            error_msg = f"Erreur lors de la mise à jour des scores: {str(e)}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
        
        return results

    def get_top_opportunities(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Récupérer les meilleures opportunités d'artistes basées sur les scores TubeBuddy"""
        try:
            from app.models.artist import Artist, Score
            from sqlalchemy.orm import joinedload

            # Récupérer les artistes avec leurs meilleurs scores TubeBuddy
            query = self.db.query(Artist).join(Score).filter(
                Artist.is_active == True,
                Score.algorithm_name == "TubeBuddy"
            ).options(joinedload(Artist.scores)).order_by(
                Score.overall_score.desc()
            ).limit(limit)

            top_artists = query.all()
            opportunities = []

            for artist in top_artists:
                # Récupérer le meilleur score TubeBuddy pour cet artiste
                tubebuddy_scores = [s for s in artist.scores if s.algorithm_name == "TubeBuddy"]
                if not tubebuddy_scores:
                    continue

                best_score = max(tubebuddy_scores, key=lambda s: s.overall_score)

                # Interpréter le score
                interpretation = self.scoring_service.get_score_interpretation(best_score.overall_score)

                opportunities.append({
                    'artist_id': artist.id,
                    'name': artist.name,
                    'score': best_score.overall_score,
                    'tubebuddy_details': {
                        'search_volume_score': best_score.search_volume_score,
                        'competition_score': best_score.competition_score,
                        'optimization_score': best_score.optimization_score,
                        'overall_score': best_score.overall_score
                    },
                    'category': interpretation['category'],
                    'recommendation': interpretation['recommendation'],
                    'spotify_id': artist.spotify_id,
                    'youtube_channel_id': artist.youtube_channel_id,
                    'spotify_followers': artist.spotify_followers,
                    'youtube_subscribers': artist.youtube_subscribers,
                    'spotify_popularity': artist.spotify_popularity,
                    'updated_at': artist.updated_at.isoformat() if artist.updated_at else None,
                    'score_date': best_score.created_at.isoformat() if best_score.created_at else None
                })

            return opportunities

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des opportunités: {str(e)}")
            return []

    async def refresh_artist_data(self, artist_id: int) -> Dict[str, Any]:
        """Rafraîchir les données d'un artiste spécifique"""
        try:
            artist = self.artist_service.get_artist(artist_id)
            if not artist:
                return {'success': False, 'error': 'Artiste non trouvé'}
            
            # Re-collecter les données
            collection_result = self.data_collector.collect_and_save_artist(artist.name)
            
            if collection_result['success']:
                # Recalculer le score
                await self._calculate_and_save_score(artist_id)
                
                return {
                    'success': True,
                    'artist_id': artist_id,
                    'artist_name': artist.name,
                    'spotify_updated': bool(collection_result.get('spotify_data')),
                    'youtube_updated': bool(collection_result.get('youtube_data'))
                }
            else:
                return {
                    'success': False,
                    'artist_id': artist_id,
                    'artist_name': artist.name,
                    'errors': collection_result.get('errors', [])
                }
                
        except Exception as e:
            logger.error(f"Erreur lors du rafraîchissement de l'artiste {artist_id}: {str(e)}")
            return {'success': False, 'error': str(e)}
