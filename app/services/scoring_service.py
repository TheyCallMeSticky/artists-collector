import math
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class ScoringService:
    def __init__(self):
        # Poids pour chaque métrique (total = 1.0)
        self.weights = {
            'spotify_popularity': 0.15,
            'spotify_followers': 0.20,
            'youtube_subscribers': 0.20,
            'youtube_views': 0.15,
            'youtube_engagement': 0.10,
            'growth_potential': 0.10,
            'content_frequency': 0.10
        }
        
        # Seuils pour la normalisation
        self.thresholds = {
            'spotify_followers': {
                'min': 1000,
                'max': 1000000,
                'optimal': 50000
            },
            'youtube_subscribers': {
                'min': 1000,
                'max': 1000000,
                'optimal': 100000
            },
            'youtube_views': {
                'min': 10000,
                'max': 10000000,
                'optimal': 500000
            },
            'spotify_popularity': {
                'min': 10,
                'max': 100,
                'optimal': 60
            }
        }

    def calculate_score(self, artist_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculer le score global d'un artiste"""
        try:
            scores = {}
            total_score = 0.0
            
            # Score Spotify Popularity (0-100)
            spotify_popularity = artist_data.get('spotify_popularity', 0)
            scores['spotify_popularity'] = self._normalize_spotify_popularity(spotify_popularity)
            total_score += scores['spotify_popularity'] * self.weights['spotify_popularity']
            
            # Score Spotify Followers
            spotify_followers = artist_data.get('spotify_followers', 0)
            scores['spotify_followers'] = self._normalize_followers(spotify_followers, 'spotify_followers')
            total_score += scores['spotify_followers'] * self.weights['spotify_followers']
            
            # Score YouTube Subscribers
            youtube_subscribers = artist_data.get('youtube_subscribers', 0)
            scores['youtube_subscribers'] = self._normalize_followers(youtube_subscribers, 'youtube_subscribers')
            total_score += scores['youtube_subscribers'] * self.weights['youtube_subscribers']
            
            # Score YouTube Views
            youtube_views = artist_data.get('youtube_views', 0)
            scores['youtube_views'] = self._normalize_views(youtube_views)
            total_score += scores['youtube_views'] * self.weights['youtube_views']
            
            # Score YouTube Engagement
            youtube_engagement = self._calculate_youtube_engagement(artist_data)
            scores['youtube_engagement'] = youtube_engagement
            total_score += scores['youtube_engagement'] * self.weights['youtube_engagement']
            
            # Score Growth Potential
            growth_potential = self._calculate_growth_potential(artist_data)
            scores['growth_potential'] = growth_potential
            total_score += scores['growth_potential'] * self.weights['growth_potential']
            
            # Score Content Frequency
            content_frequency = self._calculate_content_frequency(artist_data)
            scores['content_frequency'] = content_frequency
            total_score += scores['content_frequency'] * self.weights['content_frequency']
            
            # Score final (0-100)
            final_score = min(100.0, max(0.0, total_score * 100))
            
            return {
                'final_score': round(final_score, 2),
                'breakdown': scores,
                'weights': self.weights,
                'calculation_date': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erreur lors du calcul du score: {str(e)}")
            return {
                'final_score': 0.0,
                'breakdown': {},
                'error': str(e)
            }

    def _normalize_spotify_popularity(self, popularity: int) -> float:
        """Normaliser la popularité Spotify (0-100 -> 0-1)"""
        if popularity <= 0:
            return 0.0
        
        # Courbe logarithmique pour favoriser les artistes émergents
        normalized = math.log(popularity + 1) / math.log(101)
        
        # Bonus pour la zone "émergente" (20-60)
        if 20 <= popularity <= 60:
            normalized *= 1.2
        
        return min(1.0, normalized)

    def _normalize_followers(self, followers: int, metric_type: str) -> float:
        """Normaliser le nombre de followers/subscribers"""
        if followers <= 0:
            return 0.0
        
        thresholds = self.thresholds[metric_type]
        
        if followers < thresholds['min']:
            return 0.1  # Score minimal pour les très petits comptes
        
        if followers >= thresholds['max']:
            return 0.9  # Plafonner pour éviter de favoriser les très gros
        
        # Courbe logarithmique avec point optimal
        optimal = thresholds['optimal']
        if followers <= optimal:
            # Croissance rapide jusqu'au point optimal
            normalized = math.log(followers / thresholds['min']) / math.log(optimal / thresholds['min'])
        else:
            # Croissance plus lente après le point optimal
            excess_ratio = (followers - optimal) / (thresholds['max'] - optimal)
            normalized = 1.0 + (excess_ratio * 0.2)  # Bonus limité
        
        return min(1.0, max(0.1, normalized))

    def _normalize_views(self, views: int) -> float:
        """Normaliser le nombre de vues YouTube"""
        if views <= 0:
            return 0.0
        
        thresholds = self.thresholds['youtube_views']
        
        if views < thresholds['min']:
            return 0.1
        
        if views >= thresholds['max']:
            return 0.9
        
        # Normalisation logarithmique
        normalized = math.log(views / thresholds['min']) / math.log(thresholds['max'] / thresholds['min'])
        return min(1.0, max(0.1, normalized))

    def _calculate_youtube_engagement(self, artist_data: Dict[str, Any]) -> float:
        """Calculer le score d'engagement YouTube"""
        try:
            youtube_views = artist_data.get('youtube_views', 0)
            youtube_subscribers = artist_data.get('youtube_subscribers', 0)
            
            if youtube_subscribers <= 0 or youtube_views <= 0:
                return 0.0
            
            # Ratio vues/abonnés (indicateur d'engagement)
            view_to_subscriber_ratio = youtube_views / youtube_subscribers
            
            # Normaliser le ratio (ratio optimal autour de 10-50)
            if view_to_subscriber_ratio < 5:
                return 0.2
            elif view_to_subscriber_ratio > 100:
                return 0.9
            else:
                # Courbe logarithmique
                normalized = math.log(view_to_subscriber_ratio / 5) / math.log(20)
                return min(1.0, max(0.2, normalized))
                
        except Exception as e:
            logger.error(f"Erreur calcul engagement YouTube: {str(e)}")
            return 0.0

    def _calculate_growth_potential(self, artist_data: Dict[str, Any]) -> float:
        """Calculer le potentiel de croissance basé sur les métriques"""
        try:
            spotify_followers = artist_data.get('spotify_followers', 0)
            youtube_subscribers = artist_data.get('youtube_subscribers', 0)
            spotify_popularity = artist_data.get('spotify_popularity', 0)
            
            # Zone optimale pour les "type beats" : artistes émergents mais pas trop petits
            growth_score = 0.0
            
            # Bonus pour les artistes dans la zone émergente
            if 1000 <= spotify_followers <= 100000:
                growth_score += 0.4
            
            if 1000 <= youtube_subscribers <= 200000:
                growth_score += 0.4
            
            if 15 <= spotify_popularity <= 70:
                growth_score += 0.2
            
            # Malus pour les artistes trop établis
            if spotify_followers > 500000 or youtube_subscribers > 1000000:
                growth_score *= 0.5
            
            return min(1.0, growth_score)
            
        except Exception as e:
            logger.error(f"Erreur calcul potentiel de croissance: {str(e)}")
            return 0.0

    def _calculate_content_frequency(self, artist_data: Dict[str, Any]) -> float:
        """Calculer le score basé sur la fréquence de contenu"""
        try:
            youtube_videos_count = artist_data.get('youtube_videos_count', 0)
            
            if youtube_videos_count <= 0:
                return 0.0
            
            # Score basé sur le nombre de vidéos (indicateur d'activité)
            if youtube_videos_count < 10:
                return 0.2
            elif youtube_videos_count > 1000:
                return 0.7  # Trop de contenu peut diluer la qualité
            else:
                # Courbe logarithmique avec optimum autour de 50-200 vidéos
                normalized = math.log(youtube_videos_count / 10) / math.log(100)
                return min(1.0, max(0.2, normalized))
                
        except Exception as e:
            logger.error(f"Erreur calcul fréquence contenu: {str(e)}")
            return 0.0

    def get_score_interpretation(self, score: float) -> Dict[str, Any]:
        """Interpréter le score et donner des recommandations"""
        if score >= 80:
            category = "Excellent"
            recommendation = "Artiste très prometteur pour les type beats, forte recommandation"
        elif score >= 65:
            category = "Très bon"
            recommendation = "Bon potentiel pour les type beats, recommandé"
        elif score >= 50:
            category = "Moyen"
            recommendation = "Potentiel modéré, à surveiller"
        elif score >= 30:
            category = "Faible"
            recommendation = "Potentiel limité, pas prioritaire"
        else:
            category = "Très faible"
            recommendation = "Peu d'intérêt pour les type beats"
        
        return {
            'score': score,
            'category': category,
            'recommendation': recommendation
        }
