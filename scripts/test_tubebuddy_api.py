#!/usr/bin/env python3
"""
Script de test pour l'algorithme TubeBuddy via API
Teste l'endpoint /artists/opportunities de manière indépendante
"""

import json
import requests
import sys
from datetime import datetime
from pathlib import Path


class TubeBuddyApiTester:
    def __init__(self, api_base_url="http://localhost:8001"):
        self.api_base_url = api_base_url
        self.session = requests.Session()

    def test_api_health(self):
        """Vérifier que l'API est accessible"""
        try:
            response = self.session.get(f"{self.api_base_url}/health")
            if response.status_code == 200:
                print("✅ API accessible")
                return True
            else:
                print(f"❌ API non accessible - Status: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Impossible de contacter l'API: {e}")
            return False

    def get_sample_artists_from_db(self):
        """Récupérer des artistes de la base de données via l'API"""
        try:
            response = self.session.get(f"{self.api_base_url}/artists?limit=20")
            if response.status_code == 200:
                artists = response.json()
                if artists:
                    # Prendre les 10 premiers artistes
                    sample_artists = [artist["name"] for artist in artists[:10]]
                    print(f"📊 {len(sample_artists)} artistes récupérés de la DB:")
                    for i, artist in enumerate(sample_artists, 1):
                        print(f"  {i}. {artist}")
                    return sample_artists
                else:
                    print("⚠️ Aucun artiste trouvé dans la DB")
                    return self.get_fallback_artists()
            else:
                print(f"❌ Erreur récupération artistes: {response.status_code}")
                return self.get_fallback_artists()
        except Exception as e:
            print(f"❌ Erreur API artistes: {e}")
            return self.get_fallback_artists()

    def get_fallback_artists(self):
        """Artistes de fallback si la DB est vide"""
        fallback_artists = [
            "Yeat", "21 Savage", "Central Cee", "Lil Yachty", "TiaCorine",
            "Veeze", "Sahbabii", "Bktherula", "Nino Paid", "smokedope2016"
        ]
        print(f"🔄 Utilisation des artistes de fallback:")
        for i, artist in enumerate(fallback_artists, 1):
            print(f"  {i}. {artist}")
        return fallback_artists

    def test_tubebuddy_scoring(self, artist_names):
        """Tester le scoring TubeBuddy via l'API batch pour une liste d'artistes"""
        print("\n🚀 DÉMARRAGE DU TEST TUBEBUDDY VIA API BATCH")
        print("=" * 60)
        print(f"📋 Traitement de {len(artist_names)} artistes en batch...")

        try:
            # Appeler l'endpoint batch-score
            payload = {"artist_names": artist_names}
            response = self.session.post(
                f"{self.api_base_url}/artists/batch-score",
                json=payload,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                data = response.json()

                print(f"✅ Batch traité avec succès:")
                print(f"   📊 Total artistes: {data['total_artists']}")
                print(f"   ✅ Calculs réussis: {data['successful_calculations']}")
                print(f"   ❌ Calculs échoués: {data['failed_calculations']}")

                batch_stats = data.get('batch_statistics', {})
                print(f"   📈 Moyennes batch:")
                print(f"      🔍 Volume recherche: {batch_stats.get('avg_search_volume_score', 0)}/100")
                print(f"      ⚔️  Compétition: {batch_stats.get('avg_competition_score', 0)}/100")
                print(f"      📈 Optimisation: {batch_stats.get('avg_optimization_score', 0)}/100")
                print(f"      🏆 Score global: {batch_stats.get('avg_overall_score', 0)}/100")

                print(f"\n📋 DÉTAIL PAR ARTISTE:")

                results = []
                artist_scores = data.get('artist_scores', [])

                for i, score_data in enumerate(artist_scores, 1):
                    artist_name = score_data.get('artist_name', f'Artiste_{i}')
                    print(f"\n[{i}/{len(artist_scores)}] 📊 {artist_name}:")

                    if "error" in score_data:
                        print(f"   ❌ Erreur: {score_data['error']}")
                        results.append({
                            "artist_name": artist_name,
                            "error": score_data['error'],
                            "status": "error"
                        })
                    else:
                        search_volume = score_data.get("search_volume_score", 0)
                        competition = score_data.get("competition_score", 0)
                        optimization = score_data.get("optimization_score", 0)
                        overall = score_data.get("overall_score", 0)

                        print(f"   🔍 Volume de recherche: {search_volume}/100")
                        print(f"   ⚔️  Compétition: {competition}/100")
                        print(f"   📈 Optimisation: {optimization}/100")
                        print(f"   🏆 SCORE GLOBAL: {overall}/100")

                        interpretation = score_data.get("score_interpretation", {})
                        if interpretation:
                            print(f"   💡 Catégorie: {interpretation.get('category', 'N/A')}")
                            print(f"   📝 Recommandation: {interpretation.get('recommendation', 'N/A')}")

                        results.append({
                            "artist_name": artist_name,
                            "search_volume_score": search_volume,
                            "competition_score": competition,
                            "optimization_score": optimization,
                            "overall_score": overall,
                            "interpretation": interpretation,
                            "status": "success"
                        })

                return results

            else:
                print(f"❌ Erreur API batch: {response.status_code}")
                print(f"📝 Détail: {response.text}")

                # En cas d'erreur, retourner des résultats d'erreur pour tous les artistes
                return [{
                    "artist_name": name,
                    "error": f"API Batch Error {response.status_code}: {response.text}",
                    "status": "api_error"
                } for name in artist_names]

        except Exception as e:
            print(f"❌ Erreur lors de l'appel API batch: {str(e)}")

            # En cas d'exception, retourner des résultats d'erreur pour tous les artistes
            return [{
                "artist_name": name,
                "error": str(e),
                "status": "exception"
            } for name in artist_names]

    def generate_report(self, results):
        """Générer le rapport final"""
        print("\n" + "=" * 60)
        print("📊 RAPPORT FINAL - TEST TUBEBUDDY API")
        print("=" * 60)

        successful_results = [r for r in results if r.get("status") == "success"]
        failed_results = [r for r in results if r.get("status") != "success"]

        print(f"✅ Tests réussis: {len(successful_results)}/{len(results)}")
        print(f"❌ Tests échoués: {len(failed_results)}/{len(results)}")

        if successful_results:
            print(f"\n🏆 TOP OPPORTUNITÉS:")
            # Trier par score décroissant
            top_artists = sorted(successful_results, key=lambda x: x.get("overall_score", 0), reverse=True)

            for i, artist in enumerate(top_artists, 1):
                name = artist["artist_name"]
                score = artist.get("overall_score", 0)
                category = artist.get("interpretation", {}).get("category", "N/A")
                print(f"  {i}. {name}: {score}/100 ({category})")

            # Statistiques moyennes
            if len(successful_results) > 0:
                avg_search = sum(r.get("search_volume_score", 0) for r in successful_results) / len(successful_results)
                avg_competition = sum(r.get("competition_score", 0) for r in successful_results) / len(successful_results)
                avg_optimization = sum(r.get("optimization_score", 0) for r in successful_results) / len(successful_results)
                avg_overall = sum(r.get("overall_score", 0) for r in successful_results) / len(successful_results)

                print(f"\n📈 MOYENNES:")
                print(f"  🔍 Volume de recherche: {avg_search:.0f}/100")
                print(f"  ⚔️  Compétition: {avg_competition:.0f}/100")
                print(f"  📈 Optimisation: {avg_optimization:.0f}/100")
                print(f"  🏆 Score global: {avg_overall:.0f}/100")

        if failed_results:
            print(f"\n⚠️ ERREURS DÉTECTÉES:")
            for result in failed_results:
                name = result["artist_name"]
                error = result.get("error", "Erreur inconnue")
                print(f"  ❌ {name}: {error}")

    def save_results(self, results):
        """Sauvegarder les résultats"""
        output_data = {
            "timestamp": datetime.now().isoformat(),
            "test_type": "TubeBuddy API Test",
            "api_endpoint": "/artists/opportunities",
            "total_tests": len(results),
            "successful_tests": len([r for r in results if r.get("status") == "success"]),
            "results": results
        }

        output_path = Path(__file__).parent.parent / "reports" / "tubebuddy_api_test_results.json"
        output_path.parent.mkdir(exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Résultats sauvegardés: {output_path}")

    def run_full_test(self):
        """Lancer le test complet"""
        print("🎯 Test de l'algorithme TubeBuddy via API")
        print("🌐 API URL:", self.api_base_url)
        print()

        # Vérifier la santé de l'API
        if not self.test_api_health():
            print("❌ Impossible de continuer sans accès à l'API")
            return False

        # Récupérer les artistes à tester
        artist_names = self.get_sample_artists_from_db()
        if not artist_names:
            print("❌ Aucun artiste à tester")
            return False

        # Lancer les tests TubeBuddy
        results = self.test_tubebuddy_scoring(artist_names)

        # Générer le rapport
        self.generate_report(results)

        # Sauvegarder les résultats
        self.save_results(results)

        return True


def main():
    """Point d'entrée principal"""
    import argparse

    parser = argparse.ArgumentParser(description="Test TubeBuddy via API")
    parser.add_argument(
        "--api-url",
        default="http://localhost:8001",
        help="URL de base de l'API (défaut: http://localhost:8001)"
    )

    args = parser.parse_args()

    tester = TubeBuddyApiTester(args.api_url)

    try:
        success = tester.run_full_test()
        if success:
            print("\n🎉 Test TubeBuddy API terminé avec succès!")
        else:
            print("\n❌ Test TubeBuddy API échoué")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⏹️ Test interrompu par l'utilisateur")
    except Exception as e:
        print(f"\n❌ Erreur fatale: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()