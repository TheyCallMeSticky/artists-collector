from sqlalchemy.orm import Session
from app.models.artist import Artist, CollectionLog, Score
from app.schemas.artist import ArtistCreate, ArtistUpdate, CollectionLogCreate, ScoreCreate
from typing import List, Optional

class ArtistService:
    def __init__(self, db: Session):
        self.db = db

    def create_artist(self, artist: ArtistCreate) -> Artist:
        db_artist = Artist(**artist.dict())
        self.db.add(db_artist)
        self.db.commit()
        self.db.refresh(db_artist)
        return db_artist

    def get_artist(self, artist_id: int) -> Optional[Artist]:
        return self.db.query(Artist).filter(Artist.id == artist_id).first()

    def get_artist_by_spotify_id(self, spotify_id: str) -> Optional[Artist]:
        return self.db.query(Artist).filter(Artist.spotify_id == spotify_id).first()

    def get_artist_by_youtube_id(self, youtube_id: str) -> Optional[Artist]:
        return self.db.query(Artist).filter(Artist.youtube_channel_id == youtube_id).first()
    
    def get_artist_by_name(self, name: str) -> Optional[Artist]:
        """Rechercher un artiste par nom (insensible à la casse)"""
        return self.db.query(Artist).filter(Artist.name.ilike(f"%{name}%")).first()

    def get_artists(self, skip: int = 0, limit: int = 100) -> List[Artist]:
        return self.db.query(Artist).order_by(Artist.id.desc()).offset(skip).limit(limit).all()

    def get_top_artists_by_score(self, limit: int = 50) -> List[Artist]:
        return self.db.query(Artist).filter(Artist.is_active == True).order_by(Artist.score.desc()).limit(limit).all()

    def get_artists_by_criteria(
        self,
        min_followers: Optional[int] = None,
        max_followers: Optional[int] = None,
        max_monthly_listeners: Optional[int] = None,
        limit: int = 100
    ) -> List[Artist]:
        """
        Récupérer les artistes selon des critères de filtrage TubeBuddy
        """
        query = self.db.query(Artist).filter(Artist.is_active == True)

        # Filtres Spotify
        if min_followers is not None:
            query = query.filter(Artist.spotify_followers >= min_followers)

        if max_followers is not None:
            query = query.filter(Artist.spotify_followers <= max_followers)

        if max_monthly_listeners is not None:
            query = query.filter(Artist.spotify_monthly_listeners <= max_monthly_listeners)

        # Trier par popularité décroissante et limiter
        return query.order_by(Artist.spotify_popularity.desc()).limit(limit).all()

    def update_artist(self, artist_id: int, artist_update: ArtistUpdate) -> Optional[Artist]:
        db_artist = self.get_artist(artist_id)
        if db_artist:
            update_data = artist_update.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_artist, field, value)
            self.db.commit()
            self.db.refresh(db_artist)
        return db_artist

    def delete_artist(self, artist_id: int) -> bool:
        db_artist = self.get_artist(artist_id)
        if db_artist:
            self.db.delete(db_artist)
            self.db.commit()
            return True
        return False

    def log_collection(self, log_data: CollectionLogCreate) -> CollectionLog:
        db_log = CollectionLog(**log_data.dict())
        self.db.add(db_log)
        self.db.commit()
        self.db.refresh(db_log)
        return db_log

    def create_score(self, score_data: ScoreCreate) -> Score:
        db_score = Score(**score_data.dict())
        self.db.add(db_score)
        self.db.commit()
        self.db.refresh(db_score)
        return db_score

    def get_artist_scores(self, artist_id: int) -> List[Score]:
        return self.db.query(Score).filter(Score.artist_id == artist_id).order_by(Score.created_at.desc()).all()

    # Méthodes pour le dashboard

    def get_artists_needing_scoring(self) -> List[Artist]:
        """Récupérer les artistes qui ont besoin d'un calcul TubeBuddy (needs_scoring=True)"""
        return self.db.query(Artist).filter(Artist.needs_scoring == True, Artist.is_active == True).all()

    def count_all_artists(self) -> int:
        """Compter le nombre total d'artistes actifs"""
        return self.db.query(Artist).filter(Artist.is_active == True).count()

    def count_artists_with_scores(self) -> int:
        """Compter le nombre d'artistes qui ont au moins un score TubeBuddy"""
        return self.db.query(Artist).join(Score, Artist.id == Score.artist_id).filter(Artist.is_active == True).distinct().count()

    def count_artists_needing_scoring(self) -> int:
        """Compter le nombre d'artistes en attente de calcul TubeBuddy"""
        return self.db.query(Artist).filter(Artist.needs_scoring == True, Artist.is_active == True).count()

    def count_artists_with_score_above(self, min_score: int) -> int:
        """Compter le nombre d'artistes avec un score TubeBuddy supérieur à la valeur donnée"""
        return (self.db.query(Artist)
                .join(Score)
                .filter(Artist.is_active == True, Score.score_value >= min_score)
                .distinct()
                .count())

    def get_latest_score(self) -> Optional[Score]:
        """Récupérer le score le plus récent calculé"""
        return self.db.query(Score).order_by(Score.created_at.desc()).first()
