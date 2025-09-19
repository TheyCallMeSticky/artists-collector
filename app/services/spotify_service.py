import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class SpotifyService:
    def __init__(self):
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        
        if not client_id or not client_secret:
            raise ValueError("SPOTIFY_CLIENT_ID et SPOTIFY_CLIENT_SECRET doivent être définis")
        
        client_credentials_manager = SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret
        )
        self.sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

    def search_artist(self, artist_name: str) -> Optional[Dict[str, Any]]:
        """Rechercher un artiste par nom sur Spotify"""
        try:
            results = self.sp.search(q=f'artist:{artist_name}', type='artist', limit=1)
            if results['artists']['items']:
                return results['artists']['items'][0]
            return None
        except Exception as e:
            logger.error(f"Erreur lors de la recherche de l'artiste {artist_name}: {e}")
            return None

    def get_artist_info(self, spotify_id: str) -> Optional[Dict[str, Any]]:
        """Récupérer les informations détaillées d'un artiste"""
        try:
            artist = self.sp.artist(spotify_id)
            return {
                'id': artist['id'],
                'name': artist['name'],
                'followers': artist['followers']['total'],
                'popularity': artist['popularity'],
                'genres': artist['genres'],
                'images': artist['images']
            }
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des infos de l'artiste {spotify_id}: {e}")
            return None

    def get_artist_top_tracks(self, spotify_id: str, country: str = 'US') -> Optional[Dict[str, Any]]:
        """Récupérer les top tracks d'un artiste"""
        try:
            top_tracks = self.sp.artist_top_tracks(spotify_id, country=country)
            tracks_info = []
            
            for track in top_tracks['tracks']:
                tracks_info.append({
                    'name': track['name'],
                    'popularity': track['popularity'],
                    'duration_ms': track['duration_ms'],
                    'explicit': track['explicit']
                })
            
            return {
                'tracks': tracks_info,
                'total_tracks': len(tracks_info)
            }
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des top tracks de {spotify_id}: {e}")
            return None

    def get_artist_albums(self, spotify_id: str, limit: int = 20) -> Optional[Dict[str, Any]]:
        """Récupérer les albums d'un artiste"""
        try:
            albums = self.sp.artist_albums(spotify_id, album_type='album,single', limit=limit)
            albums_info = []
            
            for album in albums['items']:
                albums_info.append({
                    'name': album['name'],
                    'release_date': album['release_date'],
                    'total_tracks': album['total_tracks'],
                    'album_type': album['album_type']
                })
            
            return {
                'albums': albums_info,
                'total_albums': len(albums_info)
            }
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des albums de {spotify_id}: {e}")
            return None

    def get_related_artists(self, spotify_id: str) -> Optional[Dict[str, Any]]:
        """Récupérer les artistes similaires"""
        try:
            related = self.sp.artist_related_artists(spotify_id)
            related_info = []
            
            for artist in related['artists'][:10]:  # Limiter à 10 artistes
                related_info.append({
                    'id': artist['id'],
                    'name': artist['name'],
                    'popularity': artist['popularity'],
                    'followers': artist['followers']['total']
                })
            
            return {
                'related_artists': related_info,
                'total_related': len(related_info)
            }
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des artistes similaires de {spotify_id}: {e}")
            return None

    def collect_artist_data(self, artist_name: str) -> Optional[Dict[str, Any]]:
        """Collecter toutes les données d'un artiste"""
        try:
            # Rechercher l'artiste
            artist_search = self.search_artist(artist_name)
            if not artist_search:
                return None
            
            spotify_id = artist_search['id']
            
            # Collecter toutes les informations
            artist_info = self.get_artist_info(spotify_id)
            top_tracks = self.get_artist_top_tracks(spotify_id)
            albums = self.get_artist_albums(spotify_id)
            related_artists = self.get_related_artists(spotify_id)
            
            return {
                'artist_info': artist_info,
                'top_tracks': top_tracks,
                'albums': albums,
                'related_artists': related_artists,
                'spotify_id': spotify_id
            }
        except Exception as e:
            logger.error(f"Erreur lors de la collecte des données de {artist_name}: {e}")
            return None
