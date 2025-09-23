#!/usr/bin/env python3
"""
Script pour gérer le cache YouTube
- Lister les fichiers de cache
- Voir le contenu d'un fichier de cache
- Supprimer des fichiers de cache
- Créer du cache de test
"""

import json
import os
from pathlib import Path
import argparse
from datetime import datetime

class CacheManager:
    def __init__(self):
        self.cache_dir = Path(__file__).parent.parent / "cache" / "youtube"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def list_cache_files(self):
        """Lister tous les fichiers de cache"""
        print(f"📁 Cache directory: {self.cache_dir}")
        print("-" * 50)

        files = list(self.cache_dir.glob("*.json"))
        if not files:
            print("❌ Aucun fichier de cache trouvé")
            return

        print(f"✅ {len(files)} fichier(s) de cache trouvé(s):")
        for file in files:
            stat = file.stat()
            size_kb = stat.st_size / 1024
            modified = datetime.fromtimestamp(stat.st_mtime)
            print(f"  • {file.name} ({size_kb:.1f} KB) - {modified.strftime('%Y-%m-%d %H:%M:%S')}")

    def show_cache_content(self, cache_key: str):
        """Afficher le contenu d'un fichier de cache"""
        cache_file = self.cache_dir / f"{cache_key}.json"

        if not cache_file.exists():
            print(f"❌ Fichier de cache non trouvé: {cache_file}")
            return

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            print(f"📄 Contenu du cache: {cache_key}")
            print("-" * 50)
            print(f"Type: {type(data)}")

            if isinstance(data, dict):
                if 'items' in data:
                    items = data['items']
                    print(f"Nombre d'items: {len(items)}")
                    if items:
                        print("Premier item:")
                        print(json.dumps(items[0], indent=2, ensure_ascii=False)[:500] + "...")
                else:
                    print("Structure:")
                    for key in data.keys():
                        print(f"  - {key}: {type(data[key])}")

            print(f"\nTaille du fichier: {cache_file.stat().st_size} bytes")

        except Exception as e:
            print(f"❌ Erreur lors de la lecture: {e}")

    def delete_cache(self, cache_key: str = None):
        """Supprimer un fichier de cache ou tous les fichiers"""
        if cache_key:
            cache_file = self.cache_dir / f"{cache_key}.json"
            if cache_file.exists():
                cache_file.unlink()
                print(f"✅ Cache supprimé: {cache_key}")
            else:
                print(f"❌ Cache non trouvé: {cache_key}")
        else:
            files = list(self.cache_dir.glob("*.json"))
            for file in files:
                file.unlink()
            print(f"✅ {len(files)} fichier(s) de cache supprimé(s)")

    def create_test_cache(self, cache_key: str):
        """Créer un fichier de cache de test"""
        test_data = {
            "items": [
                {
                    "id": {"videoId": "test123"},
                    "snippet": {
                        "title": "Test Artist - Test Song",
                        "description": "Test description",
                        "publishedAt": "2024-01-01T00:00:00Z",
                        "thumbnails": {"default": {"url": "https://test.com/thumb.jpg"}}
                    }
                },
                {
                    "id": {"videoId": "test456"},
                    "snippet": {
                        "title": "Another Artist - Another Song",
                        "description": "Another test description",
                        "publishedAt": "2024-01-02T00:00:00Z",
                        "thumbnails": {"default": {"url": "https://test.com/thumb2.jpg"}}
                    }
                }
            ],
            "_cache_created": datetime.now().isoformat(),
            "_cache_key": cache_key
        }

        cache_file = self.cache_dir / f"{cache_key}.json"
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f, indent=2, ensure_ascii=False)

        print(f"✅ Cache de test créé: {cache_key}")
        print(f"📁 Fichier: {cache_file}")

def main():
    parser = argparse.ArgumentParser(description="Gestionnaire de cache YouTube")
    parser.add_argument("action", choices=["list", "show", "delete", "create-test"],
                       help="Action à effectuer")
    parser.add_argument("--key", help="Clé de cache (pour show, delete, create-test)")
    parser.add_argument("--all", action="store_true", help="Supprimer tous les caches (pour delete)")

    args = parser.parse_args()

    manager = CacheManager()

    if args.action == "list":
        manager.list_cache_files()
    elif args.action == "show":
        if not args.key:
            print("❌ --key requis pour l'action 'show'")
            return
        manager.show_cache_content(args.key)
    elif args.action == "delete":
        if args.all:
            manager.delete_cache()
        elif args.key:
            manager.delete_cache(args.key)
        else:
            print("❌ --key ou --all requis pour l'action 'delete'")
    elif args.action == "create-test":
        if not args.key:
            print("❌ --key requis pour l'action 'create-test'")
            return
        manager.create_test_cache(args.key)

if __name__ == "__main__":
    main()