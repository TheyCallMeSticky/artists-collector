'''
# Service de Collecte d'Artistes (`artists-collector`)

Ce service est le cœur du projet. Il s'agit d'une application backend en Python (FastAPI) responsable de la collecte de données, du scoring et de la gestion des artistes.

## Fonctionnalités

- **API RESTful** : Endpoints pour gérer les artistes, lancer des collectes de données et consulter les scores.
- **Collecte de Données** : Intégration avec les API de Spotify et YouTube pour récupérer des informations sur les artistes.
- **Scoring Personnalisé** : Un algorithme de scoring avancé pour évaluer le potentiel d'un artiste pour les "type beats".
- **Gestion de Base de Données** : Utilise SQLAlchemy pour interagir avec une base de données PostgreSQL.
- **Tâches en Arrière-Plan** : Support pour les collectes de longue durée sans bloquer l'API.
- **Gestion des Clés API** : Rotation automatique des 12 clés API YouTube pour optimiser l'utilisation des quotas.

## Structure du Projet

```
/app
├── api/          # Endpoints FastAPI (routes)
├── core/         # Configuration de l'application
├── db/           # Connexion et initialisation de la base de données
├── models/       # Modèles de données SQLAlchemy
├── schemas/      # Schémas de validation Pydantic
├── services/     # Logique métier (Spotify, YouTube, scoring, etc.)
└── main.py       # Point d'entrée de l'application FastAPI
/migrations/      # Scripts de migration et d'initialisation de la DB
/scripts/         # Scripts utiles (tests, backup, etc.)
/tests/           # Tests unitaires et d'intégration
.env.example      # Fichier d'exemple pour les variables d'environnement
Dockerfile        # Fichier pour la conteneurisation avec Docker
docker-compose.yml # Fichier pour l'orchestration du développement local
requirements.txt  # Dépendances Python
```

## Mise en Route

Ce service est conçu pour être exécuté avec Docker et Docker Compose pour une mise en place simplifiée.

1.  **Prérequis** :
    *   Docker
    *   Docker Compose

2.  **Configuration** :
    *   Copiez `.env.example` vers un nouveau fichier nommé `.env`.
    *   Remplissez les variables d'environnement dans `.env`, notamment :
        *   `SPOTIFY_CLIENT_ID` et `SPOTIFY_CLIENT_SECRET`
        *   Les 12 clés `YOUTUBE_API_KEY_`

3.  **Démarrage** :
    *   Exécutez le script de démarrage :
        ```bash
        ./scripts/start_dev.sh
        ```
    *   Ce script va automatiquement construire les images Docker, démarrer les conteneurs (PostgreSQL, Redis, API), et initialiser la base de données.

4.  **Accès** :
    *   **API** : [http://localhost:8000](http://localhost:8000)
    *   **Documentation (Swagger UI)** : [http://localhost:8000/docs](http://localhost:8000/docs)

## Endpoints Principaux

- `POST /collection/artist` : Collecte les données pour un seul artiste.
- `POST /scoring/batch-collect` : Collecte les données pour une liste d'artistes.
- `GET /scoring/opportunities` : Récupère la liste des meilleures opportunités (artistes avec les meilleurs scores).
- `GET /artists` : Liste tous les artistes présents dans la base de données.

Consultez la documentation Swagger pour une liste complète des endpoints et leurs paramètres.

## Tests

Pour exécuter la suite de tests :

```bash
./scripts/run_tests.py
```

Ce script exécute les tests unitaires, les vérifications de style de code (linting) et les analyses de sécurité.
'''
