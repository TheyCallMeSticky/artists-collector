"""
Service de scoring TubeBuddy pour évaluer les opportunités d'artistes
Implémente la formule de l'étude : (Google_Trends_Score × 1000) × (1 / log(Nombre_Résultats_YouTube))
Calcule un score basé sur: Search Volume (40%) + Competition (40%) + Optimization (20%)
"""

import asyncio
import re
import logging
import math
import os
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote_plus
from datetime import datetime, timedelta
import redis

from app.services.youtube_service import YouTubeService
from app.services.trends_service import TrendsService
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class ScoringService:
    def __init__(self):
        # Initialiser les services
        self.youtube_service = YouTubeService()

        # Initialiser Redis pour le cache
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        try:
            self.redis_client = redis.from_url(redis_url)
            self.redis_client.ping()  # Test de connexion
        except Exception as e:
            logger.warning(f"Redis non disponible, cache désactivé: {e}")
            self.redis_client = None

        # Initialiser les services avec cache
        self.trends_service = TrendsService(self.redis_client)
        self.cache_service = CacheService(self.redis_client)

        # Formule TubeBuddy selon l'étude: Search Volume (40%) + Competition (40%) + Optimization (20%)
        self.weights = {
            'search_volume': 0.4,
            'competition': 0.4,  # Note: sera inversé dans le calcul final
            'optimization': 0.2
        }

        # Coefficients par niche selon l'étude
        self.niche_coefficients = {
            'gaming': 1.2,
            'tutorials': 0.8,
            'music': 1.5,  # Type beats = musique
            'default': 1.0
        }

    async def calculate_artist_score(self, artist_name: str) -> Dict:
        """
        Calculer le score TubeBuddy complet selon la formule de l'étude :
        Search Volume = (Google_Trends_Score × 1000) × (1 / log(Nombre_Résultats_YouTube))

        Returns:
            Dict avec search_volume_score, competition_score, optimization_score et overall_score
        """
        try:
            search_query = f"{artist_name} type beat"

            # ÉTAPE 1: Récupérer le score Google Trends
            trends_score = self.trends_service.get_trends_score(search_query)
            logger.info(f"Google Trends pour '{search_query}': {trends_score}")

            # ÉTAPE 2: Recherche YouTube avec cache
            search_results = self.cache_service.get_search_results(search_query, max_results=50)

            if search_results is None:
                # Pas en cache, faire la requête YouTube
                search_results = self.youtube_service.search_videos(
                    query=search_query,
                    max_results=50
                )
                # Mettre en cache
                self.cache_service.cache_search_results(search_query, 50, search_results)

            if not search_results:
                # Aucun résultat = niche vierge
                return {
                    "artist_name": artist_name,
                    "search_volume_score": min(trends_score, 100),  # Limité à 100
                    "competition_score": 0,  # Aucune compétition
                    "optimization_score": 100,  # Opportunité maximale
                    "overall_score": round(min(trends_score, 100) * 0.8),  # Forte pondération volume
                    "trends_score": trends_score,
                    "estimated_video_count": 0,
                    "components": {
                        "formula": "Google Trends × Coefficient Niche",
                        "search_volume_weight": 0.4,
                        "competition_weight": 0.4,
                        "optimization_weight": 0.2
                    }
                }

            # ÉTAPE 3: Estimer le nombre total de vidéos selon la méthode de l'étude
            estimated_video_count = await self._estimate_total_video_count(search_results, search_query)

            # ÉTAPE 4: Calculer Search Volume selon la formule de l'étude
            search_volume_score = self._calculate_search_volume_tubebuddy_formula(
                trends_score, estimated_video_count
            )

            # ÉTAPE 5: Récupérer stats vidéos/chaînes avec cache optimisé
            video_stats_cache, channel_stats_cache = await self._get_cached_stats(search_results)

            # ÉTAPE 6: Calculer Competition et Optimization
            competition_score = self._calculate_competition_tubebuddy_formula(
                search_results, channel_stats_cache, estimated_video_count
            )
            optimization_score = self._calculate_optimization_tubebuddy_formula(
                search_results[:20], artist_name  # Top 20 pour optimisation
            )

            # ÉTAPE 7: Score final avec coefficient musique
            music_coefficient = self.niche_coefficients['music']

            # Formule finale TubeBuddy
            overall_score = (
                (search_volume_score * self.weights['search_volume']) +
                ((100 - competition_score) * self.weights['competition']) +
                (optimization_score * self.weights['optimization'])
            ) * music_coefficient

            # Limiter à 100
            overall_score = min(overall_score, 100)

            return {
                "artist_name": artist_name,
                "search_volume_score": round(search_volume_score),
                "competition_score": round(competition_score),
                "optimization_score": round(optimization_score),
                "overall_score": round(overall_score),
                "trends_score": trends_score,
                "estimated_video_count": estimated_video_count,
                "music_coefficient": music_coefficient,
                "components": {
                    "formula": f"Trends({trends_score}) × (1/log({estimated_video_count})) × coeff({music_coefficient})",
                    "search_volume_weight": self.weights['search_volume'],
                    "competition_weight": self.weights['competition'],
                    "optimization_weight": self.weights['optimization']
                },
                "cache_efficiency": {
                    "search_cached": search_results is not None,
                    "video_stats_cached": len([v for v in video_stats_cache.values() if v]),
                    "channel_stats_cached": len([c for c in channel_stats_cache.values() if c])
                }
            }

        except Exception as e:
            logger.error(f"Erreur calcul score pour {artist_name}: {str(e)}")
            return {
                "artist_name": artist_name,
                "error": f"Erreur calcul score: {str(e)}",
                "search_volume_score": 0,
                "competition_score": 100,
                "optimization_score": 0,
                "overall_score": 0
            }

    async def _calculate_search_volume_score(self, artist_name: str) -> float:
        """
        Calculer le score de volume de recherche (0-100)
        Analyse le nombre de résultats YouTube pour "[artist] type beat"
        """
        try:
            search_query = f"{artist_name} type beat"

            # Utiliser l'API YouTube Search pour compter les résultats
            search_results = self.youtube_service.search_videos(
                query=search_query,
                max_results=50  # Maximum pour avoir un échantillon représentatif
            )

            if not search_results:
                return 0

            # Analyser le volume basé sur le nombre de résultats et vues moyennes
            total_views = 0
            valid_videos = 0

            for video in search_results:
                # Récupérer les statistiques de la vidéo
                video_stats = self.youtube_service.get_video_stats(video.get("id", ""))
                if video_stats:
                    view_count = int(video_stats.get("viewCount", 0))
                    total_views += view_count
                    valid_videos += 1

            if valid_videos == 0:
                return 0

            avg_views = total_views / valid_videos

            # Conversion en score 0-100 basé sur les vues moyennes
            # 0-1K vues = 0-20 points
            # 1K-10K vues = 20-50 points
            # 10K-100K vues = 50-80 points
            # 100K+ vues = 80-100 points
            if avg_views < 1000:
                score = (avg_views / 1000) * 20
            elif avg_views < 10000:
                score = 20 + ((avg_views - 1000) / 9000) * 30
            elif avg_views < 100000:
                score = 50 + ((avg_views - 10000) / 90000) * 30
            else:
                score = 80 + min(((avg_views - 100000) / 900000) * 20, 20)

            return round(min(score, 100))

        except Exception as e:
            logger.error(f"Erreur calcul search volume pour {artist_name}: {e}")
            return 0

    async def _calculate_competition_score(self, artist_name: str) -> float:
        """
        Calculer le score de compétition (0-100, plus haut = plus de compétition)
        Analyse la densité de contenu concurrent pour "[artist] type beat"
        """
        try:
            search_query = f"{artist_name} type beat"

            # Rechercher les vidéos concurrentes
            search_results = self.youtube_service.search_videos(
                query=search_query,
                max_results=50
            )

            if not search_results:
                return 0  # Pas de compétition = score 0

            # Analyser la qualité de la compétition
            high_quality_competitors = 0
            total_competitor_subscribers = 0
            recent_uploads = 0

            for video in search_results:
                channel_id = video.get("snippet", {}).get("channelId", "")
                if not channel_id:
                    continue

                # Récupérer les stats de la chaîne
                channel_stats = self.youtube_service.get_channel_stats(channel_id)
                if channel_stats:
                    subscriber_count = int(channel_stats.get("subscriberCount", 0))
                    total_competitor_subscribers += subscriber_count

                    # Concurrent de qualité = plus de 10K abonnés
                    if subscriber_count > 10000:
                        high_quality_competitors += 1

                # Vérifier si la vidéo est récente (moins de 6 mois)
                published_at = video.get("snippet", {}).get("publishedAt", "")
                if self._is_recent_video(published_at):
                    recent_uploads += 1

            # Calcul du score de compétition
            # Facteurs: nombre de concurrents de qualité, uploads récents, abonnés moyens
            quality_factor = (high_quality_competitors / len(search_results)) * 40
            recency_factor = (recent_uploads / len(search_results)) * 30

            avg_subscribers = total_competitor_subscribers / len(search_results) if search_results else 0
            subscriber_factor = min((avg_subscribers / 100000) * 30, 30)

            competition_score = quality_factor + recency_factor + subscriber_factor

            return round(min(competition_score, 100))

        except Exception as e:
            logger.error(f"Erreur calcul competition pour {artist_name}: {e}")
            return 50  # Score moyen par défaut

    async def _calculate_optimization_score(self, artist_name: str) -> float:
        """
        Calculer le score d'opportunité d'optimisation (0-100)
        Analyse les gaps SEO et opportunités de positionnement
        """
        try:
            search_query = f"{artist_name} type beat"

            # Rechercher les résultats existants
            search_results = self.youtube_service.search_videos(
                query=search_query,
                max_results=20  # Top 20 résultats
            )

            if not search_results:
                return 100  # Aucun contenu = opportunité maximale

            # Analyser les opportunités d'optimisation
            optimization_factors = []

            # 1. Analyse des titres - rechercher des patterns faibles
            weak_titles = 0
            for video in search_results:
                title = video.get("snippet", {}).get("title", "").lower()

                # Titre faible = pas le nom exact de l'artiste, format générique
                if artist_name.lower() not in title or len(title.split()) < 3:
                    weak_titles += 1

            title_opportunity = (weak_titles / len(search_results)) * 30
            optimization_factors.append(title_opportunity)

            # 2. Analyse de la fraîcheur du contenu
            old_content = 0
            for video in search_results:
                published_at = video.get("snippet", {}).get("publishedAt", "")
                if not self._is_recent_video(published_at, months_threshold=12):
                    old_content += 1

            freshness_opportunity = (old_content / len(search_results)) * 25
            optimization_factors.append(freshness_opportunity)

            # 3. Analyse de la diversité des créateurs
            unique_channels = set()
            for video in search_results:
                channel_id = video.get("snippet", {}).get("channelId", "")
                if channel_id:
                    unique_channels.add(channel_id)

            # Plus de diversité = moins d'opportunité (marché saturé par différents créateurs)
            diversity_ratio = len(unique_channels) / len(search_results)
            monopoly_opportunity = (1 - diversity_ratio) * 25
            optimization_factors.append(monopoly_opportunity)

            # 4. Analyse de la qualité moyenne des vignettes/descriptions
            low_quality_content = 0
            for video in search_results:
                description = video.get("snippet", {}).get("description", "")
                # Contenu de faible qualité = description courte
                if len(description) < 100:
                    low_quality_content += 1

            quality_opportunity = (low_quality_content / len(search_results)) * 20
            optimization_factors.append(quality_opportunity)

            # Score final d'optimisation
            optimization_score = sum(optimization_factors)

            return round(min(optimization_score, 100))

        except Exception as e:
            logger.error(f"Erreur calcul optimization pour {artist_name}: {e}")
            return 50  # Score moyen par défaut

    def _is_recent_video(self, published_at: str, months_threshold: int = 6) -> bool:
        """Vérifier si une vidéo est récente (moins de X mois)"""
        try:
            if not published_at:
                return False

            # Parser la date ISO format YouTube
            published_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
            threshold_date = datetime.now().replace(tzinfo=published_date.tzinfo) - timedelta(days=months_threshold * 30)

            return published_date > threshold_date

        except Exception:
            return False

    async def batch_score_artists(self, artist_names: List[str]) -> List[Dict]:
        """
        Calculer les scores pour une liste d'artistes en batch
        Optimisé pour traiter plusieurs artistes efficacement
        """
        # Traiter par batches de 10 pour éviter la surcharge API
        batch_size = 10
        all_results = []

        for i in range(0, len(artist_names), batch_size):
            batch = artist_names[i:i + batch_size]

            # Traiter le batch en parallèle
            tasks = [self.calculate_artist_score(artist) for artist in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filtrer les exceptions
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Erreur batch scoring: {result}")
                else:
                    all_results.append(result)

            # Pause courte entre les batches pour respecter les quotas API
            await asyncio.sleep(1)

        return all_results

    def _calculate_search_volume_from_cache(self, search_results: List, video_stats_cache: Dict) -> float:
        """Calculer le score de volume de recherche à partir du cache"""
        if not search_results:
            return 0

        total_views = 0
        valid_videos = 0

        for video in search_results:
            video_id = video.get("id", "")
            if video_id in video_stats_cache:
                view_count = video_stats_cache[video_id].get("viewCount", 0)
                total_views += view_count
                valid_videos += 1

        if valid_videos == 0:
            return 0

        avg_views = total_views / valid_videos

        # Même logique de calcul que l'ancienne méthode
        if avg_views < 1000:
            score = (avg_views / 1000) * 20
        elif avg_views < 10000:
            score = 20 + ((avg_views - 1000) / 9000) * 30
        elif avg_views < 100000:
            score = 50 + ((avg_views - 10000) / 90000) * 30
        else:
            score = 80 + min(((avg_views - 100000) / 900000) * 20, 20)

        return round(min(score, 100))

    def _calculate_competition_from_cache(self, search_results: List, channel_stats_cache: Dict) -> float:
        """Calculer le score de compétition à partir du cache"""
        if not search_results:
            return 0

        high_quality_competitors = 0
        total_competitor_subscribers = 0
        recent_uploads = 0

        for video in search_results:
            channel_id = video.get("snippet", {}).get("channelId", "")

            # Analyser les stats de la chaîne depuis le cache
            if channel_id in channel_stats_cache:
                subscriber_count = channel_stats_cache[channel_id].get("subscriberCount", 0)
                total_competitor_subscribers += subscriber_count

                # Concurrent de qualité = plus de 10K abonnés
                if subscriber_count > 10000:
                    high_quality_competitors += 1

            # Vérifier si la vidéo est récente (moins de 6 mois)
            published_at = video.get("snippet", {}).get("publishedAt", "")
            if self._is_recent_video(published_at):
                recent_uploads += 1

        # Calcul du score de compétition (même logique)
        quality_factor = (high_quality_competitors / len(search_results)) * 40
        recency_factor = (recent_uploads / len(search_results)) * 30

        avg_subscribers = total_competitor_subscribers / len(search_results) if search_results else 0
        subscriber_factor = min((avg_subscribers / 100000) * 30, 30)

        competition_score = quality_factor + recency_factor + subscriber_factor

        return round(min(competition_score, 100))

    def _calculate_optimization_from_cache(self, search_results: List, artist_name: str) -> float:
        """Calculer le score d'optimisation à partir du cache"""
        if not search_results:
            return 100  # Aucun contenu = opportunité maximale

        optimization_factors = []

        # 1. Analyse des titres - rechercher des patterns faibles
        weak_titles = 0
        for video in search_results:
            title = video.get("snippet", {}).get("title", "").lower()

            # Titre faible = pas le nom exact de l'artiste, format générique
            if artist_name.lower() not in title or len(title.split()) < 3:
                weak_titles += 1

        title_opportunity = (weak_titles / len(search_results)) * 30
        optimization_factors.append(title_opportunity)

        # 2. Analyse de la fraîcheur du contenu
        old_content = 0
        for video in search_results:
            published_at = video.get("snippet", {}).get("publishedAt", "")
            if not self._is_recent_video(published_at, months_threshold=12):
                old_content += 1

        freshness_opportunity = (old_content / len(search_results)) * 25
        optimization_factors.append(freshness_opportunity)

        # 3. Analyse de la diversité des créateurs
        unique_channels = set()
        for video in search_results:
            channel_id = video.get("snippet", {}).get("channelId", "")
            if channel_id:
                unique_channels.add(channel_id)

        # Plus de diversité = moins d'opportunité (marché saturé par différents créateurs)
        diversity_ratio = len(unique_channels) / len(search_results)
        monopoly_opportunity = (1 - diversity_ratio) * 25
        optimization_factors.append(monopoly_opportunity)

        # 4. Analyse de la qualité moyenne des vignettes/descriptions
        low_quality_content = 0
        for video in search_results:
            description = video.get("snippet", {}).get("description", "")
            # Contenu de faible qualité = description courte
            if len(description) < 100:
                low_quality_content += 1

        quality_opportunity = (low_quality_content / len(search_results)) * 20
        optimization_factors.append(quality_opportunity)

        # Score final d'optimisation
        optimization_score = sum(optimization_factors)

        return round(min(optimization_score, 100))

    def get_score_interpretation(self, score: float) -> Dict:
        """Interpréter le score TubeBuddy et donner des recommandations"""
        if score >= 80:
            category = "Excellent"
            recommendation = "Opportunité exceptionnelle pour type beats - Forte demande, faible compétition"
        elif score >= 65:
            category = "Très bon"
            recommendation = "Bonne opportunité - Demande solide avec compétition modérée"
        elif score >= 50:
            category = "Moyen"
            recommendation = "Opportunité modérée - À considérer selon votre stratégie"
        elif score >= 30:
            category = "Faible"
            recommendation = "Opportunité limitée - Compétition élevée ou faible demande"
        else:
            category = "Très faible"
            recommendation = "Éviter - Marché saturé ou sans demande"

        return {
            'score': score,
            'category': category,
            'recommendation': recommendation
        }

    async def _estimate_total_video_count(self, search_results: List, search_query: str) -> int:
        """
        Estimer le nombre total de vidéos selon la méthode de l'étude
        Analyse la diversité et l'activité pour extrapoler
        """
        if not search_results:
            return 0

        # Vérifier le cache d'abord
        cached_count = self.cache_service.get_search_count_estimate(search_query)
        if cached_count is not None:
            return cached_count

        # Analyser l'échantillon pour extrapoler
        unique_channels = set()
        recent_videos = 0  # Moins de 6 mois
        very_recent_videos = 0  # Moins de 1 mois

        for video in search_results:
            channel_id = video.get("snippet", {}).get("channelId", "")
            if channel_id:
                unique_channels.add(channel_id)

            published_at = video.get("snippet", {}).get("publishedAt", "")
            if self._is_recent_video(published_at, months_threshold=6):
                recent_videos += 1
            if self._is_recent_video(published_at, months_threshold=1):
                very_recent_videos += 1

        # Calcul d'extrapolation
        sample_size = len(search_results)
        diversity_ratio = len(unique_channels) / sample_size if sample_size > 0 else 0
        recent_ratio = recent_videos / sample_size if sample_size > 0 else 0
        very_recent_ratio = very_recent_videos / sample_size if sample_size > 0 else 0

        # Estimation basée sur l'activité observée
        # Plus de diversité + activité récente = plus de volume total
        base_multiplier = 1000  # Facteur de base pour 50 résultats échantillon

        # Facteurs d'extrapolation
        diversity_factor = 1 + (diversity_ratio * 10)  # Plus de chaînes = plus de contenu total
        activity_factor = 1 + (recent_ratio * 5) + (very_recent_ratio * 3)  # Activité récente

        estimated_count = int(sample_size * base_multiplier * diversity_factor * activity_factor)

        # Limites réalistes selon les observations TubeBuddy
        estimated_count = max(1000, min(estimated_count, 5000000))

        # Mettre en cache l'estimation
        self.cache_service.cache_search_count_estimate(search_query, estimated_count)

        logger.info(f"Estimation vidéos pour '{search_query}': {estimated_count} (diversité: {diversity_ratio:.2f}, activité: {recent_ratio:.2f})")

        return estimated_count

    def _calculate_search_volume_tubebuddy_formula(self, trends_score: float, estimated_video_count: int) -> float:
        """
        Calculer le Search Volume selon la formule de l'étude :
        Score_Opportunité = (Google_Trends_Score × 1000) × (1 / log(Nombre_Résultats_YouTube))
        """
        if estimated_video_count <= 1:
            # Éviter log(0) ou log(1)
            return min(trends_score * 10, 100)  # Niche vierge = score élevé

        try:
            # Formule de l'étude
            log_video_count = math.log10(estimated_video_count)
            opportunity_score = (trends_score * 10) * (1 / log_video_count)

            # Normaliser sur 0-100
            # Observation : log10 varie de ~3 (1K vidéos) à ~6.7 (5M vidéos)
            # 1/log10 varie donc de ~0.33 à ~0.15
            normalized_score = min(opportunity_score * 3, 100)  # Facteur de normalisation

            logger.info(f"Search Volume: Trends({trends_score}) × (1/log10({estimated_video_count})) = {normalized_score:.1f}")

            return max(0, normalized_score)

        except Exception as e:
            logger.error(f"Erreur calcul search volume: {e}")
            return 0

    def _calculate_competition_tubebuddy_formula(self, search_results: List, channel_stats_cache: Dict, estimated_video_count: int) -> float:
        """
        Calculer la Competition selon la méthode TubeBuddy :
        Basé sur le nombre total de résultats + qualité des concurrents
        """
        if not search_results:
            return 0

        # 1. Facteur volume : plus de vidéos = plus de compétition
        volume_factor = min(math.log10(estimated_video_count) * 15, 60) if estimated_video_count > 1 else 0

        # 2. Analyser la qualité des concurrents
        high_quality_competitors = 0
        total_subscribers = 0
        total_views = 0
        recent_uploads = 0

        for video in search_results:
            channel_id = video.get("snippet", {}).get("channelId", "")

            # Stats de la chaîne
            if channel_id in channel_stats_cache and channel_stats_cache[channel_id]:
                stats = channel_stats_cache[channel_id]
                subscriber_count = int(stats.get("subscriberCount", 0))
                view_count = int(stats.get("viewCount", 0))

                total_subscribers += subscriber_count
                total_views += view_count

                # Concurrent de qualité selon TubeBuddy
                if subscriber_count > 10000:
                    high_quality_competitors += 1

            # Contenu récent
            published_at = video.get("snippet", {}).get("publishedAt", "")
            if self._is_recent_video(published_at, months_threshold=6):
                recent_uploads += 1

        # 3. Calcul des facteurs de compétition
        if len(search_results) > 0:
            quality_ratio = high_quality_competitors / len(search_results)
            recent_ratio = recent_uploads / len(search_results)
            avg_subscribers = total_subscribers / len(search_results)

            quality_factor = quality_ratio * 25  # Jusqu'à 25 points
            recency_factor = recent_ratio * 10   # Jusqu'à 10 points
            subscriber_factor = min(avg_subscribers / 50000 * 5, 5)  # Jusqu'à 5 points

            competition_score = volume_factor + quality_factor + recency_factor + subscriber_factor
        else:
            competition_score = volume_factor

        logger.info(f"Competition: Volume({volume_factor:.1f}) + Qualité({quality_factor:.1f}) + Récent({recency_factor:.1f}) = {competition_score:.1f}")

        return min(competition_score, 100)

    def _calculate_optimization_tubebuddy_formula(self, search_results: List, artist_name: str) -> float:
        """
        Calculer l'Optimization selon TubeBuddy : densité d'optimisation des concurrents
        Plus les concurrents sont mal optimisés = plus d'opportunité
        """
        if not search_results:
            return 100  # Aucun concurrent = opportunité maximale

        optimization_opportunities = 0
        total_analyzed = len(search_results)

        for video in search_results:
            snippet = video.get("snippet", {})
            title = snippet.get("title", "").lower()
            description = snippet.get("description", "")

            opportunity_points = 0

            # 1. Titre mal optimisé
            if artist_name.lower() not in title:
                opportunity_points += 25  # Pas le nom de l'artiste dans le titre

            if "type beat" not in title:
                opportunity_points += 25  # Pas "type beat" dans le titre

            if len(title.split()) < 4:
                opportunity_points += 15  # Titre trop court

            # 2. Description faible
            if len(description) < 100:
                opportunity_points += 20  # Description trop courte

            if "type beat" not in description.lower():
                opportunity_points += 10  # Pas de mots-clés dans la description

            # 3. Format non standard
            if not any(format_word in title for format_word in ["beat", "instrumental", "type"]):
                opportunity_points += 5  # Format non standard

            # Normaliser sur 100
            optimization_opportunities += min(opportunity_points, 100)

        # Score moyen d'opportunité
        avg_opportunity = optimization_opportunities / total_analyzed if total_analyzed > 0 else 0

        logger.info(f"Optimization: {avg_opportunity:.1f}% d'opportunité moyenne détectée")

        return min(avg_opportunity, 100)

    async def _get_cached_stats(self, search_results: List) -> Tuple[Dict, Dict]:
        """
        Récupérer les stats vidéos et chaînes avec cache optimisé
        """
        video_ids = [v.get("id", "") for v in search_results if v.get("id")]
        channel_ids = [v.get("snippet", {}).get("channelId", "") for v in search_results
                      if v.get("snippet", {}).get("channelId")]

        # Récupérer depuis le cache d'abord
        video_stats_cache = self.cache_service.get_batch_video_stats(video_ids)
        channel_stats_cache = self.cache_service.get_batch_channel_stats(channel_ids)

        # Identifier ce qui manque
        missing_videos = [vid for vid in video_ids if vid not in video_stats_cache]
        missing_channels = [cid for cid in channel_ids if cid not in channel_stats_cache]

        # Récupérer les données manquantes
        if missing_videos:
            for video_id in missing_videos:
                stats = self.youtube_service.get_video_stats(video_id)
                if stats:
                    video_stats_cache[video_id] = stats
                    self.cache_service.cache_video_stats(video_id, stats)

        if missing_channels:
            for channel_id in missing_channels:
                stats = self.youtube_service.get_channel_stats(channel_id)
                if stats:
                    channel_stats_cache[channel_id] = stats
                    self.cache_service.cache_channel_stats(channel_id, stats)

        return video_stats_cache, channel_stats_cache
