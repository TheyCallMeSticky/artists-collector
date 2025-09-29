# Artists Collector API

API backend pour la collecte et l'analyse d'artistes hip-hop émergents avec scoring TubeBuddy automatisé.

## 📋 Fonctionnalités

### 🎵 **Collecte de Données**
- **Spotify** : Extraction des artistes depuis playlists et recommandations
- **YouTube** : Analyse des metrics de performances (vues, abonnés, engagement)
- **Google Trends** : Mesure de la popularité générale des artistes
- **Scheduling automatique** : Collecte périodique avec gestion des quotas API

### 📊 **Scoring TubeBuddy**
- **Algorithme TubeBuddy reproduit** : Score basé sur Search Volume + Competition
- **Métriques combinées** : Google Trends (40%) + YouTube Stats (60%)
- **Coefficient niche musique** : Bonus x1.5 pour les type beats
- **Cache intelligent** : Redis pour optimiser les appels API

### 🔄 **Traitement Multi-Phase**
- **Phase 1** : Extraction initiale des artistes (Spotify)
- **Phase 2** : Enrichissement YouTube (metrics détaillées)
- **Phase TubeBuddy** : Calcul des scores d'opportunité

### 🚀 **API RESTful**
- **5 modules d'endpoints** : Artists, Collection, Scoring, Extraction, Dashboard
- **Documentation Swagger** intégrée
- **Gestion d'erreurs** robuste avec logs détaillés

## 🏗️ Architecture

```
app/
├── api/                    # 🌐 Endpoints FastAPI
│   ├── artists.py         # Gestion CRUD des artistes
│   ├── collection.py      # Collecte de données
│   ├── scoring.py         # Scoring TubeBuddy
│   ├── extraction.py      # Processus d'extraction
│   └── dashboard.py       # Stats et monitoring
├── services/              # 🔧 Services métier
│   ├── scoring_service.py # Algorithme TubeBuddy (propre)
│   ├── youtube_service.py # API YouTube avec cache
│   ├── spotify_service.py # API Spotify
│   ├── trends_service.py  # Google Trends
│   ├── artist_service.py  # CRUD artistes
│   └── processors/        # Processeurs multi-phase
├── models/                # 🗃️ Modèles SQLAlchemy
│   ├── artist.py         # Modèle Artiste
│   └── score.py          # Modèle Score TubeBuddy
├── schemas/               # 📝 Schémas Pydantic
└── db/                    # 💾 Configuration BDD
```

## 🚦 Démarrage Rapide

### Prérequis
- Docker & Docker Compose
- Clés API : Spotify, YouTube (12 clés), Redis

### Configuration
1. **Variables d'environnement** (`.env`) :
```bash
# Spotify API
SPOTIFY_CLIENT_ID=your_spotify_id
SPOTIFY_CLIENT_SECRET=your_spotify_secret

# YouTube API (12 clés pour rate limiting)
YOUTUBE_API_KEY_1=AIza...
YOUTUBE_API_KEY_2=AIza...
# ... jusqu'à YOUTUBE_API_KEY_12

# Database
ARTISTS_POSTGRES_DB=artists_collector
ARTISTS_POSTGRES_USER=artists_user
ARTISTS_POSTGRES_PASSWORD=artists_password

# Redis
REDIS_URL=redis://redis:6379/1
```

### Lancement
```bash
# Depuis le dossier racine du projet
docker-compose up artists-collector artists-postgres redis
```

### Accès
- **API** : http://localhost:8001
- **Documentation** : http://localhost:8001/docs
- **Dashboard** : http://localhost:3002

## 📡 Endpoints Principaux

### 🎤 Artists
- `GET /artists` - Liste des artistes avec filtres
- `POST /artists` - Créer un artiste
- `GET /artists/{id}` - Détails d'un artiste

### 📈 Scoring TubeBuddy
- `GET /scoring/opportunities` - Top artistes par score
- `POST /scoring/calculate/{artist_id}` - Calculer score pour un artiste
- `GET /scoring/stats` - Statistiques de scoring

### 🔄 Extraction
- `POST /extraction/start-phase1` - Lancer extraction Spotify
- `POST /extraction/start-phase2` - Lancer enrichissement YouTube
- `POST /extraction/resume-tubebuddy` - Calculer scores TubeBuddy
- `GET /extraction/status` - Statut des processus

### 📊 Collection
- `POST /collection/spotify-playlist` - Extraire depuis playlist Spotify
- `POST /collection/youtube-search` - Recherche YouTube
- `GET /collection/status` - Statut des collectes

## 🧮 Algorithme TubeBuddy

### Search Volume (60%)
```python
# Combinaison de 3 métriques :
search_volume = (
    google_trends_score * 0.4 +      # Popularité générale
    avg_youtube_views * 0.4 +        # Performance YouTube
    video_count_score * 0.2          # Densité de contenu
)
```

### Competition (40%)
```python
# Analyse des 20 premiers concurrents :
competition = moyenne([
    score_competitivite_chaine(abonnes, vues_totales)
    for chaine in top_20_resultats
])
```

### Score Final
```python
score_final = (
    search_volume * 0.6 +
    (100 - competition) * 0.4
) * 1.5  # Coefficient musique
```

## 🔍 Monitoring & Debug

### Logs détaillés
```bash
# Voir les logs en temps réel
docker logs artists-collector-api -f

# Filtrer les logs de scoring
docker logs artists-collector-api 2>&1 | grep "Search Volume\|Competition\|Google Trends"
```

### Base de données
```bash
# Connexion PostgreSQL
docker exec -it artists-db psql -U artists_user -d artists_collector

# Statistiques rapides
SELECT COUNT(*) as total,
       COUNT(CASE WHEN needs_scoring THEN 1 END) as pending
FROM artists WHERE is_active = true;
```

## 🧪 Tests & Développement

### Scripts utiles
```bash
# Tests TubeBuddy sur artistes spécifiques
python scripts/test_tubebuddy_scoring.py

# Backup base de données
python scripts/backup_database.py

# Rapport d'extraction batch
python scripts/batch_extraction_report.py
```

### Code propre
- ✅ **Code nettoyé** : Suppression des fichiers inutilisés
- ✅ **Service simplifié** : scoring_service.py refactorisé (244 lignes)
- ✅ **Architecture claire** : Une méthode par métrique
- ✅ **Logs détaillés** : Debug facilité

## 📝 Historique des Versions

### v2.0 - Service Propre (Actuel)
- 🧹 Nettoyage complet du code (suppression 27KB code mort)
- 🔄 Refactoring scoring_service.py (789→244 lignes)
- 📊 Algorithme TubeBuddy optimisé et documenté
- 🔍 Logs détaillés pour debugging

### v1.0 - Version Initiale
- 🎵 Collecte Spotify + YouTube
- 📈 Premier algorithme de scoring
- 🚀 API REST complète

---

**Développé pour l'analyse d'opportunités dans le marché des type beats hip-hop** 🎧