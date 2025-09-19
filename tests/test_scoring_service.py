import pytest
from app.services.scoring_service import ScoringService

class TestScoringService:
    def setup_method(self):
        self.scoring_service = ScoringService()

    def test_calculate_score_basic(self):
        """Test du calcul de score avec des données basiques"""
        artist_data = {
            'spotify_popularity': 50,
            'spotify_followers': 100000,
            'youtube_subscribers': 50000,
            'youtube_views': 1000000,
            'youtube_videos_count': 50
        }
        
        result = self.scoring_service.calculate_score(artist_data)
        
        assert 'final_score' in result
        assert 'breakdown' in result
        assert 'weights' in result
        assert isinstance(result['final_score'], float)
        assert 0 <= result['final_score'] <= 100

    def test_calculate_score_high_potential(self):
        """Test avec un artiste à fort potentiel"""
        artist_data = {
            'spotify_popularity': 65,
            'spotify_followers': 75000,
            'youtube_subscribers': 100000,
            'youtube_views': 2000000,
            'youtube_videos_count': 80
        }
        
        result = self.scoring_service.calculate_score(artist_data)
        
        # Un artiste avec ces métriques devrait avoir un bon score
        assert result['final_score'] > 60

    def test_calculate_score_low_potential(self):
        """Test avec un artiste à faible potentiel"""
        artist_data = {
            'spotify_popularity': 10,
            'spotify_followers': 500,
            'youtube_subscribers': 200,
            'youtube_views': 5000,
            'youtube_videos_count': 5
        }
        
        result = self.scoring_service.calculate_score(artist_data)
        
        # Un artiste avec ces métriques devrait avoir un score faible
        assert result['final_score'] < 30

    def test_normalize_spotify_popularity(self):
        """Test de la normalisation de la popularité Spotify"""
        # Test des cas limites
        assert self.scoring_service._normalize_spotify_popularity(0) == 0.0
        assert self.scoring_service._normalize_spotify_popularity(100) > 0.8
        
        # Test de la zone émergente (bonus)
        score_30 = self.scoring_service._normalize_spotify_popularity(30)
        score_50 = self.scoring_service._normalize_spotify_popularity(50)
        assert score_50 > score_30

    def test_normalize_followers(self):
        """Test de la normalisation des followers"""
        # Test avec des followers Spotify
        assert self.scoring_service._normalize_followers(0, 'spotify_followers') == 0.0
        assert self.scoring_service._normalize_followers(500, 'spotify_followers') == 0.1
        
        # Test du point optimal
        optimal_score = self.scoring_service._normalize_followers(50000, 'spotify_followers')
        lower_score = self.scoring_service._normalize_followers(10000, 'spotify_followers')
        assert optimal_score > lower_score

    def test_calculate_youtube_engagement(self):
        """Test du calcul d'engagement YouTube"""
        # Bon engagement
        good_engagement_data = {
            'youtube_views': 1000000,
            'youtube_subscribers': 50000
        }
        good_score = self.scoring_service._calculate_youtube_engagement(good_engagement_data)
        
        # Mauvais engagement
        bad_engagement_data = {
            'youtube_views': 10000,
            'youtube_subscribers': 50000
        }
        bad_score = self.scoring_service._calculate_youtube_engagement(bad_engagement_data)
        
        assert good_score > bad_score

    def test_calculate_growth_potential(self):
        """Test du calcul du potentiel de croissance"""
        # Artiste émergent (bon potentiel)
        emerging_data = {
            'spotify_followers': 25000,
            'youtube_subscribers': 50000,
            'spotify_popularity': 45
        }
        emerging_score = self.scoring_service._calculate_growth_potential(emerging_data)
        
        # Artiste établi (potentiel limité)
        established_data = {
            'spotify_followers': 2000000,
            'youtube_subscribers': 5000000,
            'spotify_popularity': 90
        }
        established_score = self.scoring_service._calculate_growth_potential(established_data)
        
        assert emerging_score > established_score

    def test_get_score_interpretation(self):
        """Test de l'interprétation des scores"""
        # Score excellent
        excellent = self.scoring_service.get_score_interpretation(85)
        assert excellent['category'] == 'Excellent'
        
        # Score moyen
        average = self.scoring_service.get_score_interpretation(55)
        assert average['category'] == 'Moyen'
        
        # Score faible
        low = self.scoring_service.get_score_interpretation(25)
        assert low['category'] == 'Très faible'

    def test_weights_sum_to_one(self):
        """Vérifier que les poids totalisent 1.0"""
        total_weight = sum(self.scoring_service.weights.values())
        assert abs(total_weight - 1.0) < 0.001  # Tolérance pour les erreurs de float

    def test_score_consistency(self):
        """Test de cohérence : même données = même score"""
        artist_data = {
            'spotify_popularity': 60,
            'spotify_followers': 80000,
            'youtube_subscribers': 120000,
            'youtube_views': 3000000,
            'youtube_videos_count': 100
        }
        
        result1 = self.scoring_service.calculate_score(artist_data)
        result2 = self.scoring_service.calculate_score(artist_data)
        
        assert result1['final_score'] == result2['final_score']
