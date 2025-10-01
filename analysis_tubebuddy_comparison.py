#!/usr/bin/env python3
"""
Analyse comparative: Notre algorithme vs TubeBuddy
Récupère les scores depuis la base de données
"""

import os
import sys

import psycopg2

# Configuration de la connexion à la base de données
DB_CONFIG = {
    "host": "artists-db",  # Nom du container Docker
    "port": 5432,
    "database": "artists_collector",
    "user": "artists_user",
    "password": "artists_password",
}

# Données TubeBuddy (ne changent pas)
tubebuddy_data = {
    "Domingo": (69, "Fair", "Very Good"),  # Score, Search, Competition
    "Tony Stanza": (47, "Poor", "Excellent"),
    "IceRocks": (46, "Poor", "Excellent"),
    "Rico James": (35, "Poor", "Excellent"),
    "Skip The Kid": (100, "Excellent", "Good"),
    "Mad1ne": (46, "Poor", "Excellent"),
    "Soul Professa": (37, "Poor", "Excellent"),
    "DJ Proof": (80, "Fair", "Excellent"),
    "Artisan P": (45, "Poor", "Excellent"),
    "Lord Juco": (43, "Poor", "Excellent"),
    "Dutch of Gotham": (46, "Poor", "Excellent"),
    "Jafet Muzic": (34, "Poor", "Excellent"),
    "Passport Rav": (47, "Poor", "Excellent"),
    "Cousin Feo": (47, "Poor", "Excellent"),
    "MRKBH": (46, "Poor", "Excellent"),
    "Alejandrito Argeñal": (28, "Poor", "Excellent"),
    "BhramaBull": (45, "Poor", "Excellent"),
    "XP The Marxman": (18, "Poor", "Excellent"),
    "Malcolmsef": (47, "Poor", "Excellent"),
    "G Herbo": (14, "Fair", "Poor"),
    "Future": (13, "Good", "Poor"),
    "Lil Tecca": (39, "Excellent", "Poor"),
}

# Mapping des qualificatifs TubeBuddy en scores numériques
tb_search_mapping = {
    "Poor": 10,  # < 20
    "Fair": 30,  # 20-40
    "Good": 50,  # 40-60
    "Very Good": 70,  # 60-80
    "Excellent": 90,  # > 80
}

tb_competition_mapping = {
    "Excellent": 90,  # Très bonne (faible compétition)
    "Very Good": 70,
    "Good": 50,
    "Fair": 30,
    "Poor": 10,  # Mauvaise (forte compétition)
}


def fetch_our_scores():
    """Récupère nos scores depuis la base de données"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Récupérer les artistes avec leurs scores les plus récents
        query = """
            SELECT
                a.name,
                s.overall_score,
                s.search_volume_score,
                s.competition_score
            FROM artists a
            INNER JOIN scores s ON a.id = s.artist_id
            WHERE s.created_at = (
                SELECT MAX(created_at)
                FROM scores
                WHERE artist_id = a.id
            )
            ORDER BY s.overall_score DESC;
        """

        cursor.execute(query)
        results = cursor.fetchall()

        cursor.close()
        conn.close()

        return {
            name: (round(overall), round(search), round(comp))
            for name, overall, search, comp in results
        }

    except Exception as e:
        print(f"❌ Erreur connexion base de données: {e}")
        print("   Assurez-vous que le container Docker est démarré")
        sys.exit(1)


# Récupérer nos scores depuis la BDD
print("📊 Récupération des scores depuis la base de données...")
our_scores_db = fetch_our_scores()
print(f"✅ {len(our_scores_db)} artistes trouvés dans la BDD\n")

# Construire le tableau de comparaison
data_with_deduction = []
for artist_name, (tb_score, tb_search_label, tb_comp_label) in tubebuddy_data.items():
    if artist_name in our_scores_db:
        our_overall, our_search, our_comp = our_scores_db[artist_name]
        tb_search = tb_search_mapping[tb_search_label]
        tb_comp = tb_competition_mapping[tb_comp_label]

        data_with_deduction.append(
            (
                artist_name,
                our_overall,
                our_search,
                our_comp,
                tb_score,
                tb_search,
                tb_comp,
            )
        )
    else:
        print(f"⚠️  Artiste '{artist_name}' non trouvé dans la BDD")

print("=" * 120)
print("COMPARAISON NOTRE ALGORITHME vs TUBEBUDDY")
print("=" * 120)
print()

# Tableau comparatif
print(
    f"{'Artiste':<25} | {'Notre':<6} {'TB':<6} {'Δ':<6} | {'N.Search':<9} {'TB.Search':<9} {'Δ':<6} | {'N.Comp':<7} {'TB.Comp':<7} {'Δ':<6}"
)
print("-" * 120)

total_score_error = 0
total_search_error = 0
total_comp_error = 0
count = len(data_with_deduction)

for (
    artist,
    our_score,
    our_search,
    our_comp,
    tb_score,
    tb_search,
    tb_comp,
) in data_with_deduction:
    score_diff = abs(our_score - tb_score)
    search_diff = abs(our_search - tb_search)
    comp_diff = abs(our_comp - tb_comp)

    total_score_error += score_diff
    total_search_error += search_diff
    total_comp_error += comp_diff

    print(
        f"{artist:<25} | {our_score:<6} {tb_score:<6} {score_diff:<6} | {our_search:<9} {tb_search:<9} {search_diff:<6} | {our_comp:<7} {tb_comp:<7} {comp_diff:<6}"
    )

print("-" * 120)
print()

# Calcul des moyennes d'erreur
avg_score_error = total_score_error / count
avg_search_error = total_search_error / count
avg_comp_error = total_comp_error / count

# Calcul de la précision (100 - erreur moyenne en %)
score_accuracy = 100 - avg_score_error
search_accuracy = 100 - avg_search_error
comp_accuracy = 100 - avg_comp_error

print("=" * 120)
print("STATISTIQUES DE PRÉCISION")
print("=" * 120)
print()
print(f"📊 SCORE GLOBAL:")
print(f"   Erreur moyenne absolue: {avg_score_error:.2f} points")
print(f"   Précision: {score_accuracy:.1f}%")
print()
print(f"🔍 VOLUME DE RECHERCHE:")
print(f"   Erreur moyenne absolue: {avg_search_error:.2f} points")
print(f"   Précision: {search_accuracy:.1f}%")
print()
print(f"⚔️  COMPÉTITION:")
print(f"   Erreur moyenne absolue: {avg_comp_error:.2f} points")
print(f"   Précision: {comp_accuracy:.1f}%")
print()

# Analyse des cas extrêmes
print("=" * 120)
print("CAS AVEC GRANDES DIVERGENCES (>30 points de différence)")
print("=" * 120)
print()

for (
    artist,
    our_score,
    our_search,
    our_comp,
    tb_score,
    tb_search,
    tb_comp,
) in data_with_deduction:
    score_diff = abs(our_score - tb_score)
    if score_diff > 30:
        print(f"⚠️  {artist}:")
        print(
            f"   Notre score: {our_score} | TubeBuddy: {tb_score} | Différence: {score_diff}"
        )
        print(
            f"   Notre Search: {our_search} | TB Search: {tb_search} | Différence: {abs(our_search - tb_search)}"
        )
        print(
            f"   Notre Comp: {our_comp} | TB Comp: {tb_comp} | Différence: {abs(our_comp - tb_comp)}"
        )
        print()

print("=" * 120)
print("OBSERVATIONS DYNAMIQUES")
print("=" * 120)
print()

# Analyse des patterns
tb_search_labels = [
    tb_search_label
    for _, (_, tb_search_label, _) in tubebuddy_data.items()
    if _ in [d[0] for d in data_with_deduction]
]
tb_comp_labels = [
    tb_comp_label
    for _, (_, _, tb_comp_label) in tubebuddy_data.items()
    if _ in [d[0] for d in data_with_deduction]
]

from collections import Counter

search_counter = Counter(tb_search_labels)
comp_counter = Counter(tb_comp_labels)

print("📊 DISTRIBUTION TUBEBUDDY:")
print(f"   Search Volume: {dict(search_counter)}")
print(f"   Competition: {dict(comp_counter)}")
print()

# Identifier les meilleurs et pires cas
sorted_by_accuracy = sorted(data_with_deduction, key=lambda x: abs(x[1] - x[4]))
best_3 = sorted_by_accuracy[:3]
worst_3 = sorted_by_accuracy[-3:]

print("✅ MEILLEURS CAS (plus précis):")
for artist, our_score, our_search, our_comp, tb_score, tb_search, tb_comp in best_3:
    score_diff = abs(our_score - tb_score)
    print(f"   • {artist}: Notre {our_score} vs TB {tb_score} (Δ={score_diff})")
print()

print("❌ PIRES CAS (plus d'écart):")
for artist, our_score, our_search, our_comp, tb_score, tb_search, tb_comp in worst_3:
    score_diff = abs(our_score - tb_score)
    search_diff = abs(our_search - tb_search)
    comp_diff = abs(our_comp - tb_comp)

    print(f"   • {artist}: Notre {our_score} vs TB {tb_score} (Δ={score_diff})")

    # Identifier le problème principal
    if search_diff > comp_diff:
        print(f"     → Problème principal: SEARCH VOLUME (Δ={search_diff})")
        print(f"       Notre: {our_search} | TB: {tb_search}")
    else:
        print(f"     → Problème principal: COMPÉTITION (Δ={comp_diff})")
        print(f"       Notre: {our_comp} | TB: {tb_comp}")
print()

# Statistiques de sur/sous-estimation
overestimated = sum(1 for _, our, _, _, tb, _, _ in data_with_deduction if our > tb)
underestimated = sum(1 for _, our, _, _, tb, _, _ in data_with_deduction if our < tb)

print("📈 TENDANCES:")
print(
    f"   • Scores surestimés: {overestimated}/{count} ({overestimated/count*100:.1f}%)"
)
print(
    f"   • Scores sous-estimés: {underestimated}/{count} ({underestimated/count*100:.1f}%)"
)
print()

# Recommandations basées sur les données
print("💡 RECOMMANDATIONS:")
if score_accuracy < 85:
    print("   ⚠️  Précision globale < 85% - Ajustements nécessaires")
if search_accuracy < 85:
    print("   ⚠️  Search Volume à améliorer (vérifier Google Trends et normalisation)")
if comp_accuracy < 85:
    print("   ⚠️  Compétition à améliorer (revoir seuils de vues/abonnés)")
if score_accuracy >= 90 and search_accuracy >= 90 and comp_accuracy >= 90:
    print("   ✅ Excellente précision ! Algorithme prêt pour production")
elif score_accuracy >= 85:
    print("   ✅ Bonne précision - Peut être testé sur plus d'artistes")
print()
print("=" * 120)
