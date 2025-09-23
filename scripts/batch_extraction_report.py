#!/usr/bin/env python3
"""
Script de test batch pour toutes les sources avec rapport détaillé
Évite la duplication de code et optimise l'utilisation des quotas API
"""

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import requests


class BatchExtractionReporter:
    def __init__(self, base_url="http://localhost:8001"):
        self.base_url = base_url
        self.results = {}
        self.total_artists = set()
        self.duplicate_artists = defaultdict(list)

    def load_sources_config(self):
        """Charger la configuration des sources"""
        config_path = Path(__file__).parent.parent / "config" / "sources.json"
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_single_source(self, source_type, source_id, source_name):
        """Tester une source individuelle"""
        try:
            response = requests.post(
                f"{self.base_url}/extraction/test-source",
                json={
                    "source_type": source_type,
                    "source_id": source_id,
                    "source_name": source_name,
                },
                timeout=60,
            )

            if response.status_code == 200:
                data = response.json()

                # Vérifier si c'est une erreur de quota dans la réponse
                if data.get("error") == "QUOTA_EXCEEDED":
                    return {
                        "status": "quota_exceeded",
                        "error": data.get("error_message", "Quota YouTube épuisé"),
                        "artists_count": 0,
                    }

                artists = data.get("artists", [])

                # Analyser les doublons
                for artist in artists:
                    artist_name = artist["name"]
                    if artist_name in self.total_artists:
                        self.duplicate_artists[artist_name].append(source_name)
                    else:
                        self.total_artists.add(artist_name)

                return {
                    "status": "success",
                    "artists_count": data.get("artists_found", 0),
                    "artists": [a["name"] for a in artists],
                    "sample_artists": [a["name"] for a in artists[:5]],  # 5 premiers
                    "raw_titles": data.get("raw_titles", [])[
                        :3
                    ],  # 3 premiers titres bruts
                }
            else:
                return {
                    "status": "error",
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "artists_count": 0,
                }

        except Exception as e:
            error_msg = str(e)
            if "QUOTA_EXCEEDED_YOUTUBE" in error_msg:
                return {
                    "status": "quota_exceeded",
                    "error": "Quota YouTube épuisé",
                    "artists_count": 0,
                }
            else:
                return {"status": "error", "error": error_msg, "artists_count": 0}

    def run_full_test(self, limit_sources=None):
        """Exécuter le test complet"""
        print("🚀 Démarrage du test batch extraction...")
        print("=" * 60)

        config = self.load_sources_config()

        # Test YouTube
        print("\n📺 TESTS YOUTUBE:")
        print("-" * 30)

        youtube_channels = config.get("youtube_channels", [])
        if limit_sources:
            youtube_channels = youtube_channels[:limit_sources]

        for i, channel in enumerate(youtube_channels, 1):
            print(f"{i}. {channel['name']}... ", end="", flush=True)
            result = self.test_single_source("youtube", channel["id"], channel["name"])
            self.results[f"youtube_{channel['name']}"] = result

            if result["status"] == "success":
                count = result["artists_count"]
                print(f"✅ {count} artistes")
                if count > 0 and result.get("sample_artists"):
                    print(f"   Exemples: {', '.join(result['sample_artists'])}")
            elif result["status"] == "quota_exceeded":
                print(f"🚫 QUOTA ÉPUISÉ")
            else:
                print(f"❌ Erreur: {result['error']}")

        # Test Spotify
        # print("\n🎵 TESTS SPOTIFY:")
        # print("-" * 30)

        # spotify_playlists = config.get("spotify_playlists", [])
        # if limit_sources:
        #     spotify_playlists = spotify_playlists[:limit_sources]

        # for i, playlist in enumerate(spotify_playlists, 1):
        #     print(f"{i}. {playlist['name']}... ", end="", flush=True)

        #     result = self.test_single_source("spotify", playlist["id"], playlist["name"])
        #     self.results[f"spotify_{playlist['name']}"] = result

        #     if result["status"] == "success":
        #         count = result["artists_count"]
        #         print(f"✅ {count} artistes")
        #         if count > 0 and result.get("sample_artists"):
        #             print(f"   Exemples: {', '.join(result['sample_artists'])}")
        #     else:
        #         print(f"❌ Erreur: {result['error']}")

    def generate_report(self):
        """Générer le rapport final"""
        print("\n" + "=" * 60)
        print("📊 RAPPORT FINAL")
        print("=" * 60)

        # Statistiques par type
        youtube_success = sum(
            1
            for k, v in self.results.items()
            if k.startswith("youtube_")
            and v["status"] == "success"
            and v["artists_count"] > 0
        )
        spotify_success = sum(
            1
            for k, v in self.results.items()
            if k.startswith("spotify_")
            and v["status"] == "success"
            and v["artists_count"] > 0
        )

        youtube_total = sum(1 for k in self.results.keys() if k.startswith("youtube_"))
        spotify_total = sum(1 for k in self.results.keys() if k.startswith("spotify_"))

        total_artists_found = sum(
            v["artists_count"]
            for v in self.results.values()
            if v["status"] == "success"
        )
        unique_artists = len(self.total_artists)

        print(f"📺 YouTube: {youtube_success}/{youtube_total} sources fonctionnelles")
        print(f"🎵 Spotify: {spotify_success}/{spotify_total} sources fonctionnelles")
        print(f"🎯 Total artistes trouvés: {total_artists_found}")
        print(f"🔍 Artistes uniques: {unique_artists}")
        print(f"🔄 Doublons détectés: {len(self.duplicate_artists)}")

        # Top sources
        print(f"\n🏆 TOP SOURCES:")
        top_sources = sorted(
            [
                (k, v["artists_count"])
                for k, v in self.results.items()
                if v["status"] == "success"
            ],
            key=lambda x: x[1],
            reverse=True,
        )[:5]

        for i, (source, count) in enumerate(top_sources, 1):
            source_name = source.replace("youtube_", "").replace("spotify_", "")
            print(f"{i}. {source_name}: {count} artistes")

        # Sources problématiques
        print(f"\n⚠️ SOURCES PROBLÉMATIQUES:")
        problematic = [
            (k, v)
            for k, v in self.results.items()
            if v["status"] == "error" or v["artists_count"] == 0
        ]

        for source, result in problematic:
            source_name = source.replace("youtube_", "").replace("spotify_", "")
            if result["status"] == "error":
                print(f"❌ {source_name}: {result['error']}")
            else:
                print(f"⚪ {source_name}: 0 artistes (patterns d'extraction à revoir)")

        # Recommandations
        print(f"\n💡 RECOMMANDATIONS:")
        print(f"1. Garder les {len(top_sources)} meilleures sources")
        print(f"2. Corriger l'algorithme d'extraction pour les sources à 0 artistes")
        print(f"3. Débugger les erreurs Spotify (authentification)")
        print(
            f"4. Optimiser les quotas API (actuellement ~{total_artists_found * 100} unités utilisées)"
        )

        return {
            "timestamp": datetime.now().isoformat(),
            "youtube_functional": youtube_success,
            "spotify_functional": spotify_success,
            "total_artists": total_artists_found,
            "unique_artists": unique_artists,
            "duplicates": len(self.duplicate_artists),
            "top_sources": top_sources,
            "recommendations": {
                "remove_trap_nation": True,
                "fix_extraction_algorithm": True,
                "debug_spotify_auth": True,
                "optimize_api_quotas": True,
            },
        }

    def save_detailed_report(self, output_file="extraction_report.json"):
        """Sauvegarder le rapport détaillé"""
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "summary": self.generate_report(),
            "detailed_results": self.results,
            "duplicate_artists": dict(self.duplicate_artists),
            "all_unique_artists": list(self.total_artists),
        }

        output_path = Path(__file__).parent.parent / "reports" / output_file
        output_path.parent.mkdir(exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Rapport détaillé sauvegardé: {output_path}")

    def save_manual_review_file(self, output_file="manual_review_artists.txt"):
        """Générer un fichier de contrôle manuel par source puis par vidéo avec vrais artistes"""
        output_path = Path(__file__).parent.parent / "reports" / output_file
        output_path.parent.mkdir(exist_ok=True)

        # Mapping des sources vers leurs IDs
        config = self.load_sources_config()
        source_mapping = {}
        for channel in config.get("youtube_channels", []):
            # Créer la clé en convertissant le nom exactement comme dans le test
            name_key = "youtube_" + channel.get("name", "").replace(" ", "_").lower()
            source_mapping[name_key] = channel.get("id", "")


        with open(output_path, "w", encoding="utf-8") as f:
            f.write("RAPPORT D'EXTRACTION MANUEL - CONTRÔLE QUALITÉ PAR SOURCE ET VIDÉO\n")
            f.write("=" * 75 + "\n")
            f.write(f"Généré le: {datetime.now().isoformat()}\n\n")

            # Trier les sources par nombre d'artistes (descendant)
            sorted_sources = sorted(
                [(k, v) for k, v in self.results.items() if v["status"] == "success"],
                key=lambda x: x[1]["artists_count"],
                reverse=True
            )

            for source_key, result in sorted_sources:
                source_name = source_key.replace("youtube_", "").replace("spotify_", "").upper()
                f.write(f"{source_name} ({result['artists_count']} artistes):\n")
                f.write("-" * 50 + "\n")

                # Récupérer l'ID de la source - convertir la clé en lowercase et remplacer espaces par underscores
                normalized_key = source_key.lower().replace(" ", "_")
                source_id = source_mapping.get(normalized_key, "")

                if source_id and source_key.startswith("youtube_"):
                    # Utiliser le nouvel endpoint pour avoir le détail par vidéo
                    try:
                        response = requests.post(
                            f"{self.base_url}/extraction/video-by-video-report",
                            json={
                                "source_type": "youtube",
                                "source_id": source_id,
                                "source_name": source_name,
                            },
                            timeout=60,
                        )

                        if response.status_code == 200:
                            video_data = response.json()
                            videos = video_data.get("videos", [])

                            for video in videos:  # Toutes les vidéos (50 max)
                                video_num = video["video_number"]
                                title = video["title"]
                                artists = video["artists"]

                                f.write(f"video {video_num}: {title}\n")
                                if artists:
                                    artists_str = ", ".join(artists)
                                    f.write(f"  → artistes: {artists_str}\n\n")
                                else:
                                    f.write(f"  → artistes: [aucun détecté]\n\n")
                        else:
                            f.write(f"[Erreur lors de la récupération des données détaillées]\n\n")

                    except Exception as e:
                        f.write(f"[Erreur API: {str(e)[:50]}]\n\n")
                else:
                    # Fallback: afficher les artistes trouvés globalement
                    artists = result.get("artists", [])
                    for i, artist in enumerate(artists[:10], 1):  # Limiter à 10 premiers
                        f.write(f"video {i}: [titre non disponible]\n")
                        f.write(f"  → artistes: {artist}\n\n")

                f.write("\n")

            # Statistiques de fin
            f.write("=" * 75 + "\n")
            f.write(f"TOTAL: {sum(v['artists_count'] for v in self.results.values() if v['status'] == 'success')} artistes extraits\n")
            f.write(f"UNIQUES: {len(self.total_artists)} artistes uniques\n")
            f.write(f"DOUBLONS: {len(self.duplicate_artists)} détectés\n")

        print(f"📝 Fichier de contrôle manuel sauvegardé: {output_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test batch des sources d'extraction")
    parser.add_argument(
        "--limit", type=int, help="Limiter le nombre de sources à tester"
    )
    parser.add_argument(
        "--youtube-only", action="store_true", help="Tester seulement YouTube"
    )
    parser.add_argument(
        "--spotify-only", action="store_true", help="Tester seulement Spotify"
    )

    args = parser.parse_args()

    reporter = BatchExtractionReporter()

    if args.youtube_only:
        print("🎯 Mode: YouTube uniquement")
    elif args.spotify_only:
        print("🎯 Mode: Spotify uniquement")
    else:
        print("🎯 Mode: Toutes les sources")

    try:
        reporter.run_full_test(limit_sources=args.limit)
        summary = reporter.generate_report()
        reporter.save_detailed_report()
        reporter.save_manual_review_file()

    except KeyboardInterrupt:
        print("\n⏹️ Test interrompu par l'utilisateur")
    except Exception as e:
        print(f"\n❌ Erreur fatale: {e}")
        sys.exit(1)
