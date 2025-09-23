"""
Service d'extraction automatique d'artistes depuis les sources configurées
"""

import html
import json
import logging
import os
import re
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from app.services.data_collector import DataCollector
from app.services.spotify_service import SpotifyService
from app.services.youtube_service import YouTubeService
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class SourceExtractor:
    def __init__(self, db_session: Session):
        self.db = db_session
        self.spotify_service = SpotifyService()
        self.youtube_service = YouTubeService()
        self.data_collector = DataCollector(db_session)
        self.sources_config = self._load_sources_config()

    def _load_sources_config(self) -> Dict[str, Any]:
        """Charger la configuration des sources"""
        config_path = Path(__file__).parent.parent.parent / "config" / "sources.json"

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Fichier de configuration non trouvé: {config_path}")
            return {
                "spotify_playlists": [],
                "youtube_channels": [],
                "extraction_settings": {},
            }
        except json.JSONDecodeError as e:
            logger.error(f"Erreur de parsing JSON: {e}")
            return {
                "spotify_playlists": [],
                "youtube_channels": [],
                "extraction_settings": {},
            }

    def extract_artists_from_spotify_playlist(
        self,
        playlist_id: str,
        playlist_name: str,
        since_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Extraire les noms d'artistes avec dates depuis une playlist Spotify"""
        artists = []

        try:
            # Priorité: Variable d'environnement > Config JSON > Défaut (100)
            limit = int(
                os.getenv(
                    "SPOTIFY_TRACKS_PER_PLAYLIST",
                    self.sources_config.get("extraction_settings", {}).get(
                        "spotify_tracks_per_playlist", 100
                    ),
                )
            )
            tracks = self.spotify_service.get_playlist_tracks(playlist_id, limit=limit)

            if not tracks:
                logger.warning(f"Aucune track trouvée pour la playlist {playlist_name}")
                return artists

            for track in tracks:
                try:
                    # Filtrer par date si spécifié
                    if since_date and track.get("added_at"):
                        added_date = datetime.fromisoformat(
                            track["added_at"].replace("Z", "+00:00")
                        )
                        if added_date < since_date:
                            continue

                    # Extraire les artistes de la track avec date
                    track_artists = track.get("track", {}).get("artists", [])
                    for artist in track_artists:
                        artist_name = artist.get("name", "").strip()
                        if artist_name and len(artist_name) > 1:
                            artists.append(
                                {
                                    "name": artist_name,
                                    "source": "spotify",
                                    "source_name": playlist_name,
                                    "appearance_date": (
                                        added_date if since_date else datetime.now()
                                    ),
                                }
                            )

                except Exception as e:
                    logger.warning(f"Erreur lors du traitement d'une track: {e}")
                    continue

            logger.info(f"Playlist {playlist_name}: {len(artists)} artistes extraits")
            return artists

        except Exception as e:
            logger.error(
                f"Erreur lors de l'extraction de la playlist {playlist_name}: {e}"
            )
            return artists

    def extract_artists_from_youtube_channel(
        self,
        channel_id: str,
        channel_name: str,
        since_date: Optional[datetime] = None,
        return_raw_titles: bool = False,
    ) -> List[Dict[str, Any]]:
        """Extraire les noms d'artistes avec dates depuis une chaîne YouTube"""
        artists = []
        raw_titles = []

        try:
            # Priorité: Variable d'environnement > Config JSON > Défaut (50)
            max_results = int(os.getenv("YOUTUBE_VIDEOS_PER_CHANNEL", 50))
            videos = self.youtube_service.get_channel_videos(
                channel_id, max_results=max_results
            )

            if not videos:
                logger.warning(f"Aucune vidéo trouvée pour la chaîne {channel_name}")
                return artists if not return_raw_titles else (artists, [])

            for video in videos:
                try:
                    # Filtrer par date si spécifié
                    if since_date and video.get("published_at"):
                        published_date = datetime.fromisoformat(
                            video["published_at"].replace("Z", "+00:00")
                        )
                        if published_date < since_date:
                            continue

                    # Extraire les artistes du titre et de la description avec date
                    title = video.get("title", "")
                    description = video.get("description", "")

                    # Stocker les titres bruts pour debug
                    if return_raw_titles:
                        raw_titles.append(title)

                    # Patterns pour extraire les noms d'artistes
                    extracted_names = self._extract_artist_names_from_text(
                        title + " " + description
                    )

                    for artist_name in extracted_names:
                        artists.append(
                            {
                                "name": artist_name,
                                "source": "youtube",
                                "source_name": channel_name,
                                "appearance_date": (
                                    published_date if since_date else datetime.now()
                                ),
                            }
                        )

                except Exception as e:
                    logger.error(
                        f"Erreur lors du traitement de la vidéo '{title}': {e}"
                    )
                    logger.error(f"Traceback complet: {traceback.format_exc()}")
                    continue

            logger.info(f"Chaîne {channel_name}: {len(artists)} artistes extraits")
            return artists if not return_raw_titles else (artists, raw_titles)

        except Exception as e:
            if "YOUTUBE_QUOTA_EXCEEDED" in str(e):
                logger.error(f"Quota YouTube épuisé pour la chaîne {channel_name}")
                raise Exception(f"QUOTA_EXCEEDED_YOUTUBE: {channel_name}")
            else:
                logger.error(
                    f"Erreur lors de l'extraction de la chaîne {channel_name}: {e}"
                )
                return artists if not return_raw_titles else (artists, [])

    def _extract_artist_names_from_text(self, text: str) -> Set[str]:
        """Extraire les noms d'artistes depuis un texte (formats multiples)"""
        artists = set()

        try:
            # Décoder les entités HTML en premier
            text = html.unescape(text)

            # Nettoyer le titre d'abord - prendre seulement la première ligne
            title = text.split("\n")[0].strip()

            # Normaliser les espaces et caractères spéciaux
            title = re.sub(r"\s+", " ", title)
            title = re.sub(r'["""]', '"', title)  # Normaliser les guillemets
            title = re.sub(r"['']", "'", title)  # Normaliser les apostrophes (CORRIGÉ)

            # === PATTERNS SPÉCIFIQUES PAR TYPE DE CONTENU ===

            # Pattern 1: Format standard "Artist(s) - Title"
            standard_pattern = r"^([^-]+?)\s*-\s*(.+?)(?:\s*\(.*\))?(?:\s*\[.*\])?$"
            match = re.match(standard_pattern, title)

            if match:
                artists_part = match.group(1).strip()
                song_part = match.group(2).strip()

                # Extraire les artistes principaux
                main_artists = self._split_artists(artists_part)
                for artist in main_artists:
                    cleaned = self._clean_artist_name(artist)
                    if cleaned:
                        artists.add(cleaned)

                # Chercher des feat dans la partie titre
                artists.update(self._extract_featuring(song_part))
            else:
                # Pattern 2: Formats spéciaux pour les freestyles, cyphers, performances

                # Pattern pour "ARTIST | The Cypher Effect"
                cypher_pattern = r"^([^|]+?)\s*\|\s*The\s+Cypher\s+Effect"
                match = re.search(cypher_pattern, title, re.IGNORECASE)
                if match:
                    artist_name = match.group(1).strip()
                    cleaned = self._clean_artist_name(artist_name)
                    if cleaned:
                        artists.add(cleaned)

                # Pattern pour les freestyles et performances
                performance_patterns = [
                    # "Artist Freestyle" ou "Artist Mafiathon Freestyle"
                    r"^(.+?)\s+(?:Mafiathon\s+)?Freestyle(?:\s|$)",
                    # "Artist X Artist2 Freestyle"
                    r"^(.+?)\s+(?:On\s+The\s+Radar|OTR).*Freestyle",
                    # "Artist (Live Performance)" ou "Artist Live Performance"
                    r"^(.+?)\s*(?:\()?Live\s+Performance(?:\))?",
                    # "Artist Performance"
                    r"^(.+?)\s+Performance(?:\s|$)",
                    # Format "Artist "On The Radar" Freestyle"
                    r'^The\s+(.+?)\s+["\"]On\s+The\s+Radar["\"]',
                    r"^The\s+(.+?)\s+Freestyle(?:\s|$)",
                    # "Artist | Session/Mic Check"
                    r"^(.+?)\s*\|\s*.*(?:Session|Mic\s+Check)",
                    # Format simple pour titres courts
                    r"^([A-Z][A-Za-z0-9$.\s&]+?)(?:\s+[-–]\s+|\s+feat\.\s+|\s+ft\.\s+)",
                ]

                for pattern in performance_patterns:
                    try:
                        match = re.search(pattern, title, re.IGNORECASE)
                        if match:
                            artists_part = match.group(1).strip()
                            # Enlever "The" au début si présent
                            if artists_part.lower().startswith("the "):
                                artists_part = artists_part[4:]

                            # Séparer les artistes multiples
                            extracted = self._split_artists(artists_part)
                            for artist in extracted:
                                cleaned = self._clean_artist_name(artist)
                                if cleaned:
                                    artists.add(cleaned)
                            break
                    except Exception as e:
                        logger.warning(f"Erreur avec le pattern '{pattern}': {e}")
                        continue

                # Pattern 3: Titres sans séparateur mais avec artiste évident
                if not artists:
                    # Format "Artist1 & Artist2 - quelque chose"
                    collab_pattern = (
                        r"^([A-Z][A-Za-z0-9$.\s]+(?:\s+[&xX]\s+[A-Z][A-Za-z0-9$.\s]+)+)"
                    )
                    match = re.search(collab_pattern, title)
                    if match:
                        artists_part = match.group(1).strip()
                        extracted = self._split_artists(artists_part)
                        for artist in extracted:
                            cleaned = self._clean_artist_name(artist)
                            if cleaned:
                                artists.add(cleaned)

            # Extraire les featuring depuis tout le titre (parenthèses/crochets)
            artists.update(self._extract_featuring(title))

            # Si toujours aucun artiste et titre court, essayer extraction directe
            if not artists and len(title.split()) <= 4:
                # Peut-être juste un nom d'artiste seul
                if not any(
                    word in title.lower()
                    for word in [
                        "official",
                        "music",
                        "video",
                        "audio",
                        "lyric",
                        "visualizer",
                        "recap",
                        "commercial",
                        "live",
                        "performance",
                    ]
                ):
                    cleaned = self._clean_artist_name(title)
                    if cleaned:
                        artists.add(cleaned)

        except Exception as e:
            logger.error(f"Erreur dans _extract_artist_names_from_text: {e}")
            logger.error(f"Texte problématique: {text[:200]}")
            logger.error(f"Traceback: {traceback.format_exc()}")

        return artists

    def _split_artists(self, text: str) -> list:
        """Diviser une chaîne en plusieurs artistes"""
        try:
            # Patterns de séparation d'artistes
            separators = [
                r"\s+[xX]\s+",  # X ou x
                r"\s+[&+]\s+",  # & ou +
                r"\s+and\s+",  # and
                r",\s+",  # virgule
                r"\s+vs\.?\s+",  # vs ou vs.
                r"\s+feat\.?\s+",  # feat ou feat.
                r"\s+ft\.?\s+",  # ft ou ft.
                r"\s+featuring\s+",  # featuring
                r"\s+with\s+",  # with
            ]

            # Créer le pattern combiné
            split_pattern = "|".join(f"({sep})" for sep in separators)

            # Diviser en préservant la casse
            parts = re.split(split_pattern, text, flags=re.IGNORECASE)

            # Filtrer les parties non vides et non séparateurs
            artists = []
            for part in parts:
                if part and not re.match(split_pattern, part, re.IGNORECASE):
                    artist = part.strip()
                    if artist:
                        artists.append(artist)

            return artists

        except Exception as e:
            logger.error(f"Erreur dans _split_artists avec texte '{text}': {e}")
            return [text]  # Retourner le texte original en cas d'erreur

    def _extract_featuring(self, text: str) -> Set[str]:
        """Extraire les artistes en featuring"""
        artists = set()

        try:
            # Patterns pour les featuring
            feat_patterns = [
                r"\((?:feat\.?|ft\.?|featuring)\s+([^)]+)\)",
                r"\[(?:feat\.?|ft\.?|featuring)\s+([^]]+)\]",
                r"(?:feat\.?|ft\.?|featuring)\s+([^(\[]+?)(?:\s*\(|\s*\[|$)",
            ]

            for pattern in feat_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for feat_part in matches:
                    # Diviser les multiples featuring
                    feat_artists = self._split_artists(feat_part)
                    for artist in feat_artists:
                        cleaned = self._clean_artist_name(artist)
                        if cleaned:
                            artists.add(cleaned)

        except Exception as e:
            logger.error(f"Erreur dans _extract_featuring: {e}")

        return artists

    def _clean_artist_name(self, name: str) -> Optional[str]:
        """Nettoyer et valider un nom d'artiste"""
        if not name:
            return None

        try:
            # Nettoyer les espaces multiples
            name = re.sub(r"\s+", " ", name).strip()

            # Enlever les parenthèses/crochets résiduels
            name = re.sub(r"[\[\]()]", "", name).strip()

            # Ignorer si trop court ou trop long
            if len(name) < 2 or len(name) > 60:
                return None

            # Liste de mots-clés à exclure (minuscule pour comparaison)
            exclude_keywords = {
                # Mots techniques/formats
                "official",
                "music",
                "video",
                "audio",
                "lyric",
                "lyrics",
                "visualizer",
                "remix",
                "version",
                "edit",
                "extended",
                "instrumental",
                "acoustic",
                "explicit",
                "clean",
                # Actions/descriptions
                "directed",
                "produced",
                "shot",
                "filmed",
                "recorded",
                "mixed",
                "mastered",
                "presents",
                "introduces",
                # Événements/formats
                "interview",
                "talks",
                "documentary",
                "behind",
                "scenes",
                "reaction",
                "review",
                "breakdown",
                "analysis",
                "recap",
                # Plateformes/shows
                "vevo",
                "worldstar",
                "complex",
                "genius",
                "colors",
                "tiny desk",
                "sway",
                "breakfast club",
                # Descriptions génériques
                "album",
                "mixtape",
                "single",
                "track",
                "song",
                "beat",
                "instrumental",
                "type beat",
                "freestyle beat",
                # Actions live
                "live",
                "performance",
                "concert",
                "tour",
                "session",
                "rehearsal",
                "soundcheck",
                "backstage",
                # Fragments HTML/encoding
                "quot",
                "amp",
                "nbsp",
                "ndash",
                "mdash",
                # Mots isolés non pertinents
                "the",
                "and",
                "or",
                "vs",
                "versus",
                "with",
                "from",
                "new",
                "latest",
                "exclusive",
                "premiere",
                "debut",
                "full",
                "complete",
                "entire",
                "whole",
                # Erreurs communes d'extraction
                "experience",
                "effect",
                "records",
                "entertainment",
                "productions",
                "media",
                "group",
                "collective",
            }

            # Vérifier si c'est un mot-clé à exclure
            name_lower = name.lower()

            # Exclure si c'est exactement un mot-clé
            if name_lower in exclude_keywords:
                return None

            # Exclure si contient certaines phrases
            exclude_phrases = [
                "music video",
                "official video",
                "lyric video",
                "live performance",
                "full album",
                "full ep",
                "directed by",
                "produced by",
                "shot by",
                "turns mashups",
                "elevator pitch",
                "mic check",
                "the cypher effect",
                "on the radar",
                "mafiathon freestyle",
                "dj set",
            ]

            for phrase in exclude_phrases:
                if phrase in name_lower:
                    return None

            # Nettoyer les résidus de patterns
            # Enlever "The" au début seulement s'il reste quelque chose après
            if name_lower.startswith("the ") and len(name) > 4:
                potential_name = name[4:].strip()
                # Vérifier que ce n'est pas juste un autre mot-clé
                if potential_name.lower() not in exclude_keywords:
                    name = potential_name

            # Enlever les numéros isolés à la fin (ex: "Artist 2024")
            name = re.sub(r"\s+\d{4}$", "", name).strip()

            # Enlever les mentions réseaux sociaux
            name = re.sub(r"@[\w]+", "", name).strip()

            # Validation finale
            # Au moins 2 caractères alphanumériques
            if not re.search(r"[A-Za-z0-9]{2,}", name):
                return None

            # Pas plus de 4 mots (éviter les phrases)
            if len(name.split()) > 4:
                return None

            # Éviter les patterns numériques seuls
            if re.match(r"^\d+$", name):
                return None

            # Éviter les fragments évidents
            if name_lower.startswith(("feat ", "ft ", "with ", "and ", "x ")):
                return None

            if name_lower.endswith((" feat", " ft", " with", " and", " x")):
                return None

            return name.strip()

        except Exception as e:
            logger.error(f"Erreur dans _clean_artist_name avec '{name}': {e}")
            return None

    def run_full_extraction(self, limit_priority: int = 400) -> Dict[str, Any]:
        """Lancer une extraction complète (premier run avec limite prioritaire)"""
        logger.info("Début de l'extraction complète depuis toutes les sources")

        all_artists = []
        results = {
            "extraction_type": "full",
            "timestamp": datetime.now().isoformat(),
            "sources_processed": 0,
            "artists_found": 0,
            "artists_saved": 0,
            "priority_artists": 0,
            "errors": [],
        }

        # Extraction depuis Spotify
        for playlist in self.sources_config.get("spotify_playlists", []):
            try:
                playlist_artists = self.extract_artists_from_spotify_playlist(
                    playlist["id"], playlist["name"]
                )
                all_artists.extend(playlist_artists)
                results["sources_processed"] += 1

            except Exception as e:
                error_msg = f"Erreur playlist Spotify {playlist['name']}: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)

        # Extraction depuis YouTube
        for channel in self.sources_config.get("youtube_channels", []):
            try:
                channel_artists = self.extract_artists_from_youtube_channel(
                    channel["id"], channel["name"]
                )
                all_artists.extend(channel_artists)
                results["sources_processed"] += 1

            except Exception as e:
                error_msg = f"Erreur chaîne YouTube {channel['name']}: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)

        # Déduplication et tri par date d'apparition la plus récente
        artists_dict = {}
        for artist_data in all_artists:
            name = artist_data["name"]
            if (
                name not in artists_dict
                or artist_data["appearance_date"]
                > artists_dict[name]["appearance_date"]
            ):
                artists_dict[name] = artist_data

        # Convertir en liste et trier par date (plus récent en premier)
        unique_artists = list(artists_dict.values())
        unique_artists.sort(key=lambda x: x["appearance_date"], reverse=True)

        results["artists_found"] = len(unique_artists)

        # Sauvegarder TOUS les artistes en base
        saved_count = 0
        priority_count = 0
        now = datetime.now()

        for i, artist_data in enumerate(unique_artists):
            try:
                artist_name = artist_data["name"]
                appearance_date = artist_data["appearance_date"]

                # Vérifier si l'artiste existe déjà
                existing_artist = self.data_collector.artist_service.get_artist_by_name(
                    artist_name
                )

                if existing_artist:
                    # Artiste existant : MAJ last_seen_date et most_recent_appearance
                    if (
                        not existing_artist.most_recent_appearance
                        or appearance_date > existing_artist.most_recent_appearance
                    ):
                        existing_artist.most_recent_appearance = appearance_date
                        existing_artist.needs_scoring = True  # Nouveau contenu détecté

                    existing_artist.last_seen_date = now
                    self.db.commit()

                else:
                    # Nouvel artiste : collecter les données complètes
                    collection_result = self.data_collector.collect_and_save_artist(
                        artist_name
                    )
                    if collection_result.get("success"):
                        # MAJ avec les dates d'extraction
                        artist_id = collection_result.get("artist_id")
                        if artist_id:
                            artist = self.data_collector.artist_service.get_artist(
                                artist_id
                            )
                            if artist:
                                artist.most_recent_appearance = appearance_date
                                artist.last_seen_date = now
                                artist.needs_scoring = True

                                # Marquer comme prioritaire si dans les X premiers
                                if i < limit_priority:
                                    priority_count += 1

                                self.db.commit()

                saved_count += 1

            except Exception as e:
                logger.warning(
                    f"Erreur lors du traitement de {artist_data['name']}: {e}"
                )

        results["artists_saved"] = saved_count
        results["priority_artists"] = priority_count

        logger.info(
            f"Extraction complète terminée: {saved_count}/{len(unique_artists)} artistes traités, {priority_count} prioritaires"
        )
        return results

    def run_incremental_extraction(self) -> Dict[str, Any]:
        """Lancer une extraction incrémentale (nouveautés des dernières 24h)"""
        frequency_hours = self.sources_config.get("extraction_settings", {}).get(
            "extraction_frequency_hours", 24
        )
        since_date = datetime.now() - timedelta(hours=frequency_hours)

        logger.info(f"Début de l'extraction incrémentale (depuis {since_date})")

        all_artists = set()
        results = {
            "extraction_type": "incremental",
            "timestamp": datetime.now().isoformat(),
            "since_date": since_date.isoformat(),
            "sources_processed": 0,
            "artists_found": 0,
            "artists_saved": 0,
            "errors": [],
        }

        # Extraction depuis Spotify (nouveautés)
        for playlist in self.sources_config.get("spotify_playlists", []):
            try:
                playlist_artists = self.extract_artists_from_spotify_playlist(
                    playlist["id"], playlist["name"], since_date=since_date
                )
                all_artists.update(playlist_artists)
                results["sources_processed"] += 1

            except Exception as e:
                error_msg = f"Erreur playlist Spotify {playlist['name']}: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)

        # Extraction depuis YouTube (nouveautés)
        for channel in self.sources_config.get("youtube_channels", []):
            try:
                channel_artists = self.extract_artists_from_youtube_channel(
                    channel["id"], channel["name"], since_date=since_date
                )
                all_artists.update(channel_artists)
                results["sources_processed"] += 1

            except Exception as e:
                error_msg = f"Erreur chaîne YouTube {channel['name']}: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)

        # Déduplication et traitement des artistes avec dates
        artists_dict = {}
        for artist_data in all_artists:
            name = artist_data["name"]
            if (
                name not in artists_dict
                or artist_data["appearance_date"]
                > artists_dict[name]["appearance_date"]
            ):
                artists_dict[name] = artist_data

        unique_artists = list(artists_dict.values())
        results["artists_found"] = len(unique_artists)

        # Traiter chaque artiste (nouveau ou MAJ existant)
        new_artists = 0
        updated_artists = 0
        now = datetime.now()

        for artist_data in unique_artists:
            try:
                artist_name = artist_data["name"]
                appearance_date = artist_data["appearance_date"]

                # Vérifier si l'artiste existe déjà
                existing_artist = self.data_collector.artist_service.get_artist_by_name(
                    artist_name
                )

                if existing_artist:
                    # Artiste existant réapparu : MAJ dates et marquer pour recalcul
                    if (
                        not existing_artist.most_recent_appearance
                        or appearance_date > existing_artist.most_recent_appearance
                    ):
                        existing_artist.most_recent_appearance = appearance_date
                        existing_artist.needs_scoring = (
                            True  # Nouveau contenu = recalcul score
                        )
                        updated_artists += 1
                        logger.info(
                            f"Artiste existant réapparu: {artist_name} (nouveau contenu détecté)"
                        )

                    existing_artist.last_seen_date = now
                    self.db.commit()

                else:
                    # Nouvel artiste : collecter les données complètes
                    collection_result = self.data_collector.collect_and_save_artist(
                        artist_name
                    )
                    if collection_result.get("success"):
                        # MAJ avec les dates d'extraction
                        artist_id = collection_result.get("artist_id")
                        if artist_id:
                            artist = self.data_collector.artist_service.get_artist(
                                artist_id
                            )
                            if artist:
                                artist.most_recent_appearance = appearance_date
                                artist.last_seen_date = now
                                artist.needs_scoring = True
                                self.db.commit()
                                new_artists += 1
                                logger.info(f"Nouvel artiste découvert: {artist_name}")

            except Exception as e:
                logger.warning(
                    f"Erreur lors du traitement de {artist_data['name']}: {e}"
                )

        results["new_artists"] = new_artists
        results["updated_artists"] = updated_artists

        logger.info(
            f"Extraction incrémentale terminée: {new_artists} nouveaux, {updated_artists} mis à jour"
        )
        return results
