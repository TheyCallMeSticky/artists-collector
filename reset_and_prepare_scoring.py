#!/usr/bin/env python3
"""
Script pour réinitialiser et préparer le scoring des artistes de test
Usage: docker exec artists-collector-api python3 /app/reset_and_prepare_scoring.py
"""

import sys

import psycopg2

# Configuration de la connexion à la base de données
DB_CONFIG = {
    "host": "artists-db",
    "port": 5432,
    "database": "artists_collector",
    "user": "artists_user",
    "password": "artists_password",
}

# Liste des artistes de test (sans Alejandrito Argeñal)
TEST_ARTISTS = [
    "Artisan P",
    "BhramaBull",
    "Cousin Feo",
    "DJ Proof",
    "Domingo",
    "Dutch of Gotham",
    "IceRocks",
    "Jafet Muzic",
    "Lord Juco",
    "MRKBH",
    "Mad1ne",
    "Malcolmsef",
    "Passport Rav",
    "Rico James",
    "Skip The Kid",
    "Soul Professa",
    "Tony Stanza",
    "XP The Marxman",
    "Future",
    "G Herbo",
    "Lil Tecca",
]


def reset_and_prepare():
    """Réinitialiser les scores et préparer les artistes pour le recalcul"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        print("🔄 Réinitialisation en cours...")
        print()

        # 1. Supprimer tous les scores
        cursor.execute("DELETE FROM scores;")
        deleted_scores = cursor.rowcount
        print(f"✅ {deleted_scores} scores supprimés")

        # 2. Mettre needs_scoring à false pour tous
        cursor.execute("UPDATE artists SET needs_scoring = false;")
        print(f"✅ Tous les artistes marqués needs_scoring = false")

        # 3. Activer needs_scoring pour les artistes de test
        placeholders = ",".join(["%s"] * len(TEST_ARTISTS))
        query = (
            f"UPDATE artists SET needs_scoring = true WHERE name IN ({placeholders});"
        )
        cursor.execute(query, TEST_ARTISTS)
        updated_artists = cursor.rowcount
        print(f"✅ {updated_artists} artistes marqués needs_scoring = true")

        # Commit
        conn.commit()

        print()
        print("=" * 80)
        print("📊 ÉTAT FINAL DE LA BASE DE DONNÉES")
        print("=" * 80)

        # Vérification
        cursor.execute(
            """
            SELECT
                'Total artistes' as metric, COUNT(*)::text as count FROM artists
            UNION ALL
            SELECT
                'Scores en BDD', COUNT(*)::text FROM scores
            UNION ALL
            SELECT
                'Artistes à recalculer (needs_scoring=true)', COUNT(*)::text FROM artists WHERE needs_scoring = true
            UNION ALL
            SELECT
                'Artistes sans recalcul (needs_scoring=false)', COUNT(*)::text FROM artists WHERE needs_scoring = false;
        """
        )

        results = cursor.fetchall()
        for metric, count in results:
            print(f"   {metric:<45} {count}")

        print()
        print("=" * 80)
        print("📝 ARTISTES PRÊTS POUR LE RECALCUL")
        print("=" * 80)

        cursor.execute(
            "SELECT name FROM artists WHERE needs_scoring = true ORDER BY name;"
        )
        artists = cursor.fetchall()
        for i, (name,) in enumerate(artists, 1):
            print(f"   {i:2}. {name}")

        cursor.close()
        conn.close()

        print()
        print("=" * 80)
        print("✅ PRÉPARATION TERMINÉE !")
        print("=" * 80)
        print()
        print("🚀 Vous pouvez maintenant lancer le scoring depuis l'UI")
        print()

        return True

    except Exception as e:
        print(f"❌ Erreur: {e}")
        sys.exit(1)


if __name__ == "__main__":
    reset_and_prepare()
