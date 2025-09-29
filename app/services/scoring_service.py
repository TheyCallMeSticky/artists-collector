"""
Service de scoring TubeBuddy simplifié et propre
Une seule méthode par métrique, algorithme clair et lisible
"""

import asyncio
import logging
import os
import redis
from typing import Dict, List, Optional
from datetime import datetime

from app.services.youtube_service import YouTubeService
from app.services.trends_service import TrendsService

logger = logging.getLogger(__name__)


class ScoringService:
    def __init__(self):
        # Services
        self.youtube_service = YouTubeService()

        # Redis pour cache
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        try:
            self.redis_client = redis.from_url(redis_url)
            self.redis_client.ping()
            self.trends_service = TrendsService(self.redis_client)
        except Exception as e:
            logger.warning(f"Redis non disponible: {e}")
            self.redis_client = None
            self.trends_service = TrendsService(None)

        # Coefficient musique (niche type beats)
        self.music_coefficient = 1.5

    async def calculate_tubebuddy_score(self, artist_name: str) -> Dict:
        """
        Calculer le score TubeBuddy pour un artiste
        Algorithme: 60% Search Volume + 40% Competition (ignorer optimisation)
        """
        try:
            # 1. Search Volume combiné (Trends + YouTube)
            search_volume_score = await self._calculate_search_volume(artist_name)

            # 2. Competition basée sur la densité des concurrents
            competition_score = await self._calculate_competition(artist_name)

            # 3. Score final: 60% volume + 40% faible compétition
            overall_score = (
                search_volume_score * 0.6 +
                (100 - competition_score) * 0.4
            ) * self.music_coefficient

            # Limiter à 100
            overall_score = min(overall_score, 100)

            return {
                "artist_name": artist_name,
                "search_volume_score": round(search_volume_score),
                "competition_score": round(competition_score),
                "optimization_score": 90,  # Fixe (format optimal supposé)
                "overall_score": round(overall_score),
                "calculated_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Erreur calcul score pour {artist_name}: {e}")
            return {
                "artist_name": artist_name,
                "error": str(e),
                "search_volume_score": 0,
                "competition_score": 100,
                "optimization_score": 0,
                "overall_score": 0
            }

    async def _calculate_search_volume(self, artist_name: str) -> float:
        """
        Search Volume combiné: Google Trends + YouTube Stats
        40% Trends + 40% Vues moyennes + 20% Nombre de vidéos
        """
        try:
            search_query = f"{artist_name} type beat"

            # 1. Google Trends (popularité générale)
            trends_score = 0
            try:
                trends_score = self.trends_service.get_trends_score(artist_name)
                logger.info(f"Google Trends pour {artist_name}: {trends_score}")
            except Exception as e:
                logger.warning(f"Erreur Google Trends pour {artist_name}: {e}")

            # 2. YouTube Search
            search_results = self.youtube_service.search_videos(search_query, max_results=50)
            if not search_results:
                return trends_score * 0.8  # Si pas de vidéos, utiliser seulement trends

            # 3. Statistiques des vidéos
            total_views = 0
            valid_videos = 0

            for video in search_results[:20]:  # Top 20 seulement
                video_stats = self.youtube_service.get_video_stats(video.get("id", ""))
                if video_stats:
                    view_count = int(video_stats.get("viewCount", 0))
                    total_views += view_count
                    valid_videos += 1

            avg_views = total_views / valid_videos if valid_videos > 0 else 0
            video_count = len(search_results)

            # 4. Normaliser les métriques (0-100)
            views_score = self._normalize_views(avg_views)
            count_score = self._normalize_video_count(video_count)

            # 5. Combiner: 40% trends + 40% vues + 20% nombre
            volume_score = (
                trends_score * 0.4 +
                views_score * 0.4 +
                count_score * 0.2
            )

            logger.info(f"Search Volume {artist_name}: trends={trends_score}, views={views_score}, count={count_score} → {volume_score}")
            return round(min(volume_score, 100))

        except Exception as e:
            logger.error(f"Erreur search volume pour {artist_name}: {e}")
            return 0

    def _normalize_views(self, avg_views: float) -> float:
        """Convertir vues moyennes en score 0-100"""
        if avg_views < 1000:
            return (avg_views / 1000) * 20
        elif avg_views < 10000:
            return 20 + ((avg_views - 1000) / 9000) * 30
        elif avg_views < 100000:
            return 50 + ((avg_views - 10000) / 90000) * 30
        else:
            return 80 + min(((avg_views - 100000) / 900000) * 20, 20)

    def _normalize_video_count(self, video_count: int) -> float:
        """Convertir nombre de vidéos en score 0-100"""
        if video_count < 100:
            return (video_count / 100) * 30
        elif video_count < 1000:
            return 30 + ((video_count - 100) / 900) * 40
        else:
            return 70 + min(((video_count - 1000) / 9000) * 30, 30)

    async def _calculate_competition(self, artist_name: str) -> float:
        """
        Competition: densité des concurrents sur "[artist] type beat"
        Plus il y a de gros créateurs → plus de compétition
        """
        try:
            search_query = f"{artist_name} type beat"
            search_results = self.youtube_service.search_videos(search_query, max_results=20)

            if not search_results:
                return 0  # Pas de compétition

            # Analyser les 20 premiers résultats
            total_competition = 0
            channels_analyzed = 0

            for video in search_results:
                channel_id = video.get("snippet", {}).get("channelId", "")
                if not channel_id:
                    continue

                # Stats de la chaîne
                channel_stats = self.youtube_service.get_channel_stats(channel_id)
                if channel_stats:
                    subscriber_count = int(channel_stats.get("subscriberCount", 0))
                    view_count = int(channel_stats.get("viewCount", 0))

                    # Score de compétitivité de cette chaîne
                    channel_competition = self._calculate_channel_competition(subscriber_count, view_count)
                    total_competition += channel_competition
                    channels_analyzed += 1

            if channels_analyzed == 0:
                return 50  # Compétition moyenne par défaut

            avg_competition = total_competition / channels_analyzed
            logger.info(f"Competition {artist_name}: {avg_competition} (sur {channels_analyzed} chaînes)")

            return round(min(avg_competition, 100))

        except Exception as e:
            logger.error(f"Erreur competition pour {artist_name}: {e}")
            return 50

    def _calculate_channel_competition(self, subscribers: int, total_views: int) -> float:
        """Score de compétitivité d'une chaîne (0-100)"""
        competition_score = 0

        # Abonnés (50% du score)
        if subscribers < 1000:
            competition_score += 10
        elif subscribers < 10000:
            competition_score += 25
        elif subscribers < 100000:
            competition_score += 40
        else:
            competition_score += 50

        # Vues totales (50% du score)
        if total_views < 100000:
            competition_score += 10
        elif total_views < 1000000:
            competition_score += 25
        elif total_views < 10000000:
            competition_score += 40
        else:
            competition_score += 50

        return competition_score

    async def batch_score_artists(self, artist_names: List[str]) -> List[Dict]:
        """Calculer les scores pour plusieurs artistes en parallèle"""
        batch_size = 5  # Traiter par groupes de 5
        all_results = []

        for i in range(0, len(artist_names), batch_size):
            batch = artist_names[i:i + batch_size]

            # Traitement parallèle du batch
            tasks = [self.calculate_tubebuddy_score(artist) for artist in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Traiter les résultats
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Erreur batch: {result}")
                else:
                    all_results.append(result)

            # Pause entre batches pour éviter rate limiting
            await asyncio.sleep(1)

        return all_results