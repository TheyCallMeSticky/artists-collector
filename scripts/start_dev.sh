#!/bin/bash

# Script de démarrage pour le développement local

set -e

echo "🚀 Démarrage de l'environnement de développement Artists Collector"

# Vérifier que Docker est installé
if ! command -v docker &> /dev/null; then
    echo "❌ Docker n'est pas installé. Veuillez l'installer d'abord."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose n'est pas installé. Veuillez l'installer d'abord."
    exit 1
fi

# Créer le fichier .env s'il n'existe pas
if [ ! -f .env ]; then
    echo "📝 Création du fichier .env à partir de .env.example"
    cp .env.example .env
    echo "⚠️  N'oubliez pas de configurer vos clés API dans le fichier .env"
fi

# Créer les répertoires nécessaires
mkdir -p backups logs

# Démarrer les services
echo "🐳 Démarrage des conteneurs Docker..."
docker-compose up -d postgres redis

# Attendre que PostgreSQL soit prêt
echo "⏳ Attente de PostgreSQL..."
until docker-compose exec postgres pg_isready -U artists_user -d artists_collector; do
    sleep 2
done

# Initialiser la base de données
echo "🗄️  Initialisation de la base de données..."
python migrations/init_db.py

# Démarrer l'API
echo "🚀 Démarrage de l'API..."
docker-compose up -d api

# Afficher les logs
echo "📋 Services démarrés avec succès!"
echo ""
echo "🌐 API disponible sur: http://localhost:8000"
echo "📊 Documentation API: http://localhost:8000/docs"
echo "🗄️  PostgreSQL: localhost:5432"
echo "🔴 Redis: localhost:6379"
echo ""
echo "📝 Pour voir les logs: docker-compose logs -f"
echo "🛑 Pour arrêter: docker-compose down"
echo ""

# Optionnel: afficher les logs en temps réel
read -p "Voulez-vous voir les logs en temps réel? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker-compose logs -f
fi
