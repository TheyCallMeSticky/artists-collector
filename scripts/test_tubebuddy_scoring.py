#!/usr/bin/env python3
"""
Script de test pour l'algorithme TubeBuddy
Teste le calcul des scores sur 10 artistes du rapport précédent
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent.parent))

from app.services.scoring_service import ScoringService


class TubeBuddyTester:
    def __init__(self):
        self.scoring_service = ScoringService()

    def get_sample_artists(self) -> list[str]:
        """Récupérer 10 artistes du rapport d'extraction précédent"""

        # Liste des 10 premiers artistes uniques du rapport (en évitant les doublons)
        sample_artists = [
            "smokedope2016",
            "Yeat",
            "Nino Paid",
            "Lil Yachty",
            "TiaCorine",
            "Veeze",
            "21 Savage",
            "Central Cee",
            "Sahbabii",
            "Bktherula"
        ]

        print(f"🎯 Artistes sélectionnés pour le test TubeBuddy:")
        for i, artist in enumerate(sample_artists, 1):
            print(f"  {i}. {artist}")
        print()

        return sample_artists

    async def test_single_artist(self, artist_name: str) -> dict:
        """Tester le scoring pour un seul artiste"""
        print(f"📊 Calcul du score TubeBuddy pour: {artist_name}")

        try:
            # Calculer le score complet
            score_result = await self.scoring_service.calculate_artist_score(artist_name)

            if "error" in score_result:
                print(f"   ❌ Erreur: {score_result['error']}")
                return score_result

            # Afficher les résultats
            search_volume = score_result.get("search_volume_score", 0)
            competition = score_result.get("competition_score", 0)
            optimization = score_result.get("optimization_score", 0)
            overall = score_result.get("overall_score", 0)

            print(f"   🔍 Volume de recherche: {search_volume:.1f}/100")
            print(f"   ⚔️  Compétition: {competition:.1f}/100")
            print(f"   📈 Optimisation: {optimization:.1f}/100")
            print(f"   🏆 SCORE GLOBAL: {overall:.1f}/100")

            # Interprétation
            interpretation = self.scoring_service.get_score_interpretation(overall)
            print(f"   💡 Catégorie: {interpretation['category']}")
            print(f"   📝 Recommandation: {interpretation['recommendation']}")
            print()

            return score_result

        except Exception as e:
            error_msg = f"Erreur lors du calcul pour {artist_name}: {str(e)}"
            print(f"   ❌ {error_msg}")
            return {"artist_name": artist_name, "error": error_msg}

    async def run_full_test(self):
        """Lancer le test complet sur tous les artistes"""
        print("🚀 DÉMARRAGE DU TEST TUBEBUDDY")
        print("=" * 60)
        print()

        # Récupérer les artistes
        artists = self.get_sample_artists()

        # Tester chaque artiste
        all_results = []
        successful_tests = 0

        for i, artist in enumerate(artists, 1):
            print(f"[{i}/{len(artists)}]", end=" ")
            result = await self.test_single_artist(artist)
            all_results.append(result)

            if "error" not in result:
                successful_tests += 1

            # Pause entre les tests pour respecter les quotas API
            if i < len(artists):
                print("⏳ Pause 2s pour respecter les quotas API...")
                await asyncio.sleep(2)
                print()

        # Générer le rapport final
        self.generate_final_report(all_results, successful_tests, len(artists))

        # Sauvegarder les résultats
        self.save_results(all_results)

    def generate_final_report(self, results: list, successful: int, total: int):
        """Générer le rapport final des tests"""
        print("=" * 60)
        print("📊 RAPPORT FINAL - TEST TUBEBUDDY")
        print("=" * 60)

        print(f"✅ Tests réussis: {successful}/{total}")
        print(f"❌ Tests échoués: {total - successful}/{total}")
        print()

        # Filtrer les résultats réussis
        valid_results = [r for r in results if "error" not in r]

        if not valid_results:
            print("⚠️ Aucun résultat valide pour générer les statistiques")
            return

        # Top 5 des meilleurs scores
        print("🏆 TOP 5 OPPORTUNITÉS:")
        top_artists = sorted(valid_results, key=lambda x: x.get("overall_score", 0), reverse=True)[:5]

        for i, artist in enumerate(top_artists, 1):
            name = artist["artist_name"]
            score = artist.get("overall_score", 0)
            interpretation = self.scoring_service.get_score_interpretation(score)
            print(f"  {i}. {name}: {score:.1f}/100 ({interpretation['category']})")

        print()

        # Statistiques moyennes
        avg_search = sum(r.get("search_volume_score", 0) for r in valid_results) / len(valid_results)
        avg_competition = sum(r.get("competition_score", 0) for r in valid_results) / len(valid_results)
        avg_optimization = sum(r.get("optimization_score", 0) for r in valid_results) / len(valid_results)
        avg_overall = sum(r.get("overall_score", 0) for r in valid_results) / len(valid_results)

        print("📈 MOYENNES:")
        print(f"  🔍 Volume de recherche: {avg_search:.1f}/100")
        print(f"  ⚔️  Compétition: {avg_competition:.1f}/100")
        print(f"  📈 Optimisation: {avg_optimization:.1f}/100")
        print(f"  🏆 Score global: {avg_overall:.1f}/100")
        print()

        # Recommandations
        excellent_count = sum(1 for r in valid_results if r.get("overall_score", 0) >= 80)
        good_count = sum(1 for r in valid_results if 65 <= r.get("overall_score", 0) < 80)

        print("💡 ANALYSE:")
        print(f"  • {excellent_count} artiste(s) avec opportunité excellente (≥80)")
        print(f"  • {good_count} artiste(s) avec bonne opportunité (65-79)")
        print(f"  • Score moyen de {avg_overall:.1f} indique un potentiel {'élevé' if avg_overall >= 60 else 'modéré' if avg_overall >= 40 else 'faible'}")

    def save_results(self, results: list):
        """Sauvegarder les résultats du test"""
        output_data = {
            "timestamp": datetime.now().isoformat(),
            "test_type": "TubeBuddy Algorithm Test",
            "algorithm": "Search Volume (40%) + Competition (40%) + Optimization (20%)",
            "total_artists_tested": len(results),
            "successful_tests": len([r for r in results if "error" not in r]),
            "results": results
        }

        output_path = Path(__file__).parent.parent / "reports" / "tubebuddy_test_results.json"
        output_path.parent.mkdir(exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"💾 Résultats sauvegardés: {output_path}")


async def main():
    """Point d'entrée principal"""
    tester = TubeBuddyTester()

    try:
        await tester.run_full_test()
        print("\n🎉 Test TubeBuddy terminé avec succès!")

    except KeyboardInterrupt:
        print("\n⏹️ Test interrompu par l'utilisateur")
    except Exception as e:
        print(f"\n❌ Erreur fatale: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())