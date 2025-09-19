#!/usr/bin/env python3
"""
Script de sauvegarde de la base de données Artists Collector
"""

import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path
import logging

# Ajouter le répertoire parent au path
sys.path.append(str(Path(__file__).parent.parent))

from app.db.database import DATABASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_backup():
    """Créer une sauvegarde de la base de données"""
    try:
        # Créer le répertoire de sauvegarde s'il n'existe pas
        backup_dir = Path(__file__).parent.parent / "backups"
        backup_dir.mkdir(exist_ok=True)
        
        # Nom du fichier de sauvegarde avec timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"artists_collector_backup_{timestamp}.sql"
        
        # Extraire les informations de connexion de l'URL
        if not DATABASE_URL.startswith("postgresql://"):
            raise ValueError("Seules les bases PostgreSQL sont supportées")
        
        # Commande pg_dump
        cmd = [
            "pg_dump",
            DATABASE_URL,
            "--no-password",
            "--verbose",
            "--clean",
            "--no-acl",
            "--no-owner",
            "-f", str(backup_file)
        ]
        
        logger.info(f"Création de la sauvegarde: {backup_file}")
        
        # Exécuter pg_dump
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"Sauvegarde créée avec succès: {backup_file}")
            logger.info(f"Taille du fichier: {backup_file.stat().st_size} bytes")
            return str(backup_file)
        else:
            logger.error(f"Erreur lors de la sauvegarde: {result.stderr}")
            return None
            
    except Exception as e:
        logger.error(f"Erreur lors de la création de la sauvegarde: {e}")
        return None

def cleanup_old_backups(keep_days=7):
    """Supprimer les anciennes sauvegardes"""
    try:
        backup_dir = Path(__file__).parent.parent / "backups"
        if not backup_dir.exists():
            return
        
        cutoff_time = datetime.now().timestamp() - (keep_days * 24 * 3600)
        deleted_count = 0
        
        for backup_file in backup_dir.glob("artists_collector_backup_*.sql"):
            if backup_file.stat().st_mtime < cutoff_time:
                backup_file.unlink()
                deleted_count += 1
                logger.info(f"Sauvegarde supprimée: {backup_file.name}")
        
        if deleted_count > 0:
            logger.info(f"{deleted_count} anciennes sauvegardes supprimées")
        else:
            logger.info("Aucune ancienne sauvegarde à supprimer")
            
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage: {e}")

def list_backups():
    """Lister les sauvegardes disponibles"""
    try:
        backup_dir = Path(__file__).parent.parent / "backups"
        if not backup_dir.exists():
            logger.info("Aucun répertoire de sauvegarde trouvé")
            return
        
        backups = list(backup_dir.glob("artists_collector_backup_*.sql"))
        
        if not backups:
            logger.info("Aucune sauvegarde trouvée")
            return
        
        logger.info(f"Sauvegardes disponibles ({len(backups)}):")
        for backup in sorted(backups, key=lambda x: x.stat().st_mtime, reverse=True):
            size = backup.stat().st_size
            mtime = datetime.fromtimestamp(backup.stat().st_mtime)
            logger.info(f"  {backup.name} - {size} bytes - {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
            
    except Exception as e:
        logger.error(f"Erreur lors de la liste des sauvegardes: {e}")

def main():
    """Fonction principale"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Gestion des sauvegardes de la base de données")
    parser.add_argument("action", choices=["backup", "list", "cleanup"], 
                       help="Action à effectuer")
    parser.add_argument("--keep-days", type=int, default=7,
                       help="Nombre de jours de sauvegardes à conserver (défaut: 7)")
    
    args = parser.parse_args()
    
    if args.action == "backup":
        backup_file = create_backup()
        if backup_file:
            cleanup_old_backups(args.keep_days)
    elif args.action == "list":
        list_backups()
    elif args.action == "cleanup":
        cleanup_old_backups(args.keep_days)

if __name__ == "__main__":
    main()
