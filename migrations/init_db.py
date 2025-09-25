#!/usr/bin/env python3
"""
Script d'initialisation de la base de données pour Artists Collector
"""

import os
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour importer les modules de l'app
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from app.db.database import Base, DATABASE_URL
from app.models.artist import Artist, CollectionLog, Score
from app.models.process_status import ProcessStatus
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_database():
    """Créer la base de données si elle n'existe pas"""
    try:
        # Extraire le nom de la base de données de l'URL
        if "postgresql://" in DATABASE_URL:
            # Format: postgresql://user:password@host:port/database
            db_name = DATABASE_URL.split('/')[-1]
            base_url = DATABASE_URL.rsplit('/', 1)[0]
            
            # Se connecter à la base postgres par défaut pour créer la DB
            engine = create_engine(f"{base_url}/postgres")
            
            with engine.connect() as conn:
                # Terminer toute transaction en cours
                conn.execute(text("COMMIT"))
                
                # Vérifier si la base existe
                result = conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
                    {"db_name": db_name}
                )
                
                if not result.fetchone():
                    # Créer la base de données
                    conn.execute(text(f"CREATE DATABASE {db_name}"))
                    logger.info(f"Base de données '{db_name}' créée avec succès")
                else:
                    logger.info(f"Base de données '{db_name}' existe déjà")
            
            engine.dispose()
        else:
            logger.info("URL de base de données non PostgreSQL, création ignorée")
            
    except Exception as e:
        logger.error(f"Erreur lors de la création de la base de données: {e}")
        raise

def create_tables():
    """Créer toutes les tables"""
    try:
        engine = create_engine(DATABASE_URL)
        
        # Créer toutes les tables
        Base.metadata.create_all(bind=engine)
        logger.info("Tables créées avec succès")
        
        # Vérifier que les tables ont été créées
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            
            tables = [row[0] for row in result.fetchall()]
            logger.info(f"Tables créées: {', '.join(tables)}")
        
        engine.dispose()
        
    except Exception as e:
        logger.error(f"Erreur lors de la création des tables: {e}")
        raise

def create_indexes():
    """Créer des index pour optimiser les performances"""
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            # Index sur le score pour les requêtes de top artistes
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_artists_score 
                ON artists (score DESC) 
                WHERE is_active = true
            """))
            
            # Index sur les IDs externes
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_artists_spotify_id 
                ON artists (spotify_id) 
                WHERE spotify_id IS NOT NULL
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_artists_youtube_id 
                ON artists (youtube_channel_id) 
                WHERE youtube_channel_id IS NOT NULL
            """))
            
            # Index sur les logs de collection
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_collection_logs_artist_id 
                ON collection_logs (artist_id, created_at DESC)
            """))
            
            # Index sur les scores
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_scores_artist_id 
                ON scores (artist_id, created_at DESC)
            """))
            
            # Index sur les processus
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_process_status_running 
                ON process_status (status, is_active) 
                WHERE status = 'running' AND is_active = true
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_process_status_history 
                ON process_status (started_at DESC, process_type)
            """))
            
            conn.commit()
            logger.info("Index créés avec succès")
        
        engine.dispose()
        
    except Exception as e:
        logger.error(f"Erreur lors de la création des index: {e}")
        raise

def insert_sample_data():
    """Pas de données d'exemple - base vide pour de vraies données"""
    logger.info("Pas de données d'exemple insérées - base prête pour de vraies données")

def main():
    """Fonction principale d'initialisation"""
    logger.info("Début de l'initialisation de la base de données")
    
    try:
        # 1. Créer la base de données
        create_database()
        
        # 2. Créer les tables
        create_tables()
        
        # 3. Créer les index
        create_indexes()
        
        # 4. Insérer des données d'exemple
        insert_sample_data()
        
        logger.info("Initialisation de la base de données terminée avec succès")
        
    except Exception as e:
        logger.error(f"Échec de l'initialisation: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
