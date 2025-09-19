#!/bin/bash
set -e

echo "🚀 Démarrage du service Artists Collector"

# Attendre que PostgreSQL soit prêt
echo "⏳ Attente de PostgreSQL..."
while ! pg_isready -h artists-postgres -p 5432 -U artists_user; do
    echo "PostgreSQL n'est pas encore prêt - attente..."
    sleep 2
done

echo "✅ PostgreSQL est prêt!"

# Initialiser la base de données si nécessaire
echo "🗄️ Initialisation de la base de données..."
python migrations/init_db.py || echo "⚠️ Initialisation de la DB échouée ou déjà effectuée"

echo "🎵 Démarrage de l'API Artists Collector..."

# Exécuter la commande passée en argument
exec "$@"
