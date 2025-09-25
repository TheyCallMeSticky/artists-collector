from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON
from sqlalchemy.sql import func
from app.db.database import Base

class ProcessStatus(Base):
    __tablename__ = "process_status"

    id = Column(Integer, primary_key=True, index=True)
    process_type = Column(String(50), nullable=False)  # phase1, phase2, tubebuddy
    status = Column(String(20), nullable=False)  # running, completed, error, cancelled
    progress_percentage = Column(Integer, default=0)
    current_step = Column(String(200))
    
    # Métriques de progression
    sources_processed = Column(Integer, default=0)
    total_sources = Column(Integer, default=0)
    artists_processed = Column(Integer, default=0)
    artists_saved = Column(Integer, default=0)
    new_artists = Column(Integer, default=0)
    updated_artists = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    
    # Informations contextuelles
    current_source = Column(String(200))
    error_message = Column(Text)
    result_data = Column(JSON)  # Résultats finaux
    
    # Timestamps
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    last_update = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Flags
    is_active = Column(Boolean, default=True)
    can_be_cancelled = Column(Boolean, default=True)

    def to_dict(self):
        """Convertir en dictionnaire pour l'API"""
        return {
            "id": self.id,
            "process_type": self.process_type,
            "status": self.status,
            "progress_percentage": self.progress_percentage,
            "current_step": self.current_step,
            "sources_processed": self.sources_processed,
            "total_sources": self.total_sources,
            "artists_processed": self.artists_processed,
            "artists_saved": self.artists_saved,
            "new_artists": self.new_artists,
            "updated_artists": self.updated_artists,
            "errors_count": self.errors_count,
            "current_source": self.current_source,
            "error_message": self.error_message,
            "result_data": self.result_data,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "is_active": self.is_active,
            "can_be_cancelled": self.can_be_cancelled
        }

    @classmethod
    def get_running_process(cls, db):
        """Récupérer le processus en cours d'exécution"""
        return db.query(cls).filter(
            cls.status == "running",
            cls.is_active == True
        ).first()

    @classmethod
    def has_running_process(cls, db):
        """Vérifier s'il y a un processus en cours"""
        return cls.get_running_process(db) is not None

    def update_progress(self, db, **kwargs):
        """Mettre à jour la progression du processus"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        
        # Calculer le pourcentage si possible
        if self.total_sources and self.total_sources > 0:
            self.progress_percentage = min(100, int((self.sources_processed / self.total_sources) * 100))
        
        db.commit()
        db.refresh(self)

    def complete(self, db, result_data=None, error_message=None):
        """Marquer le processus comme terminé"""
        from datetime import datetime
        
        self.completed_at = datetime.now()
        self.progress_percentage = 100
        self.is_active = False
        
        if error_message:
            self.status = "error"
            self.error_message = error_message
            self.current_step = "Erreur"
        else:
            self.status = "completed"
            self.current_step = "Terminé"
        
        if result_data:
            self.result_data = result_data
            
        db.commit()
        db.refresh(self)
