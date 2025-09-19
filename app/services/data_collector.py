import logging
import json
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.services.spotify_service import SpotifyService
from app.services.youtube_service import YouTubeService
from app.services.artist_service import ArtistService
from app.schemas.artist import ArtistCreate, ArtistUpdate, CollectionLogCreate

logger = logging.getLogger(__name__)

class DataCollector:
    def __init__(self, db: Session):
        self.db = db
        self.spotify_service = SpotifyService()
        self.youtube_service = YouTubeService()
        self.artist_service = ArtistService(db)

    def collect_artist_data(self, artist_name: str) -> Optional[Dict[str, Any]]:
        """Collecter les données d'un artiste depuis Spotify et YouTube"""
        logger.info(f"Début de la collecte pour l'artiste: {artist_name}")
        
        result = {
            'artist_name': artist_name,
            'spotify_data': None,
            'youtube_data': None,
            'success': False,
            'errors': []
        }
        
        # Collecter les données Spotify
        try:
            spotify_data = self.spotify_service.collect_artist_data(artist_name)
            if spotify_data:
                result['spotify_data'] = spotify_data
                logger.info(f"Données Spotify collectées pour {artist_name}")
            else:
                result['errors'].append("Aucune donnée Spotify trouvée")
        except Exception as e:
            error_msg = f"Erreur lors de la collecte Spotify: {str(e)}"
            result['errors'].append(error_msg)
            logger.error(error_msg)

        # Collecter les données YouTube
        try:
            youtube_data = self.youtube_service.collect_artist_data(artist_name)
            if youtube_data:
                result['youtube_data'] = youtube_data
                logger.info(f"Données YouTube collectées pour {artist_name}")
            else:
                result['errors'].append("Aucune donnée YouTube trouvée")
        except Exception as e:
            error_msg = f"Erreur lors de la collecte YouTube: {str(e)}"
            result['errors'].append(error_msg)
            logger.error(error_msg)

        # Marquer comme succès si au moins une source a des données
        result['success'] = bool(result['spotify_data'] or result['youtube_data'])
        
        return result

    def save_artist_data(self, collection_result: Dict[str, Any]) -> Optional[int]:
        """Sauvegarder les données collectées dans la base de données"""
        if not collection_result['success']:
            logger.warning(f"Aucune donnée à sauvegarder pour {collection_result['artist_name']}")
            return None

        try:
            artist_name = collection_result['artist_name']
            spotify_data = collection_result.get('spotify_data')
            youtube_data = collection_result.get('youtube_data')

            # Vérifier si l'artiste existe déjà
            existing_artist = None
            if spotify_data and spotify_data.get('spotify_id'):
                existing_artist = self.artist_service.get_artist_by_spotify_id(spotify_data['spotify_id'])
            
            if not existing_artist and youtube_data and youtube_data.get('channel_id'):
                existing_artist = self.artist_service.get_artist_by_youtube_id(youtube_data['channel_id'])

            if existing_artist:
                # Mettre à jour l'artiste existant
                artist_id = self._update_existing_artist(existing_artist.id, spotify_data, youtube_data)
            else:
                # Créer un nouvel artiste
                artist_id = self._create_new_artist(artist_name, spotify_data, youtube_data)

            # Enregistrer les logs de collecte
            self._log_collection_results(artist_id, collection_result)

            return artist_id

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des données: {str(e)}")
            return None

    def _create_new_artist(self, artist_name: str, spotify_data: Dict, youtube_data: Dict) -> int:
        """Créer un nouvel artiste dans la base de données"""
        artist_create = ArtistCreate(
            name=artist_name,
            spotify_id=spotify_data.get('spotify_id') if spotify_data else None,
            youtube_channel_id=youtube_data.get('channel_id') if youtube_data else None
        )
        
        new_artist = self.artist_service.create_artist(artist_create)
        
        # Mettre à jour avec les données collectées
        self._update_artist_metrics(new_artist.id, spotify_data, youtube_data)
        
        return new_artist.id

    def _update_existing_artist(self, artist_id: int, spotify_data: Dict, youtube_data: Dict) -> int:
        """Mettre à jour un artiste existant"""
        self._update_artist_metrics(artist_id, spotify_data, youtube_data)
        return artist_id

    def _update_artist_metrics(self, artist_id: int, spotify_data: Dict, youtube_data: Dict):
        """Mettre à jour les métriques d'un artiste"""
        update_data = {}

        # Données Spotify
        if spotify_data and spotify_data.get('artist_info'):
            artist_info = spotify_data['artist_info']
            update_data.update({
                'spotify_followers': artist_info.get('followers', 0),
                'spotify_popularity': artist_info.get('popularity', 0),
                'spotify_id': artist_info.get('id')
            })

        # Données YouTube
        if youtube_data and youtube_data.get('channel_info'):
            channel_info = youtube_data['channel_info']
            update_data.update({
                'youtube_subscribers': channel_info.get('subscriber_count', 0),
                'youtube_views': channel_info.get('view_count', 0),
                'youtube_videos_count': channel_info.get('video_count', 0),
                'youtube_channel_id': channel_info.get('channel_id')
            })

        if update_data:
            artist_update = ArtistUpdate(**update_data)
            self.artist_service.update_artist(artist_id, artist_update)

    def _log_collection_results(self, artist_id: int, collection_result: Dict[str, Any]):
        """Enregistrer les logs de collecte"""
        # Log Spotify
        if collection_result.get('spotify_data'):
            log_data = CollectionLogCreate(
                artist_id=artist_id,
                collection_type='spotify',
                status='success',
                data_collected=json.dumps(collection_result['spotify_data'])
            )
            self.artist_service.log_collection(log_data)
        elif 'Aucune donnée Spotify trouvée' in collection_result.get('errors', []):
            log_data = CollectionLogCreate(
                artist_id=artist_id,
                collection_type='spotify',
                status='error',
                error_message='Aucune donnée Spotify trouvée'
            )
            self.artist_service.log_collection(log_data)

        # Log YouTube
        if collection_result.get('youtube_data'):
            log_data = CollectionLogCreate(
                artist_id=artist_id,
                collection_type='youtube',
                status='success',
                data_collected=json.dumps(collection_result['youtube_data'])
            )
            self.artist_service.log_collection(log_data)
        elif 'Aucune donnée YouTube trouvée' in collection_result.get('errors', []):
            log_data = CollectionLogCreate(
                artist_id=artist_id,
                collection_type='youtube',
                status='error',
                error_message='Aucune donnée YouTube trouvée'
            )
            self.artist_service.log_collection(log_data)

    def collect_and_save_artist(self, artist_name: str) -> Dict[str, Any]:
        """Collecter et sauvegarder les données d'un artiste en une seule opération"""
        collection_result = self.collect_artist_data(artist_name)
        
        if collection_result['success']:
            artist_id = self.save_artist_data(collection_result)
            collection_result['artist_id'] = artist_id
        
        return collection_result
