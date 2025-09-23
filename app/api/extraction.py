import asyncio
import os
from typing import Any, Dict

from app.db.database import get_db
from app.services.source_extractor import SourceExtractor
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

router = APIRouter(prefix="/extraction", tags=["extraction"])

from typing import Optional


class ExtractionResponse(BaseModel):
    extraction_type: str
    timestamp: str
    sources_processed: int
    artists_found: int
    artists_saved: Optional[int] = None
    artists_collected: Optional[int] = None
    new_artists: Optional[int] = None
    updated_artists: Optional[int] = None
    priority_artists: Optional[int] = None
    errors: list


@router.post("/full", response_model=ExtractionResponse)
def run_full_extraction(db: Session = Depends(get_db)):
    """Lancer une extraction complète depuis toutes les sources (premier run)"""
    try:
        extractor = SourceExtractor(db)
        results = extractor.run_full_extraction()

        return ExtractionResponse(**results)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erreur lors de l'extraction complète: {str(e)}"
        )


@router.post("/incremental", response_model=ExtractionResponse)
def run_incremental_extraction(db: Session = Depends(get_db)):
    """Lancer une extraction incrémentale (nouveautés des dernières 24h)"""
    try:
        extractor = SourceExtractor(db)
        results = extractor.run_incremental_extraction()

        return ExtractionResponse(**results)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de l'extraction incrémentale: {str(e)}",
        )


@router.post("/full/background")
def run_full_extraction_background(
    background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    """Lancer une extraction complète en arrière-plan"""

    def extraction_task():
        extractor = SourceExtractor(db)
        extractor.run_full_extraction()

    background_tasks.add_task(extraction_task)
    return {
        "message": "Extraction complète démarrée en arrière-plan",
        "type": "full_extraction",
    }


@router.post("/incremental/background")
def run_incremental_extraction_background(
    background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    """Lancer une extraction incrémentale en arrière-plan"""

    def extraction_task():
        extractor = SourceExtractor(db)
        extractor.run_incremental_extraction()

    background_tasks.add_task(extraction_task)
    return {
        "message": "Extraction incrémentale démarrée en arrière-plan",
        "type": "incremental_extraction",
    }


@router.get("/sources")
def get_configured_sources(db: Session = Depends(get_db)):
    """Récupérer la configuration des sources"""
    try:
        extractor = SourceExtractor(db)
        sources = extractor.sources_config

        return {
            "spotify_playlists": len(sources.get("spotify_playlists", [])),
            "youtube_channels": len(sources.get("youtube_channels", [])),
            "extraction_settings": sources.get("extraction_settings", {}),
            "playlists": [
                {
                    "name": playlist.get("name"),
                    "description": playlist.get("description"),
                }
                for playlist in sources.get("spotify_playlists", [])
            ],
            "channels": [
                {"name": channel.get("name"), "description": channel.get("description")}
                for channel in sources.get("youtube_channels", [])
            ],
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la récupération des sources: {str(e)}",
        )


class TestSourceRequest(BaseModel):
    source_type: str  # "spotify" ou "youtube"
    source_id: str
    source_name: str


@router.post("/test-source")
def test_single_source(request: TestSourceRequest, db: Session = Depends(get_db)):
    """Tester l'extraction depuis une source unique"""

    try:
        extractor = SourceExtractor(db)

        raw_titles = []

        if request.source_type == "spotify":
            artists = extractor.extract_artists_from_spotify_playlist(
                request.source_id, request.source_name
            )
        elif request.source_type == "youtube":
            artists, raw_titles = extractor.extract_artists_from_youtube_channel(
                request.source_id, request.source_name, return_raw_titles=True
            )
        else:
            raise HTTPException(
                status_code=400, detail="Type de source invalide (spotify ou youtube)"
            )

        result = {
            "source_type": request.source_type,
            "source_name": request.source_name,
            "artists_found": len(artists),
            "artists": list(artists),
        }

        # Ajouter les titres bruts pour YouTube
        if request.source_type == "youtube" and raw_titles:
            result["raw_titles"] = raw_titles[:10]  # 10 premiers titres

        return result

    except Exception as e:
        error_msg = str(e)
        if "QUOTA_EXCEEDED_YOUTUBE" in error_msg:
            return {
                "source_type": request.source_type,
                "source_name": request.source_name,
                "artists_found": 0,
                "artists": [],
                "error": "QUOTA_EXCEEDED",
                "error_message": "Quota YouTube épuisé",
            }
        else:
            raise HTTPException(
                status_code=500, detail=f"Erreur lors du test de la source: {error_msg}"
            )


@router.post("/debug-titles")
def debug_youtube_titles(request: TestSourceRequest, db: Session = Depends(get_db)):
    """Debug - Afficher les titres bruts YouTube"""
    if request.source_type != "youtube":
        raise HTTPException(
            status_code=400, detail="Endpoint réservé aux sources YouTube"
        )

    try:
        from app.services.youtube_service import YouTubeService

        youtube_service = YouTubeService()

        # Récupérer directement les vidéos
        videos = youtube_service.get_channel_videos(request.source_id, max_results=10)

        if not videos:
            return {"error": "Aucune vidéo trouvée", "titles": []}

        titles = [video.get("title", "Titre manquant") for video in videos]

        return {
            "source_name": request.source_name,
            "videos_count": len(videos),
            "raw_titles": titles,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur debug: {str(e)}")


@router.post("/video-by-video-report")
def get_video_by_video_report(
    request: TestSourceRequest, db: Session = Depends(get_db)
):
    """Endpoint temporaire - Rapport détaillé par vidéo avec artistes extraits"""
    if request.source_type != "youtube":
        raise HTTPException(
            status_code=400, detail="Endpoint réservé aux sources YouTube"
        )

    try:
        from app.services.youtube_service import YouTubeService

        extractor = SourceExtractor(db)
        youtube_service = YouTubeService()

        # Récupérer les vidéos (utilise la variable d'environnement)
        max_results = int(os.getenv("YOUTUBE_VIDEOS_PER_CHANNEL", 50))
        videos = youtube_service.get_channel_videos(
            request.source_id, max_results=max_results
        )

        if not videos:
            return {"error": "Aucune vidéo trouvée", "videos": []}

        video_reports = []

        for i, video in enumerate(videos, 1):
            title = video.get("title", "Titre manquant")

            # Extraire les artistes de ce titre spécifique
            extracted_artists = extractor._extract_artist_names_from_text(title)

            video_reports.append(
                {
                    "video_number": i,
                    "title": title,
                    "artists": list(extracted_artists) if extracted_artists else [],
                    "artists_count": len(extracted_artists) if extracted_artists else 0,
                }
            )

        total_artists = sum(len(v["artists"]) for v in video_reports)

        return {
            "source_name": request.source_name,
            "videos_count": len(video_reports),
            "total_artists": total_artists,
            "videos": video_reports,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur rapport vidéo: {str(e)}")
