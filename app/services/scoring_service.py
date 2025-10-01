"""
Service de scoring TubeBuddy simplifié et propre
Une seule méthode par métrique, algorithme clair et lisible
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

import redis
from app.services.trends_service import TrendsService
from app.services.youtube_service import YouTubeService

logger = logging.getLogger(__name__)


class ScoringService:
    def __init__(self):
        # Services
        self.youtube_service = YouTubeService()

        # Redis pour cache
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
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
        Optimisé: 1 seul appel API récupère 50 vidéos avec stats, partagé entre les 2 calculs
        """
        try:
            search_query = f'"{artist_name}" "type beat"'

            # OPTIMISATION: Un seul appel pour récupérer 50 vidéos avec toutes les stats
            # Réduit de 24 appels API (1 search + 20 video_stats + 3 pour competition) à 3 appels
            videos_with_stats = self.youtube_service.search_videos_with_stats(
                search_query, max_results=50
            )

            # 1. Search Volume combiné (Trends + YouTube) - utilise top 20 pour vues, 50 pour count
            search_volume_score = await self._calculate_search_volume(
                artist_name, videos_with_stats
            )

            # 2. Competition basée sur la densité des concurrents - utilise top 20
            competition_score = await self._calculate_competition(
                artist_name, videos_with_stats
            )

            # 3. Score final: 60% volume + 40% faible compétition
            overall_score = (
                search_volume_score * 0.6 + (100 - competition_score) * 0.4
            ) * self.music_coefficient

            # Limiter à 100
            overall_score = min(overall_score, 100)

            return {
                "artist_name": artist_name,
                "search_volume_score": round(search_volume_score),
                "competition_score": round(competition_score),
                "optimization_score": 90,  # Fixe (format optimal supposé)
                "overall_score": round(overall_score),
                "calculated_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Erreur calcul score pour {artist_name}: {e}")
            return {
                "artist_name": artist_name,
                "error": str(e),
                "search_volume_score": 0,
                "competition_score": 100,
                "optimization_score": 0,
                "overall_score": 0,
            }

    async def _calculate_search_volume(
        self, artist_name: str, videos_with_stats: List[Dict] = None
    ) -> float:
        """
        Search Volume combiné: Google Trends + YouTube Stats
        40% Trends + 40% Vues moyennes + 20% Nombre de vidéos
        """
        try:
            # 1. Google Trends (popularité générale)
            trends_score = 0
            try:
                trends_score = self.trends_service.get_trends_score(artist_name)
                logger.info(f"Google Trends pour {artist_name}: {trends_score}")
            except Exception as e:
                logger.warning(f"Erreur Google Trends pour {artist_name}: {e}")

            # 2. Utiliser les vidéos pré-chargées (optimisé)
            if not videos_with_stats:
                return trends_score * 0.8  # Si pas de vidéos, utiliser seulement trends

            # 3. Statistiques des vidéos - utiliser top 20 pour vues moyennes
            total_views = 0
            valid_videos = 0

            for video in videos_with_stats[:20]:  # Top 20 seulement pour vues moyennes
                view_count = video.get("statistics", {}).get("viewCount", 0)
                if view_count > 0:
                    total_views += view_count
                    valid_videos += 1

            avg_views = total_views / valid_videos if valid_videos > 0 else 0
            video_count = len(videos_with_stats)  # Nombre total (50)

            # 4. Normaliser les métriques (0-100)
            views_score = self._normalize_views(avg_views)
            count_score = self._normalize_video_count(video_count)

            # 5. Combiner: 40% trends + 40% vues + 20% nombre
            volume_score = trends_score * 0.4 + views_score * 0.4 + count_score * 0.2

            logger.info(
                f"Search Volume {artist_name}: trends={trends_score}, views={views_score}, count={count_score} → {volume_score}"
            )
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

    def _normalize_metric(self, value: int, min_val: int, max_val: int, max_points: float = 50) -> float:
        """
        Distribution logarithmique d'une métrique entre min et max
        Retourne un score entre 0 et max_points
        """
        import math

        if value <= min_val:
            return 0
        if value >= max_val:
            return max_points

        # Échelle logarithmique pour mieux différencier les ordres de grandeur
        log_min = math.log10(max(min_val, 1))
        log_max = math.log10(max_val)
        log_value = math.log10(max(value, 1))

        # Normaliser entre 0 et max_points
        normalized = ((log_value - log_min) / (log_max - log_min)) * max_points
        return min(max(normalized, 0), max_points)

    async def _calculate_competition(
        self, artist_name: str, videos_with_stats: List[Dict] = None
    ) -> float:
        """
        Competition selon méthode TubeBuddy:
        - Analyse des 20 premières vidéos
        - Pour chaque vidéo: nombre de vues + taille de la chaîne
        - Score 0-100: 0 = pas de compétition, 100 = grosse compétition
        - Utilise une distribution logarithmique pour mieux capturer les ordres de grandeur
        """
        try:
            if not videos_with_stats:
                return 50  # Compétition moyenne par défaut

            # Utiliser seulement les 20 premières vidéos (même si on en a 50)
            top_20_videos = videos_with_stats[:20]
            total_videos = len(top_20_videos)

            # Grouper par chaîne pour détecter la saturation
            channels = {}
            total_views = 0
            for video in top_20_videos:
                channel_id = video.get("snippet", {}).get("channelId", "unknown")
                video_views = video.get("statistics", {}).get("viewCount", 0)
                channel_subs = video.get("channelStats", {}).get("subscriberCount", 0)

                total_views += video_views

                if channel_id not in channels:
                    channels[channel_id] = {
                        "video_count": 0,
                        "max_views": 0,
                        "subscribers": channel_subs,
                    }

                channels[channel_id]["video_count"] += 1
                channels[channel_id]["max_views"] = max(channels[channel_id]["max_views"], video_views)

            # 1. Score de saturation (monopole vs diversifié) - 33%
            unique_channels = len(channels)
            if unique_channels <= 3:  # 1-3 chaînes = monopole = forte compétition
                saturation_score = 50
            elif unique_channels <= 5:  # 4-5 chaînes = moyenne-haute
                saturation_score = 40
            elif unique_channels <= 8:  # 6-8 chaînes = moyenne
                saturation_score = 25
            elif unique_channels <= 12:  # 9-12 chaînes = faible
                saturation_score = 15
            else:  # 13+ chaînes = très faible
                saturation_score = 5

            # 2. Score de qualité des chaînes (taille) - 33%
            total_subs = sum(ch["subscribers"] for ch in channels.values())
            avg_subs = total_subs / unique_channels if unique_channels > 0 else 0
            if avg_subs >= 20000:  # 20k+ = grosse chaîne
                quality_score = 50
            elif avg_subs >= 5000:  # 5k+ = moyenne
                quality_score = 30
            elif avg_subs >= 1000:  # 1k+ = petite monétisée
                quality_score = 15
            else:  # < 1k = micro
                quality_score = 5

            # 3. Score de vues moyennes - 34%
            avg_views = total_views / total_videos if total_videos > 0 else 0
            if avg_views >= 20000:  # 20k+ vues = forte compétition
                views_score = 50
            elif avg_views >= 5000:  # 5k+ vues = moyenne
                views_score = 30
            elif avg_views >= 1000:  # 1k+ vues = faible
                views_score = 15
            else:  # < 1k = très faible
                views_score = 5

            # Score final combiné (33% saturation + 33% qualité + 34% vues)
            avg_competition = (saturation_score * 0.33) + (quality_score * 0.33) + (views_score * 0.34)

            # Logs pour debug - afficher toutes les vidéos
            print(f"\n[DEBUG {artist_name}] Analyse complète des 20 vidéos:")
            for idx, video in enumerate(top_20_videos, 1):
                v = video.get("statistics", {}).get("viewCount", 0)
                s = video.get("channelStats", {}).get("subscriberCount", 0)
                ch_id = video.get("snippet", {}).get("channelId", "")[:15]
                print(f"  #{idx:2d}: {v:8,} vues | {s:8,} abonnés | Channel: {ch_id}...")

            print(f"\n  → {unique_channels} chaînes uniques | Avg: {avg_subs:,.0f} abonnés, {avg_views:,.0f} vues")
            print(f"  → Saturation: {saturation_score} | Qualité: {quality_score} | Vues: {views_score} | Final: {avg_competition:.1f}")

            # Inverser le score: TubeBuddy donne 100 pour faible compétition, 0 pour forte
            # avg_competition est entre 0 (faible) et 100 (forte), on inverse
            inverted_score = 100 - avg_competition

            logger.info(
                f"Competition {artist_name}: {inverted_score:.1f}/100 (analysé {total_videos} vidéos)"
            )

            return round(max(min(inverted_score, 100), 0))

        except Exception as e:
            logger.error(f"Erreur competition pour {artist_name}: {e}")
            return 50

    async def batch_score_artists(self, artist_names: List[str]) -> List[Dict]:
        """Calculer les scores pour plusieurs artistes en parallèle"""
        batch_size = 5  # Traiter par groupes de 5
        all_results = []

        for i in range(0, len(artist_names), batch_size):
            batch = artist_names[i : i + batch_size]

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

    def get_score_interpretation(self, score: float) -> Dict:
        """Interpréter le score TubeBuddy et donner des recommandations"""
        if score >= 80:
            category = "Excellent"
            recommendation = "Opportunité exceptionnelle pour type beats - Forte demande, faible compétition"
        elif score >= 65:
            category = "Très bon"
            recommendation = (
                "Bonne opportunité - Demande solide avec compétition modérée"
            )
        elif score >= 50:
            category = "Moyen"
            recommendation = "Opportunité modérée - À considérer selon votre stratégie"
        elif score >= 30:
            category = "Faible"
            recommendation = (
                "Opportunité limitée - Compétition élevée ou faible demande"
            )
        else:
            category = "Très faible"
            recommendation = "Éviter - Marché saturé ou sans demande"

        return {"score": score, "category": category, "recommendation": recommendation}
