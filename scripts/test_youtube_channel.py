#!/usr/bin/env python3
"""
Script de test pour diagnostiquer les problèmes d'API YouTube sur une chaîne spécifique
Teste différents paramètres et configurations pour comprendre pourquoi certaines chaînes retournent peu de résultats
"""

import json
from datetime import datetime
from pathlib import Path

import requests

# ============= CONFIGURATION =============
CHANNEL_ID = "UCa8b7nZo-iPKoJxspOplnWg"  # Rap Nation (à modifier)
CHANNEL_NAME = "Rap Nation"  # Nom pour les logs (à modifier)
API_KEY = (
    "AIzaSyBfVwwp5sszvbk7-1YL1kfIThgAJk6qhKw"  # Votre clé API YouTube (à modifier)
)

# URL de base YouTube API v3
BASE_URL = "https://www.googleapis.com/youtube/v3"


def test_api_connection():
    """Test basique de connexion à l'API"""
    print("🔍 Test de connexion API...")

    try:
        response = requests.get(
            f"{BASE_URL}/channels",
            params={"part": "snippet,statistics", "id": CHANNEL_ID, "key": API_KEY},
            timeout=30,
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("items"):
                channel = data["items"][0]
                stats = channel.get("statistics", {})
                print(f"✅ Chaîne trouvée: {channel['snippet']['title']}")
                print(f"📊 Abonnés: {stats.get('subscriberCount', 'N/A')}")
                print(f"🎥 Vidéos: {stats.get('videoCount', 'N/A')}")
                print(f"👁️ Vues totales: {stats.get('viewCount', 'N/A')}")
                return True
            else:
                print("❌ Chaîne introuvable avec cet ID")
                return False
        else:
            print(f"❌ Erreur API: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        print(f"❌ Erreur de connexion: {e}")
        return False


def test_search_variations():
    """Teste différentes variations de recherche"""
    print(f"\n🧪 Test de variations de recherche pour {CHANNEL_NAME}...")

    variations = [
        {
            "name": "Standard (date, 50 résultats)",
            "params": {
                "part": "snippet",
                "channelId": CHANNEL_ID,
                "type": "video",
                "order": "date",
                "maxResults": 50,
            },
        },
        {
            "name": "Par pertinence (50 résultats)",
            "params": {
                "part": "snippet",
                "channelId": CHANNEL_ID,
                "type": "video",
                "order": "relevance",
                "maxResults": 50,
            },
        },
        {
            "name": "Par popularité (50 résultats)",
            "params": {
                "part": "snippet",
                "channelId": CHANNEL_ID,
                "type": "video",
                "order": "viewCount",
                "maxResults": 50,
            },
        },
        {
            "name": "Moins de résultats (10)",
            "params": {
                "part": "snippet",
                "channelId": CHANNEL_ID,
                "type": "video",
                "order": "date",
                "maxResults": 10,
            },
        },
        {
            "name": "Avec query générique",
            "params": {
                "part": "snippet",
                "channelId": CHANNEL_ID,
                "type": "video",
                "q": "music",
                "order": "date",
                "maxResults": 50,
            },
        },
        {
            "name": "Sans filtre type",
            "params": {
                "part": "snippet",
                "channelId": CHANNEL_ID,
                "order": "date",
                "maxResults": 50,
            },
        },
    ]

    results = {}

    for variation in variations:
        print(f"\n  📋 Test: {variation['name']}")

        try:
            params = variation["params"].copy()
            params["key"] = API_KEY

            response = requests.get(f"{BASE_URL}/search", params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()
                total = data.get("pageInfo", {}).get("totalResults", 0)
                returned = len(data.get("items", []))

                print(f"    ✅ Total disponible: {total}")
                print(f"    📦 Retournés: {returned}")

                if returned > 0:
                    # Montrer quelques titres
                    titles = [item["snippet"]["title"] for item in data["items"][:3]]
                    print(f"    🎬 Exemples: {', '.join(titles[:2])}...")

                results[variation["name"]] = {
                    "success": True,
                    "total_results": total,
                    "returned_count": returned,
                    "sample_titles": [
                        item["snippet"]["title"] for item in data["items"][:5]
                    ],
                }

            elif response.status_code == 403:
                print(f"    🚫 Quota épuisé ou clé invalide")
                results[variation["name"]] = {"success": False, "error": "Quota/Auth"}
            else:
                print(f"    ❌ Erreur: {response.status_code}")
                results[variation["name"]] = {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                }

        except Exception as e:
            print(f"    💥 Exception: {e}")
            results[variation["name"]] = {"success": False, "error": str(e)}

    return results


def test_uploads_playlist():
    """Teste la playlist 'uploads' de la chaîne"""
    print(f"\n📺 Test via playlist uploads...")

    try:
        # D'abord récupérer l'ID de la playlist uploads
        response = requests.get(
            f"{BASE_URL}/channels",
            params={"part": "contentDetails", "id": CHANNEL_ID, "key": API_KEY},
            timeout=30,
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("items"):
                uploads_playlist_id = data["items"][0]["contentDetails"][
                    "relatedPlaylists"
                ]["uploads"]
                print(f"  📋 Playlist uploads ID: {uploads_playlist_id}")

                # Récupérer les vidéos de la playlist
                playlist_response = requests.get(
                    f"{BASE_URL}/playlistItems",
                    params={
                        "part": "snippet",
                        "playlistId": uploads_playlist_id,
                        "maxResults": 50,
                        "key": API_KEY,
                    },
                    timeout=30,
                )

                if playlist_response.status_code == 200:
                    playlist_data = playlist_response.json()
                    total = playlist_data.get("pageInfo", {}).get("totalResults", 0)
                    returned = len(playlist_data.get("items", []))

                    print(f"  ✅ Vidéos via playlist: {returned}/{total}")

                    if returned > 0:
                        titles = [
                            item["snippet"]["title"]
                            for item in playlist_data["items"][:3]
                        ]
                        print(f"  🎬 Exemples: {', '.join(titles)}")

                    return {
                        "success": True,
                        "total_results": total,
                        "returned_count": returned,
                        "method": "uploads_playlist",
                    }
                else:
                    print(f"  ❌ Erreur playlist: {playlist_response.status_code}")
            else:
                print("  ❌ Impossible de récupérer les détails de la chaîne")
        else:
            print(f"  ❌ Erreur channel: {response.status_code}")

    except Exception as e:
        print(f"  💥 Exception: {e}")

    return {"success": False, "error": "Playlist method failed"}


def test_quota_status():
    """Test simple pour vérifier le statut des quotas"""
    print(f"\n⚡ Test de statut des quotas...")

    try:
        # Requête très simple qui consomme peu de quota
        response = requests.get(
            f"{BASE_URL}/channels",
            params={"part": "id", "id": CHANNEL_ID, "key": API_KEY},
            timeout=10,
        )

        if response.status_code == 200:
            print("  ✅ Quotas OK")
            return True
        elif response.status_code == 403:
            error_data = (
                response.json()
                if response.headers.get("content-type", "").startswith(
                    "application/json"
                )
                else {}
            )
            error_reason = (
                error_data.get("error", {})
                .get("errors", [{}])[0]
                .get("reason", "unknown")
            )
            print(f"  🚫 Quota/Auth error: {error_reason}")
            return False
        else:
            print(f"  ⚠️ Status inhabituel: {response.status_code}")
            return False

    except Exception as e:
        print(f"  💥 Exception: {e}")
        return False


def save_diagnostic_report(results):
    """Sauvegarde un rapport de diagnostic"""
    report = {
        "timestamp": datetime.now().isoformat(),
        "channel_id": CHANNEL_ID,
        "channel_name": CHANNEL_NAME,
        "api_key_used": (
            API_KEY[:10] + "..."
            if API_KEY != "YOUR_YOUTUBE_API_KEY_HERE"
            else "NOT_SET"
        ),
        "test_results": results,
    }

    # Créer le dossier reports s'il n'existe pas
    reports_dir = Path(__file__).parent.parent / "reports"
    reports_dir.mkdir(exist_ok=True)

    # Nom de fichier avec timestamp
    filename = f"youtube_diagnostic_{CHANNEL_NAME.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = reports_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Rapport sauvegardé: {filepath}")


def main():
    """Fonction principale"""
    print("=" * 60)
    print("🚀 DIAGNOSTIC YOUTUBE API")
    print("=" * 60)
    print(f"🎯 Chaîne cible: {CHANNEL_NAME}")
    print(f"🔑 Channel ID: {CHANNEL_ID}")
    print(
        f"🗝️ API Key: {'✅ Configurée' if API_KEY != 'YOUR_YOUTUBE_API_KEY_HERE' else '❌ À configurer'}"
    )

    if API_KEY == "YOUR_YOUTUBE_API_KEY_HERE":
        print(
            "\n❌ ERREUR: Vous devez configurer votre clé API YouTube dans le script !"
        )
        print("   Modifiez la variable API_KEY au début du fichier.")
        return

    all_results = {}

    # Test 1: Connexion de base
    if test_api_connection():
        all_results["api_connection"] = {"success": True}
    else:
        all_results["api_connection"] = {"success": False}
        print("\n⚠️ Connexion API échouée, arrêt des tests")
        return

    # Test 2: Statut des quotas
    quota_ok = test_quota_status()
    all_results["quota_status"] = {"success": quota_ok}

    if not quota_ok:
        print("\n⚠️ Problème de quota détecté, les tests suivants peuvent échouer")

    # Test 3: Variations de recherche
    search_results = test_search_variations()
    all_results["search_variations"] = search_results

    # Test 4: Méthode playlist uploads
    playlist_result = test_uploads_playlist()
    all_results["uploads_playlist"] = playlist_result

    # Analyse finale
    print("\n" + "=" * 60)
    print("📊 ANALYSE FINALE")
    print("=" * 60)

    successful_methods = []
    for method, result in search_results.items():
        if result.get("success") and result.get("returned_count", 0) > 1:
            successful_methods.append((method, result["returned_count"]))

    if successful_methods:
        print("✅ Méthodes qui fonctionnent:")
        for method, count in sorted(
            successful_methods, key=lambda x: x[1], reverse=True
        ):
            print(f"   • {method}: {count} vidéos")
    else:
        print("❌ Aucune méthode ne retourne beaucoup de résultats")

    if playlist_result.get("success"):
        print(f"✅ Méthode playlist: {playlist_result.get('returned_count', 0)} vidéos")

    # Recommandations
    print("\n💡 RECOMMANDATIONS:")
    if not quota_ok:
        print("   1. Vérifier la clé API et les quotas YouTube")

    if any(
        r.get("total_results", 0) > r.get("returned_count", 0)
        for r in search_results.values()
    ):
        print("   2. Implémenter la pagination pour récupérer plus de résultats")

    best_method = max(
        search_results.items(),
        key=lambda x: x[1].get("returned_count", 0) if x[1].get("success") else 0,
    )
    if best_method[1].get("success"):
        print(
            f"   3. Utiliser la méthode '{best_method[0]}' qui donne le plus de résultats"
        )

    # Sauvegarder le rapport
    save_diagnostic_report(all_results)


if __name__ == "__main__":
    main()
