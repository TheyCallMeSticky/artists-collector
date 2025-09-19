import requests
import os
import time
import logging
from typing import Optional, Dict, Any, List
import json

logger = logging.getLogger(__name__)

class YouTubeService:
    def __init__(self):
        # Charger toutes les clés API YouTube disponibles (de 1 à 12 max)
        self.api_keys = []
        for i in range(1, 13):  # Vérifier de YOUTUBE_API_KEY_1 à YOUTUBE_API_KEY_12
            key = os.getenv(f"YOUTUBE_API_KEY_{i}")
            if key and key.strip():  # Vérifier que la clé n'est pas vide
                self.api_keys.append(key.strip())
        
        if not self.api_keys:
            raise ValueError("Au moins une clé API YouTube doit être définie (YOUTUBE_API_KEY_1 à YOUTUBE_API_KEY_12)")
        
        logger.info(f"YouTube Service initialisé avec {len(self.api_keys)} clé(s) API")
        
        self.current_key_index = 0
        self.base_url = "https://www.googleapis.com/youtube/v3"
        
        # Compteurs pour la gestion des quotas
        self.daily_quota_used = 0
        self.requests_per_key = {key: 0 for key in self.api_keys}

    def get_current_api_key(self) -> str:
        """Récupérer la clé API actuelle avec rotation"""
        return self.api_keys[self.current_key_index]

    def rotate_api_key(self):
        """Passer à la clé API suivante"""
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        logger.info(f"Rotation vers la clé API {self.current_key_index + 1}")

    def make_request(self, endpoint: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Faire une requête à l'API YouTube avec gestion des erreurs et rotation des clés"""
        max_retries = len(self.api_keys)
        
        for attempt in range(max_retries):
            current_key = self.get_current_api_key()
            params['key'] = current_key
            
            try:
                response = requests.get(f"{self.base_url}/{endpoint}", params=params)
                
                if response.status_code == 200:
                    self.requests_per_key[current_key] += 1
                    return response.json()
                elif response.status_code == 403:
                    # Quota dépassé, passer à la clé suivante
                    logger.warning(f"Quota dépassé pour la clé {self.current_key_index + 1}")
                    self.rotate_api_key()
                    time.sleep(1)  # Attendre un peu avant de réessayer
                else:
                    logger.error(f"Erreur API YouTube: {response.status_code} - {response.text}")
                    return None
                    
            except Exception as e:
                logger.error(f"Erreur lors de la requête YouTube: {e}")
                self.rotate_api_key()
                time.sleep(1)
        
        logger.error("Toutes les clés API ont été épuisées")
        return None

    def search_channel(self, artist_name: str) -> Optional[Dict[str, Any]]:
        """Rechercher une chaîne YouTube par nom d'artiste"""
        params = {
            'part': 'snippet',
            'q': f"{artist_name} hip hop rap",
            'type': 'channel',
            'maxResults': 5
        }
        
        result = self.make_request('search', params)
        if result and 'items' in result:
            # Retourner la première chaîne trouvée
            for item in result['items']:
                return {
                    'channel_id': item['id']['channelId'],
                    'title': item['snippet']['title'],
                    'description': item['snippet']['description'],
                    'thumbnail': item['snippet']['thumbnails']['default']['url']
                }
        return None

    def get_channel_info(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Récupérer les informations détaillées d'une chaîne"""
        params = {
            'part': 'snippet,statistics',
            'id': channel_id
        }
        
        result = self.make_request('channels', params)
        if result and 'items' in result and len(result['items']) > 0:
            channel = result['items'][0]
            stats = channel.get('statistics', {})
            
            return {
                'channel_id': channel['id'],
                'title': channel['snippet']['title'],
                'description': channel['snippet']['description'],
                'subscriber_count': int(stats.get('subscriberCount', 0)),
                'video_count': int(stats.get('videoCount', 0)),
                'view_count': int(stats.get('viewCount', 0)),
                'published_at': channel['snippet']['publishedAt']
            }
        return None

    def get_channel_videos(self, channel_id: str, max_results: int = 10) -> Optional[List[Dict[str, Any]]]:
        """Récupérer les vidéos récentes d'une chaîne"""
        params = {
            'part': 'snippet',
            'channelId': channel_id,
            'maxResults': max_results,
            'order': 'date',
            'type': 'video'
        }
        
        result = self.make_request('search', params)
        if result and 'items' in result:
            videos = []
            for item in result['items']:
                videos.append({
                    'video_id': item['id']['videoId'],
                    'title': item['snippet']['title'],
                    'description': item['snippet']['description'],
                    'published_at': item['snippet']['publishedAt'],
                    'thumbnail': item['snippet']['thumbnails']['default']['url']
                })
            return videos
        return None

    def get_video_stats(self, video_ids: List[str]) -> Optional[Dict[str, Dict[str, Any]]]:
        """Récupérer les statistiques de plusieurs vidéos"""
        if not video_ids:
            return None
            
        params = {
            'part': 'statistics',
            'id': ','.join(video_ids[:50])  # Limiter à 50 vidéos par requête
        }
        
        result = self.make_request('videos', params)
        if result and 'items' in result:
            video_stats = {}
            for item in result['items']:
                stats = item.get('statistics', {})
                video_stats[item['id']] = {
                    'view_count': int(stats.get('viewCount', 0)),
                    'like_count': int(stats.get('likeCount', 0)),
                    'comment_count': int(stats.get('commentCount', 0))
                }
            return video_stats
        return None

    def collect_artist_data(self, artist_name: str) -> Optional[Dict[str, Any]]:
        """Collecter toutes les données YouTube d'un artiste"""
        try:
            # Rechercher la chaîne
            channel_search = self.search_channel(artist_name)
            if not channel_search:
                return None
            
            channel_id = channel_search['channel_id']
            
            # Récupérer les informations de la chaîne
            channel_info = self.get_channel_info(channel_id)
            if not channel_info:
                return None
            
            # Récupérer les vidéos récentes
            recent_videos = self.get_channel_videos(channel_id, 20)
            
            # Récupérer les statistiques des vidéos
            video_stats = None
            if recent_videos:
                video_ids = [video['video_id'] for video in recent_videos]
                video_stats = self.get_video_stats(video_ids)
            
            return {
                'channel_info': channel_info,
                'recent_videos': recent_videos,
                'video_stats': video_stats,
                'channel_id': channel_id
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la collecte des données YouTube de {artist_name}: {e}")
            return None

    def get_quota_usage(self) -> Dict[str, Any]:
        """Récupérer les informations d'utilisation des quotas"""
        return {
            'total_keys': len(self.api_keys),
            'current_key_index': self.current_key_index,
            'requests_per_key': self.requests_per_key,
            'total_requests': sum(self.requests_per_key.values())
        }
