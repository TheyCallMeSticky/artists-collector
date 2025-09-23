"""
Service de scoring TubeBuddy pour évaluer les opportunités d'artistes
Calcule un score basé sur: Search Volume (40%) + Competition (40%) + Optimization (20%)
"""

import asyncio
import re
import logging
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote_plus
from datetime import datetime, timedelta

from app.services.youtube_service import YouTubeService

logger = logging.getLogger(__name__)


class ScoringService:
    def __init__(self):
        self.youtube_service = YouTubeService()

        # Formule TubeBuddy: Search Volume (40%) + Competition (40%) + Optimization (20%)
        self.weights = {
            'search_volume': 0.4,
            'competition': 0.4,  # Note: sera inversé dans le calcul final
            'optimization': 0.2
        }

    async def calculate_artist_score(self, artist_name: str) -> Dict:
        """
        Calculer le score TubeBuddy complet pour un artiste
        OPTIMISÉ: Une seule recherche YouTube + cache des données

        Returns:
            Dict avec search_volume_score, competition_score, optimization_score et overall_score
        """
        try:
            search_query = f"{artist_name} type beat"

            # ÉTAPE 1: UNE SEULE recherche YouTube (50 résultats)
            search_results = self.youtube_service.search_videos(
                query=search_query,
                max_results=50
            )

            if not search_results:
                return {
                    "artist_name": artist_name,
                    "search_volume_score": 0,
                    "competition_score": 0,
                    "optimization_score": 100,  # Aucune compétition = opportunité max
                    "overall_score": 60,  # (0×0.4) + ((100-0)×0.4) + (100×0.2) = 60
                    "components": {
                        "search_volume_weight": 0.4,
                        "competition_weight": 0.4,
                        "optimization_weight": 0.2
                    }
                }

            # ÉTAPE 2: Récupérer les stats des vidéos (pour Search Volume)
            video_stats_cache = {}
            for video in search_results:
                video_id = video.get("id", "")
                if video_id and video_id not in video_stats_cache:
                    stats = self.youtube_service.get_video_stats(video_id)
                    if stats:
                        video_stats_cache[video_id] = stats

            # ÉTAPE 3: Récupérer les stats des chaînes (pour Competition) - avec cache
            channel_stats_cache = {}
            for video in search_results:
                channel_id = video.get("snippet", {}).get("channelId", "")
                if channel_id and channel_id not in channel_stats_cache:
                    stats = self.youtube_service.get_channel_stats(channel_id)
                    if stats:
                        channel_stats_cache[channel_id] = stats

            # ÉTAPE 4: Calculer les scores en utilisant les données cachées
            search_volume_score = self._calculate_search_volume_from_cache(
                search_results, video_stats_cache
            )
            competition_score = self._calculate_competition_from_cache(
                search_results, channel_stats_cache
            )
            optimization_score = self._calculate_optimization_from_cache(
                search_results[:20], artist_name  # Top 20 pour optimisation
            )

            # ÉTAPE 5: Score final
            overall_score = (
                (search_volume_score * 0.4) +
                ((100 - competition_score) * 0.4) +
                (optimization_score * 0.2)
            )

            return {
                "artist_name": artist_name,
                "search_volume_score": round(search_volume_score),
                "competition_score": round(competition_score),
                "optimization_score": round(optimization_score),
                "overall_score": round(overall_score),
                "components": {
                    "search_volume_weight": 0.4,
                    "competition_weight": 0.4,
                    "optimization_weight": 0.2
                },
                "api_calls_saved": f"Économie: ~{len(set(video.get('snippet', {}).get('channelId', '') for video in search_results))} appels chaînes"
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
