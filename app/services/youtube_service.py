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

            # Système de gestion des clés épuisées
            self.exhausted_keys = set()  # Clés qui ont épuisé leur quota

    def get_current_api_key(self) -> str:
        """Récupérer la clé API actuelle avec rotation"""
        if self.mode == "MOCK":
            return "mock_key"
        return self.api_keys[self.current_key_index]

    def get_available_keys(self) -> List[str]:
        """Récupérer la liste des clés non épuisées"""
        return [key for key in self.api_keys if key not in self.exhausted_keys]

    def get_next_available_key_index(self) -> Optional[int]:
        """Trouver l'index de la prochaine clé disponible"""
        available_keys = self.get_available_keys()
        if not available_keys:
            return None

        # Chercher la prochaine clé disponible à partir de l'index actuel
        for i in range(len(self.api_keys)):
            next_index = (self.current_key_index + i) % len(self.api_keys)
            if self.api_keys[next_index] not in self.exhausted_keys:
                return next_index
        return None

    def rotate_api_key(self, mark_current_exhausted: bool = False):
        """Passer à la clé API suivante"""
        if self.mode == "MOCK":
            return

        # Marquer la clé actuelle comme épuisée si demandé
        if mark_current_exhausted:
            current_key = self.get_current_api_key()
            self.exhausted_keys.add(current_key)
            logger.warning(
                f"Clé API {self.current_key_index + 1} marquée comme épuisée"
            )

        # Trouver la prochaine clé disponible
        available_keys = [key for key in self.api_keys if key not in self.exhausted_keys]
        if not available_keys:
            next_index = None
        else:
            # Chercher la prochaine clé disponible à partir de l'index actuel
            next_index = None
            for i in range(len(self.api_keys)):
                candidate_index = (self.current_key_index + i) % len(self.api_keys)
                if self.api_keys[candidate_index] not in self.exhausted_keys:
                    next_index = candidate_index
                    break
        if next_index is not None:
            self.current_key_index = next_index
            logger.info(f"Rotation vers la clé API {self.current_key_index + 1}")
        else:
            logger.error("Aucune clé API disponible pour la rotation")

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

        available_keys = self.get_available_keys()
        if not available_keys:
            logger.error("Toutes les clés API ont été épuisées")
            raise Exception(
                "YOUTUBE_QUOTA_EXCEEDED: Toutes les clés API YouTube ont épuisé leur quota"
            )

        # S'assurer qu'on utilise une clé disponible
        if self.get_current_api_key() in self.exhausted_keys:
            next_index = self.get_next_available_key_index()
            if next_index is not None:
                self.current_key_index = next_index
                logger.info(
                    f"Passage à une clé disponible: {self.current_key_index + 1}"
                )

        max_retries = len(available_keys)
        logger.info(
            f"Tentative avec {max_retries} clé(s) disponible(s) sur {len(self.api_keys)} total"
        )

        for attempt in range(max_retries):
            current_key = self.get_current_api_key()

            # Vérifier que la clé n'est pas épuisée (double sécurité)
            if current_key in self.exhausted_keys:
                logger.warning(f"Clé épuisée détectée, rotation forcée")
                self.rotate_api_key()
                continue

            params["key"] = current_key

            try:
                response = requests.get(f"{self.base_url}/{endpoint}", params=params)
                print(
                    f"INFO : requète externe sur {self.base_url}/{endpoint} (clé {self.current_key_index + 1})"
                )

                if response.status_code == 200:
                    self.requests_per_key[current_key] += 1
                    result = response.json()
                    try:
                        self._save_to_cache(cache_key, result)
                    except Exception as cache_error:
                        logger.error(f"Erreur sauvegarde cache: {cache_error}")
                    return result

                elif response.status_code == 403:
                    # Quota dépassé pour cette clé
                    logger.warning(
                        f"Quota dépassé pour la clé {self.current_key_index + 1}, mise de côté"
                    )

                    # Vérifier si c'est la dernière clé disponible
                    remaining_keys = [k for k in available_keys if k != current_key]
                    if not remaining_keys:
                        logger.error("Dernière clé API épuisée - arrêt des requêtes")
                        raise Exception(
                            "YOUTUBE_QUOTA_EXCEEDED: Toutes les clés API YouTube ont épuisé leur quota"
                        )

                    # Marquer comme épuisée et passer à la suivante
                    self.rotate_api_key(mark_current_exhausted=True)
                    time.sleep(0.5)  # Attendre moins longtemps

                else:
                    logger.error(
                        f"Erreur API YouTube: {response.status_code} - {response.text}"
                    )
                    return None

            except Exception as e:
                logger.error(f"Erreur lors de la requête YouTube: {e}")
                self.rotate_api_key()
                time.sleep(0.5)

        logger.error("Toutes les clés disponibles ont été épuisées")
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

    def search_videos_with_stats(
        self, query: str, max_results: int = 50
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Rechercher des vidéos avec leurs stats ET les stats des chaînes en une requête optimisée
        Réduit de 3 appels API par vidéo à 2 appels API pour toutes les vidéos
        """
        # 1. Recherche des vidéos (sans guillemets pour simuler le comportement réel des utilisateurs)
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": max_results,
            "order": "relevance",
        }

        search_result = self.make_request("search", params)
        if not search_result or "items" not in search_result:
            return None

        # Extraire les IDs des vidéos et des chaînes
        video_ids = []
        channel_ids = []
        videos_map = {}

        for item in search_result["items"]:
            video_id = item["id"]["videoId"]
            channel_id = item["snippet"]["channelId"]

            video_ids.append(video_id)
            if channel_id not in channel_ids:
                channel_ids.append(channel_id)

            videos_map[video_id] = {
                "id": video_id,
                "snippet": item["snippet"],
                "channelId": channel_id
            }

        # 2. Récupérer les stats de TOUTES les vidéos en un seul appel
        video_stats_params = {
            "part": "statistics",
            "id": ",".join(video_ids),  # Jusqu'à 50 IDs par requête
        }

        videos_stats_result = self.make_request("videos", video_stats_params)
        if videos_stats_result and "items" in videos_stats_result:
            for item in videos_stats_result["items"]:
                video_id = item["id"]
                stats = item.get("statistics", {})
                if video_id in videos_map:
                    videos_map[video_id]["statistics"] = {
                        "viewCount": int(stats.get("viewCount", 0)),
                        "likeCount": int(stats.get("likeCount", 0)),
                        "commentCount": int(stats.get("commentCount", 0)),
                    }

        # 3. Récupérer les stats de TOUTES les chaînes en un seul appel
        channels_stats_params = {
            "part": "statistics",
            "id": ",".join(channel_ids),  # Jusqu'à 50 IDs par requête
        }

        channels_stats_result = self.make_request("channels", channels_stats_params)
        channels_map = {}
        if channels_stats_result and "items" in channels_stats_result:
            for item in channels_stats_result["items"]:
                channel_id = item["id"]
                stats = item.get("statistics", {})
                channels_map[channel_id] = {
                    "subscriberCount": int(stats.get("subscriberCount", 0)),
                    "videoCount": int(stats.get("videoCount", 0)),
                    "viewCount": int(stats.get("viewCount", 0)),
                }

        # 4. Combiner tout
        result_videos = []
        for video_id, video_data in videos_map.items():
            channel_id = video_data["channelId"]
            video_data["channelStats"] = channels_map.get(channel_id, {
                "subscriberCount": 0,
                "videoCount": 0,
                "viewCount": 0,
            })
            result_videos.append(video_data)

        logger.info(f"Récupéré {len(result_videos)} vidéos avec stats complètes en 3 appels API")
        return result_videos

    def collect_artist_data(self, artist_name: str) -> Optional[Dict[str, Any]]:
        """Pas de collecte YouTube - retourne None"""
        return None



    def get_quota_usage(self) -> Dict[str, Any]:
        """Récupérer les informations d'utilisation des quotas"""
        available_keys = self.get_available_keys()
        return {
            "total_keys": len(self.api_keys),
            "available_keys": len(available_keys),
            "exhausted_keys": len(self.exhausted_keys),
            "current_key_index": self.current_key_index,
            "exhausted_key_indices": [
                i + 1
                for i, key in enumerate(self.api_keys)
                if key in self.exhausted_keys
            ],
            "requests_per_key": self.requests_per_key,
            "total_requests": sum(self.requests_per_key.values()),
        }
