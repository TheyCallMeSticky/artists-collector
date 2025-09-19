import pytest
from unittest.mock import Mock, patch, MagicMock
from app.services.spotify_service import SpotifyService
from app.services.youtube_service import YouTubeService

class TestSpotifyService:
    @patch('app.services.spotify_service.spotipy.Spotify')
    @patch.dict('os.environ', {
        'SPOTIFY_CLIENT_ID': 'test_client_id',
        'SPOTIFY_CLIENT_SECRET': 'test_client_secret'
    })
    def test_spotify_service_init(self, mock_spotify):
        """Test de l'initialisation du service Spotify"""
        service = SpotifyService()
        assert service.sp is not None

    @patch.dict('os.environ', {}, clear=True)
    def test_spotify_service_missing_credentials(self):
        """Test avec des credentials manquants"""
        with pytest.raises(ValueError, match="SPOTIFY_CLIENT_ID et SPOTIFY_CLIENT_SECRET doivent être définis"):
            SpotifyService()

    @patch('app.services.spotify_service.spotipy.Spotify')
    @patch.dict('os.environ', {
        'SPOTIFY_CLIENT_ID': 'test_client_id',
        'SPOTIFY_CLIENT_SECRET': 'test_client_secret'
    })
    def test_search_artist_success(self, mock_spotify):
        """Test de recherche d'artiste réussie"""
        # Mock de la réponse Spotify
        mock_response = {
            'artists': {
                'items': [{
                    'id': 'test_id',
                    'name': 'Test Artist',
                    'followers': {'total': 100000},
                    'popularity': 75
                }]
            }
        }
        
        mock_spotify_instance = Mock()
        mock_spotify_instance.search.return_value = mock_response
        mock_spotify.return_value = mock_spotify_instance
        
        service = SpotifyService()
        result = service.search_artist('Test Artist')
        
        assert result is not None
        assert result['id'] == 'test_id'
        assert result['name'] == 'Test Artist'

    @patch('app.services.spotify_service.spotipy.Spotify')
    @patch.dict('os.environ', {
        'SPOTIFY_CLIENT_ID': 'test_client_id',
        'SPOTIFY_CLIENT_SECRET': 'test_client_secret'
    })
    def test_search_artist_not_found(self, mock_spotify):
        """Test de recherche d'artiste non trouvé"""
        mock_response = {'artists': {'items': []}}
        
        mock_spotify_instance = Mock()
        mock_spotify_instance.search.return_value = mock_response
        mock_spotify.return_value = mock_spotify_instance
        
        service = SpotifyService()
        result = service.search_artist('Unknown Artist')
        
        assert result is None

    @patch('app.services.spotify_service.spotipy.Spotify')
    @patch.dict('os.environ', {
        'SPOTIFY_CLIENT_ID': 'test_client_id',
        'SPOTIFY_CLIENT_SECRET': 'test_client_secret'
    })
    def test_get_artist_info_success(self, mock_spotify):
        """Test de récupération d'infos artiste"""
        mock_response = {
            'id': 'test_id',
            'name': 'Test Artist',
            'followers': {'total': 100000},
            'popularity': 75,
            'genres': ['hip-hop', 'rap'],
            'images': [{'url': 'test_image_url'}]
        }
        
        mock_spotify_instance = Mock()
        mock_spotify_instance.artist.return_value = mock_response
        mock_spotify.return_value = mock_spotify_instance
        
        service = SpotifyService()
        result = service.get_artist_info('test_id')
        
        assert result is not None
        assert result['id'] == 'test_id'
        assert result['followers'] == 100000
        assert result['popularity'] == 75

class TestYouTubeService:
    @patch.dict('os.environ', {
        'YOUTUBE_API_KEY_1': 'test_key_1',
        'YOUTUBE_API_KEY_2': 'test_key_2'
    })
    def test_youtube_service_init(self):
        """Test de l'initialisation du service YouTube"""
        service = YouTubeService()
        assert len(service.api_keys) == 2
        assert service.current_key_index == 0

    @patch.dict('os.environ', {}, clear=True)
    def test_youtube_service_no_keys(self):
        """Test avec aucune clé API"""
        with pytest.raises(ValueError, match="Au moins une clé API YouTube doit être définie"):
            YouTubeService()

    @patch.dict('os.environ', {
        'YOUTUBE_API_KEY_1': 'test_key_1',
        'YOUTUBE_API_KEY_2': 'test_key_2'
    })
    def test_api_key_rotation(self):
        """Test de la rotation des clés API"""
        service = YouTubeService()
        
        initial_key = service.get_current_api_key()
        assert initial_key == 'test_key_1'
        
        service.rotate_api_key()
        rotated_key = service.get_current_api_key()
        assert rotated_key == 'test_key_2'
        
        service.rotate_api_key()
        back_to_first = service.get_current_api_key()
        assert back_to_first == 'test_key_1'

    @patch('app.services.youtube_service.requests.get')
    @patch.dict('os.environ', {'YOUTUBE_API_KEY_1': 'test_key_1'})
    def test_make_request_success(self, mock_get):
        """Test de requête réussie"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'items': [{'id': 'test_id'}]}
        mock_get.return_value = mock_response
        
        service = YouTubeService()
        result = service.make_request('search', {'q': 'test'})
        
        assert result is not None
        assert 'items' in result

    @patch('app.services.youtube_service.requests.get')
    @patch.dict('os.environ', {
        'YOUTUBE_API_KEY_1': 'test_key_1',
        'YOUTUBE_API_KEY_2': 'test_key_2'
    })
    def test_make_request_quota_exceeded(self, mock_get):
        """Test de gestion du quota dépassé"""
        # Premier appel : quota dépassé
        mock_response_403 = Mock()
        mock_response_403.status_code = 403
        
        # Deuxième appel : succès
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {'items': [{'id': 'test_id'}]}
        
        mock_get.side_effect = [mock_response_403, mock_response_200]
        
        service = YouTubeService()
        result = service.make_request('search', {'q': 'test'})
        
        assert result is not None
        assert service.current_key_index == 1  # Clé rotée

    @patch('app.services.youtube_service.requests.get')
    @patch.dict('os.environ', {'YOUTUBE_API_KEY_1': 'test_key_1'})
    def test_search_channel_success(self, mock_get):
        """Test de recherche de chaîne réussie"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'items': [{
                'id': {'channelId': 'test_channel_id'},
                'snippet': {
                    'title': 'Test Channel',
                    'description': 'Test Description',
                    'thumbnails': {'default': {'url': 'test_thumb_url'}}
                }
            }]
        }
        mock_get.return_value = mock_response
        
        service = YouTubeService()
        result = service.search_channel('Test Artist')
        
        assert result is not None
        assert result['channel_id'] == 'test_channel_id'
        assert result['title'] == 'Test Channel'

    @patch('app.services.youtube_service.requests.get')
    @patch.dict('os.environ', {'YOUTUBE_API_KEY_1': 'test_key_1'})
    def test_get_channel_info_success(self, mock_get):
        """Test de récupération d'infos de chaîne"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'items': [{
                'id': 'test_channel_id',
                'snippet': {
                    'title': 'Test Channel',
                    'description': 'Test Description',
                    'publishedAt': '2020-01-01T00:00:00Z'
                },
                'statistics': {
                    'subscriberCount': '100000',
                    'videoCount': '50',
                    'viewCount': '1000000'
                }
            }]
        }
        mock_get.return_value = mock_response
        
        service = YouTubeService()
        result = service.get_channel_info('test_channel_id')
        
        assert result is not None
        assert result['subscriber_count'] == 100000
        assert result['video_count'] == 50
        assert result['view_count'] == 1000000

    @patch.dict('os.environ', {'YOUTUBE_API_KEY_1': 'test_key_1'})
    def test_get_quota_usage(self):
        """Test de récupération de l'usage des quotas"""
        service = YouTubeService()
        
        # Simuler quelques requêtes
        service.requests_per_key['test_key_1'] = 10
        
        usage = service.get_quota_usage()
        
        assert usage['total_keys'] == 1
        assert usage['current_key_index'] == 0
        assert usage['total_requests'] == 10
