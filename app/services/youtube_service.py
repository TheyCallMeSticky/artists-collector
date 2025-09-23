import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class YouTubeService:
    def __init__(self):
        try:
            # Test de débogage
            self.debug_init = True

            # Mode de fonctionnement : MOCK ou LIVE
            self.mode = os.getenv("YOUTUBE_MODE", "LIVE").upper()

            # Chemin de cache robuste - utilise le répertoire de travail de l'app
            self.cache_dir = Path("/app/cache/youtube")
            if not self.cache_dir.exists():
                # Fallback pour développement local
                self.cache_dir = Path.cwd() / "cache" / "youtube"
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            # Sauvegarder l'erreur pour debug
            self.init_error = str(e)
            raise

        if self.mode == "MOCK":
            logger.info("YouTube Service en mode MOCK - utilisation du cache")
        else:
            # Charger toutes les clés API YouTube disponibles (de 1 à 12 max)
            self.api_keys = []
            for i in range(1, 13):  # Vérifier de YOUTUBE_API_KEY_1 à YOUTUBE_API_KEY_12
                key = os.getenv(f"YOUTUBE_API_KEY_{i}")
                if key and key.strip():  # Vérifier que la clé n'est pas vide
                    self.api_keys.append(key.strip())

            if not self.api_keys:
                raise ValueError(
                    "Au moins une clé API YouTube doit être définie (YOUTUBE_API_KEY_1 à YOUTUBE_API_KEY_12)"
                )

            logger.info(
                f"YouTube Service initialisé avec {len(self.api_keys)} clé(s) API"
            )

            self.current_key_index = 0
            self.base_url = "https://www.googleapis.com/youtube/v3"

            # Compteurs pour la gestion des quotas
            self.daily_quota_used = 0
            self.requests_per_key = {key: 0 for key in self.api_keys}

    def get_current_api_key(self) -> str:
        """Récupérer la clé API actuelle avec rotation"""
        if self.mode == "MOCK":
            return "mock_key"
        return self.api_keys[self.current_key_index]

    def rotate_api_key(self):
        """Passer à la clé API suivante"""
        if self.mode == "MOCK":
            return
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        logger.info(f"Rotation vers la clé API {self.current_key_index + 1}")

    def _get_cache_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        """Générer une clé de cache unique pour la requête"""
        # Retirer la clé API des params pour le cache
        cache_params = {k: v for k, v in params.items() if k != "key"}

        # Nom de fichier plus lisible pour les chaînes
        if endpoint == "search" and "channelId" in cache_params:
            channel_id = cache_params["channelId"]
            # Mapping des channel IDs vers des noms lisibles
            channel_names = {
                "UCtylTUUVIGY_i5afsQYeBZA": "lyrical_lemonade",
                "UC8QfB1wbfrNwNFHQxfyNJsw": "rap_nation",
                "UCSN7R7sDkoXfrx8gRdITr0Q": "elevator",
                "UC-yXuc1__OzjwpsJPlxYUCQ": "worldstarhiphop",
                "UCb5whUu1UmmYlbxoN6CCDXg": "paka_the_plug",
                "UClqCSuQEhuuiprJVTw3-rJQ": "the_cypher_effect",
                "UC9wgG6MYWq-5G0pjHGCw5GA": "i_am_hip_hop",
                "UCa8b7nZo-iPKoJxspOplnWg": "on_the_radar_radio",
            }
            channel_name = channel_names.get(channel_id, channel_id)
            cache_key = f"channel_{channel_name}_videos"
            logger.info(f"Cache key pour {channel_name}: {cache_key}")
            return cache_key

        # Fallback pour autres types de requêtes
        cache_string = f"{endpoint}_{json.dumps(cache_params, sort_keys=True)}"
        cache_key = hashlib.md5(cache_string.encode()).hexdigest()
        logger.info(f"Cache key pour {endpoint}: {cache_key} (params: {cache_params})")
        return cache_key

    def _save_to_cache(self, cache_key: str, data: Dict[str, Any]):
        """Sauvegarder les données dans le cache"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.debug(f"Données sauvées en cache: {cache_file}")

    def _load_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Charger les données depuis le cache"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.debug(f"Données chargées depuis le cache: {cache_file}")
            return data
        return None

    def make_request(
        self, endpoint: str, params: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Faire une requête à l'API YouTube avec gestion des erreurs et rotation des clés"""
        cache_key = self._get_cache_key(endpoint, params)
        logger.debug(f"Cache key généré: {cache_key}")

        print(f"INFO : mode {self.mode}")
        # En mode MOCK, vérifier le cache en premier
        if self.mode == "MOCK":
            cached_data = self._load_from_cache(cache_key)
            if cached_data:
                print(f"INFO : load from cache {cache_key}")
                return cached_data
            else:
                logger.warning(
                    f"Pas de données en cache pour {endpoint} avec params {params}"
                )
                return None

        max_retries = len(self.api_keys)

        for attempt in range(max_retries):
            current_key = self.get_current_api_key()
            params["key"] = current_key

            try:
                response = requests.get(f"{self.base_url}/{endpoint}", params=params)
                print(f"INFO : requète externe sur {self.base_url}/{endpoint}")
                print(params)
                if response.status_code == 200:
                    self.requests_per_key[current_key] += 1
                    result = response.json()
                    try:
                        self._save_to_cache(cache_key, result)
                    except Exception as cache_error:
                        logger.error(f"Erreur sauvegarde cache: {cache_error}")
                    return result
                elif response.status_code == 403:
                    # Quota dépassé, passer à la clé suivante
                    logger.warning(
                        f"Quota dépassé pour la clé {self.current_key_index + 1}"
                    )
                    self.rotate_api_key()
                    time.sleep(1)  # Attendre un peu avant de réessayer
                else:
                    logger.error(
                        f"Erreur API YouTube: {response.status_code} - {response.text}"
                    )
                    return None

            except Exception as e:
                logger.error(f"Erreur lors de la requête YouTube: {e}")
                self.rotate_api_key()
                time.sleep(1)

        logger.error("Toutes les clés API ont été épuisées")
        raise Exception(
            "YOUTUBE_QUOTA_EXCEEDED: Toutes les clés API YouTube ont épuisé leur quota"
        )

    def search_channel(self, artist_name: str) -> Optional[Dict[str, Any]]:
        """Rechercher une chaîne YouTube par nom d'artiste"""
        params = {
            "part": "snippet",
            "q": f"{artist_name} hip hop rap",
            "type": "channel",
            "maxResults": 5,
        }

        result = self.make_request("search", params)
        if result and "items" in result:
            # Retourner la première chaîne trouvée
            for item in result["items"]:
                return {
                    "channel_id": item["id"]["channelId"],
                    "title": item["snippet"]["title"],
                    "description": item["snippet"]["description"],
                    "thumbnail": item["snippet"]["thumbnails"]["default"]["url"],
                }
        return None

    def get_channel_info(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Récupérer les informations détaillées d'une chaîne"""
        params = {"part": "snippet,statistics", "id": channel_id}

        result = self.make_request("channels", params)
        if result and "items" in result and len(result["items"]) > 0:
            channel = result["items"][0]
            stats = channel.get("statistics", {})

            return {
                "channel_id": channel["id"],
                "title": channel["snippet"]["title"],
                "description": channel["snippet"]["description"],
                "subscriber_count": int(stats.get("subscriberCount", 0)),
                "video_count": int(stats.get("videoCount", 0)),
                "view_count": int(stats.get("viewCount", 0)),
                "published_at": channel["snippet"]["publishedAt"],
            }
        return None

    def get_channel_videos(
        self, channel_id: str, max_results: int = 10
    ) -> Optional[List[Dict[str, Any]]]:
        """Récupérer les vidéos récentes d'une chaîne"""
        params = {
            "part": "snippet",
            "channelId": channel_id,
            "q": "music",  # Fix: ajouter query pour contourner le bug YouTube API
            "maxResults": max_results,
            "order": "date",
            "type": "video",
        }
        try:
            result = self.make_request("search", params)
            if result and "items" in result:
                videos = []
                for item in result["items"]:
                    videos.append(
                        {
                            "video_id": item["id"]["videoId"],
                            "title": item["snippet"]["title"],
                            "description": item["snippet"]["description"],
                            "published_at": item["snippet"]["publishedAt"],
                            "thumbnail": item["snippet"]["thumbnails"]["default"][
                                "url"
                            ],
                        }
                    )
                return videos
            return None
        except Exception as e:
            # Propager les exceptions de quota
            raise e

    def get_video_stats(
        self, video_id: str
    ) -> Optional[Dict[str, Any]]:
        """Récupérer les statistiques d'une vidéo unique"""
        if not video_id:
            return None

        params = {
            "part": "statistics",
            "id": video_id,
        }

        result = self.make_request("videos", params)
        if result and "items" in result and len(result["items"]) > 0:
            stats = result["items"][0].get("statistics", {})
            return {
                "viewCount": int(stats.get("viewCount", 0)),
                "likeCount": int(stats.get("likeCount", 0)),
                "commentCount": int(stats.get("commentCount", 0)),
            }
        return None

    def get_multiple_video_stats(
        self, video_ids: List[str]
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        """Récupérer les statistiques de plusieurs vidéos"""
        if not video_ids:
            return None

        params = {
            "part": "statistics",
            "id": ",".join(video_ids[:50]),  # Limiter à 50 vidéos par requête
        }

        result = self.make_request("videos", params)
        if result and "items" in result:
            video_stats = {}
            for item in result["items"]:
                stats = item.get("statistics", {})
                video_stats[item["id"]] = {
                    "view_count": int(stats.get("viewCount", 0)),
                    "like_count": int(stats.get("likeCount", 0)),
                    "comment_count": int(stats.get("commentCount", 0)),
                }
            return video_stats
        return None

    def search_videos(
        self, query: str, max_results: int = 50
    ) -> Optional[List[Dict[str, Any]]]:
        """Rechercher des vidéos par requête de recherche"""
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": max_results,
            "order": "relevance",
        }

        result = self.make_request("search", params)
        if result and "items" in result:
            videos = []
            for item in result["items"]:
                videos.append({
                    "id": item["id"]["videoId"],
                    "snippet": item["snippet"]
                })
            return videos
        return None

    def get_channel_stats(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Récupérer les statistiques d'une chaîne"""
        params = {
            "part": "statistics",
            "id": channel_id
        }

        result = self.make_request("channels", params)
        if result and "items" in result and len(result["items"]) > 0:
            stats = result["items"][0].get("statistics", {})
            return {
                "subscriberCount": int(stats.get("subscriberCount", 0)),
                "videoCount": int(stats.get("videoCount", 0)),
                "viewCount": int(stats.get("viewCount", 0)),
            }
        return None

    def collect_artist_data(self, artist_name: str) -> Optional[Dict[str, Any]]:
        """Collecter toutes les données YouTube d'un artiste"""
        try:
            # Rechercher la chaîne
            channel_search = self.search_channel(artist_name)
            if not channel_search:
                return None

            channel_id = channel_search["channel_id"]

            # Récupérer les informations de la chaîne
            channel_info = self.get_channel_info(channel_id)
            if not channel_info:
                return None

            # Récupérer les vidéos récentes
            recent_videos = self.get_channel_videos(channel_id, 20)

            # Récupérer les statistiques des vidéos
            video_stats = None
            if recent_videos:
                video_ids = [video["video_id"] for video in recent_videos]
                video_stats = self.get_multiple_video_stats(video_ids)

            return {
                "channel_info": channel_info,
                "recent_videos": recent_videos,
                "video_stats": video_stats,
                "channel_id": channel_id,
            }

        except Exception as e:
            logger.error(
                f"Erreur lors de la collecte des données YouTube de {artist_name}: {e}"
            )
            return None

    def get_quota_usage(self) -> Dict[str, Any]:
        """Récupérer les informations d'utilisation des quotas"""
        return {
            "total_keys": len(self.api_keys),
            "current_key_index": self.current_key_index,
            "requests_per_key": self.requests_per_key,
            "total_requests": sum(self.requests_per_key.values()),
        }
