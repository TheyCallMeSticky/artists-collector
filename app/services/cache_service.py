"""
Service de cache Redis pour optimiser les appels API YouTube
Évite les appels répétés pour les mêmes recherches/vidéos/chaînes
"""

import json
import logging
from typing import Dict, List, Optional, Any
import redis
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CacheService:
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client

        # TTL par type de données
        self.ttl_config = {
            'search_results': 3600,        # 1h - Les résultats de recherche changent fréquemment
            'video_stats': 24 * 3600,      # 24h - Stats vidéo évoluent moins vite
            'channel_stats': 7 * 24 * 3600, # 7j - Stats chaîne encore plus stables
            'search_count': 6 * 3600,      # 6h - Nombre de résultats de recherche
        }

    def _get_cache_key(self, cache_type: str, identifier: str) -> str:
        """Générer une clé de cache normalisée"""
        return f"yt_cache:{cache_type}:{identifier.lower().replace(' ', '_')}"

    def get_search_results(self, query: str, max_results: int = 50) -> Optional[List[Dict]]:
        """Récupérer les résultats de recherche YouTube depuis le cache"""
        if not self.redis_client:
            return None

        cache_key = self._get_cache_key('search_results', f"{query}:{max_results}")

        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                data = json.loads(cached_data.decode())
                logger.info(f"Cache HIT pour recherche: {query}")
                return data
        except Exception as e:
            logger.warning(f"Erreur lecture cache recherche: {e}")

        return None

    def cache_search_results(self, query: str, max_results: int, results: List[Dict]):
        """Mettre en cache les résultats de recherche YouTube"""
        if not self.redis_client or not results:
            return

        cache_key = self._get_cache_key('search_results', f"{query}:{max_results}")

        try:
            # Ajouter timestamp pour debugging
            cache_data = {
                'results': results,
                'cached_at': datetime.now().isoformat(),
                'query': query,
                'count': len(results)
            }

            self.redis_client.setex(
                cache_key,
                self.ttl_config['search_results'],
                json.dumps(cache_data['results'])  # On ne cache que les résultats
            )

            logger.info(f"Cache SET pour recherche: {query} ({len(results)} résultats)")

        except Exception as e:
            logger.error(f"Erreur mise en cache recherche: {e}")

    def get_video_stats(self, video_id: str) -> Optional[Dict]:
        """Récupérer les stats d'une vidéo depuis le cache"""
        if not self.redis_client:
            return None

        cache_key = self._get_cache_key('video_stats', video_id)

        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data.decode())
        except Exception as e:
            logger.warning(f"Erreur lecture cache video {video_id}: {e}")

        return None

    def cache_video_stats(self, video_id: str, stats: Dict):
        """Mettre en cache les stats d'une vidéo"""
        if not self.redis_client or not stats:
            return

        cache_key = self._get_cache_key('video_stats', video_id)

        try:
            self.redis_client.setex(
                cache_key,
                self.ttl_config['video_stats'],
                json.dumps(stats)
            )

            logger.debug(f"Cache SET pour vidéo: {video_id}")

        except Exception as e:
            logger.error(f"Erreur cache video {video_id}: {e}")

    def get_channel_stats(self, channel_id: str) -> Optional[Dict]:
        """Récupérer les stats d'une chaîne depuis le cache"""
        if not self.redis_client:
            return None

        cache_key = self._get_cache_key('channel_stats', channel_id)

        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data.decode())
        except Exception as e:
            logger.warning(f"Erreur lecture cache channel {channel_id}: {e}")

        return None

    def cache_channel_stats(self, channel_id: str, stats: Dict):
        """Mettre en cache les stats d'une chaîne"""
        if not self.redis_client or not stats:
            return

        cache_key = self._get_cache_key('channel_stats', channel_id)

        try:
            self.redis_client.setex(
                cache_key,
                self.ttl_config['channel_stats'],
                json.dumps(stats)
            )

            logger.debug(f"Cache SET pour chaîne: {channel_id}")

        except Exception as e:
            logger.error(f"Erreur cache channel {channel_id}: {e}")

    def get_search_count_estimate(self, query: str) -> Optional[int]:
        """Récupérer une estimation du nombre total de résultats pour une recherche"""
        if not self.redis_client:
            return None

        cache_key = self._get_cache_key('search_count', query)

        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                return int(cached_data.decode())
        except Exception as e:
            logger.warning(f"Erreur lecture cache count {query}: {e}")

        return None

    def cache_search_count_estimate(self, query: str, estimated_count: int):
        """Mettre en cache l'estimation du nombre de résultats"""
        if not self.redis_client:
            return

        cache_key = self._get_cache_key('search_count', query)

        try:
            self.redis_client.setex(
                cache_key,
                self.ttl_config['search_count'],
                str(estimated_count)
            )

            logger.info(f"Cache SET count pour: {query} = {estimated_count}")

        except Exception as e:
            logger.error(f"Erreur cache count {query}: {e}")

    def get_batch_video_stats(self, video_ids: List[str]) -> Dict[str, Dict]:
        """Récupérer les stats de plusieurs vidéos depuis le cache"""
        if not self.redis_client:
            return {}

        results = {}

        for video_id in video_ids:
            cached_stats = self.get_video_stats(video_id)
            if cached_stats:
                results[video_id] = cached_stats

        if results:
            logger.info(f"Cache HIT batch pour {len(results)}/{len(video_ids)} vidéos")

        return results

    def cache_batch_video_stats(self, video_stats_dict: Dict[str, Dict]):
        """Mettre en cache les stats de plusieurs vidéos"""
        if not self.redis_client or not video_stats_dict:
            return

        for video_id, stats in video_stats_dict.items():
            self.cache_video_stats(video_id, stats)

        logger.info(f"Cache SET batch pour {len(video_stats_dict)} vidéos")

    def get_batch_channel_stats(self, channel_ids: List[str]) -> Dict[str, Dict]:
        """Récupérer les stats de plusieurs chaînes depuis le cache"""
        if not self.redis_client:
            return {}

        results = {}

        for channel_id in channel_ids:
            cached_stats = self.get_channel_stats(channel_id)
            if cached_stats:
                results[channel_id] = cached_stats

        if results:
            logger.info(f"Cache HIT batch pour {len(results)}/{len(channel_ids)} chaînes")

        return results

    def cache_batch_channel_stats(self, channel_stats_dict: Dict[str, Dict]):
        """Mettre en cache les stats de plusieurs chaînes"""
        if not self.redis_client or not channel_stats_dict:
            return

        for channel_id, stats in channel_stats_dict.items():
            self.cache_channel_stats(channel_id, stats)

        logger.info(f"Cache SET batch pour {len(channel_stats_dict)} chaînes")

    def clear_cache_for_query(self, query: str):
        """Vider le cache pour une requête spécifique"""
        if not self.redis_client:
            return

        try:
            pattern = self._get_cache_key('search_results', f"{query}*")
            keys = self.redis_client.keys(pattern)

            if keys:
                self.redis_client.delete(*keys)
                logger.info(f"Cache cleared pour requête: {query}")

        except Exception as e:
            logger.error(f"Erreur clear cache pour {query}: {e}")

    def get_cache_stats(self) -> Dict:
        """Obtenir des statistiques sur l'utilisation du cache"""
        if not self.redis_client:
            return {}

        try:
            info = self.redis_client.info('memory')

            # Compter les clés par type
            key_counts = {}
            for cache_type in self.ttl_config.keys():
                pattern = f"yt_cache:{cache_type}:*"
                keys = self.redis_client.keys(pattern)
                key_counts[cache_type] = len(keys)

            return {
                'memory_used': info.get('used_memory_human', 'N/A'),
                'total_keys': sum(key_counts.values()),
                'keys_by_type': key_counts,
                'ttl_config': self.ttl_config
            }

        except Exception as e:
            logger.error(f"Erreur stats cache: {e}")
            return {}