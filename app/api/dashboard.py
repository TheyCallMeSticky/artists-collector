"""
Dashboard API pour la gestion manuelle des processus de production
Interface simple avec boutons pour déclencher les phases d'extraction et scoring
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import Dict, Any
from datetime import datetime

from app.db.database import get_db
from app.services.source_extractor import SourceExtractor
from app.services.scoring_service import ScoringService
from app.services.artist_service import ArtistService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/", response_class=HTMLResponse)
def get_dashboard():
    """Interface dashboard HTML simple pour contrôler les processus"""

    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>🎯 Artists Collector - Dashboard de Production</title>
        <meta charset="utf-8">
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                border-radius: 10px;
                text-align: center;
                margin-bottom: 30px;
            }
            .section {
                background: white;
                padding: 25px;
                margin: 20px 0;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            .phase-title {
                color: #333;
                border-bottom: 3px solid #667eea;
                padding-bottom: 10px;
                margin-bottom: 20px;
            }
            .btn {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                padding: 15px 30px;
                border-radius: 8px;
                cursor: pointer;
                font-size: 16px;
                margin: 10px;
                transition: transform 0.2s;
            }
            .btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            }
            .btn-phase1 { background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%); }
            .btn-phase2 { background: linear-gradient(135deg, #2196F3 0%, #1976D2 100%); }
            .btn-scoring { background: linear-gradient(135deg, #FF9800 0%, #F57C00 100%); }
            .btn-status { background: linear-gradient(135deg, #9C27B0 0%, #7B1FA2 100%); }

            .description {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 5px;
                margin: 15px 0;
                border-left: 4px solid #667eea;
            }
            .status-box {
                background: #e3f2fd;
                padding: 15px;
                border-radius: 5px;
                margin: 10px 0;
            }
            .grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🎯 Artists Collector Dashboard</h1>
            <p>Gestion manuelle des processus d'extraction et scoring TubeBuddy</p>
        </div>

        <div class="grid">
            <!-- PHASE 1 -->
            <div class="section">
                <h2 class="phase-title">🚀 PHASE 1 - Extraction Complète</h2>
                <div class="description">
                    <strong>Premier passage :</strong><br>
                    • 50 dernières vidéos de chaque chaîne YouTube<br>
                    • Extraction totale des playlists Spotify<br>
                    • Métadonnées enrichies (genre, style, mood)<br>
                    • Persistance avec dates de tracking
                </div>
                <button class="btn btn-phase1" onclick="startPhase1()">
                    ▶️ Démarrer Phase 1 Complète
                </button>
                <div id="phase1-status" class="status-box" style="display:none;"></div>
            </div>

            <!-- PHASE 2 -->
            <div class="section">
                <h2 class="phase-title">🔄 PHASE 2 - Mise à jour Hebdomadaire</h2>
                <div class="description">
                    <strong>Passage hebdomadaire :</strong><br>
                    • Nouveaux contenus (7 derniers jours)<br>
                    • Re-scoring intelligent<br>
                    • Mise à jour métriques Spotify/YouTube<br>
                    • Optimisé pour quotas API
                </div>
                <button class="btn btn-phase2" onclick="startPhase2()">
                    🔄 Démarrer Phase 2 Hebdomadaire
                </button>
                <div id="phase2-status" class="status-box" style="display:none;"></div>
            </div>

            <!-- SCORING TUBEBUDDY -->
            <div class="section">
                <h2 class="phase-title">🏆 Calculs TubeBuddy</h2>
                <div class="description">
                    <strong>Système de scoring :</strong><br>
                    • Search Volume (40%) + Competition (40%)<br>
                    • Optimization (20%)<br>
                    • Reprise automatique si quota épuisé<br>
                    • Cache optimisé
                </div>
                <button class="btn btn-scoring" onclick="resumeScoring()">
                    📊 Reprendre Calculs TubeBuddy
                </button>
                <button class="btn btn-scoring" onclick="getProcessStatus()">
                    📈 Statut des Processus
                </button>
                <div id="scoring-status" class="status-box" style="display:none;"></div>
            </div>

            <!-- MONITORING -->
            <div class="section">
                <h2 class="phase-title">📊 Monitoring</h2>
                <div class="description">
                    <strong>État du système :</strong><br>
                    • Artistes en base de données<br>
                    • Calculs TubeBuddy terminés<br>
                    • Sources configurées<br>
                    • Quotas API utilisés
                </div>
                <button class="btn btn-status" onclick="getSystemStatus()">
                    📋 État Système
                </button>
                <button class="btn btn-status" onclick="getTopOpportunities()">
                    🎯 Top Opportunités
                </button>
                <div id="system-status" class="status-box" style="display:none;"></div>
            </div>
        </div>

        <script>
            async function apiCall(url, method = 'POST') {
                try {
                    const response = await fetch(url, {
                        method: method,
                        headers: { 'Content-Type': 'application/json' }
                    });
                    return await response.json();
                } catch (error) {
                    return { error: error.message };
                }
            }

            async function startPhase1() {
                document.getElementById('phase1-status').style.display = 'block';
                document.getElementById('phase1-status').innerHTML = '⏳ Démarrage Phase 1...';

                const result = await apiCall('/extraction/phase1-complete');

                if (result.error) {
                    document.getElementById('phase1-status').innerHTML = `❌ Erreur: ${result.error}`;
                } else {
                    document.getElementById('phase1-status').innerHTML = `
                        ✅ Phase 1 terminée !<br>
                        📊 ${result.artists_found} artistes trouvés<br>
                        💾 ${result.artists_saved} artistes sauvés<br>
                        🎯 ${result.priority_artists} prioritaires<br>
                        🔍 ${result.artists_with_enriched_metadata} avec métadonnées enrichies
                    `;
                }
            }

            async function startPhase2() {
                document.getElementById('phase2-status').style.display = 'block';
                document.getElementById('phase2-status').innerHTML = '⏳ Démarrage Phase 2...';

                const result = await apiCall('/extraction/phase2-weekly');

                if (result.error) {
                    document.getElementById('phase2-status').innerHTML = `❌ Erreur: ${result.error}`;
                } else {
                    document.getElementById('phase2-status').innerHTML = `
                        ✅ Phase 2 terminée !<br>
                        📊 ${result.artists_found} artistes trouvés<br>
                        🆕 ${result.new_artists} nouveaux<br>
                        🔄 ${result.updated_artists} mis à jour<br>
                        🏆 ${result.artists_marked_for_rescoring} marqués pour re-scoring
                    `;
                }
            }

            async function resumeScoring() {
                document.getElementById('scoring-status').style.display = 'block';
                document.getElementById('scoring-status').innerHTML = '⏳ Reprise des calculs TubeBuddy...';

                const result = await apiCall('/dashboard/resume-tubebuddy-scoring');

                if (result.error) {
                    document.getElementById('scoring-status').innerHTML = `❌ Erreur: ${result.error}`;
                } else {
                    document.getElementById('scoring-status').innerHTML = `
                        ✅ Calculs en cours !<br>
                        📊 ${result.total_artists} artistes à traiter<br>
                        ✅ ${result.completed} terminés<br>
                        ⏳ ${result.remaining} restants
                    `;
                }
            }

            async function getProcessStatus() {
                const result = await apiCall('/dashboard/process-status', 'GET');

                document.getElementById('scoring-status').style.display = 'block';
                if (result.error) {
                    document.getElementById('scoring-status').innerHTML = `❌ Erreur: ${result.error}`;
                } else {
                    document.getElementById('scoring-status').innerHTML = `
                        📊 Statut des processus :<br>
                        🎯 ${result.total_artists} artistes total<br>
                        ✅ ${result.scored_artists} avec scores TubeBuddy<br>
                        ⏳ ${result.pending_scoring} en attente de calcul<br>
                        📈 Dernier calcul: ${result.last_scoring || 'Jamais'}
                    `;
                }
            }

            async function getSystemStatus() {
                const result = await apiCall('/dashboard/system-status', 'GET');

                document.getElementById('system-status').style.display = 'block';
                if (result.error) {
                    document.getElementById('system-status').innerHTML = `❌ Erreur: ${result.error}`;
                } else {
                    document.getElementById('system-status').innerHTML = `
                        📋 État système :<br>
                        👥 ${result.total_artists} artistes en base<br>
                        📺 ${result.youtube_channels} chaînes YouTube<br>
                        🎵 ${result.spotify_playlists} playlists Spotify<br>
                        🔥 ${result.top_scored} avec excellent score (≥80)
                    `;
                }
            }

            async function getTopOpportunities() {
                const result = await apiCall('/artists/opportunities?limit=10', 'GET');

                document.getElementById('system-status').style.display = 'block';
                if (result.error || !result.opportunities) {
                    document.getElementById('system-status').innerHTML = `❌ Erreur: ${result.error || 'Pas d\\'opportunités'}`;
                } else {
                    let html = '🎯 Top 10 Opportunités :<br><br>';
                    result.opportunities.slice(0, 5).forEach((opp, i) => {
                        html += `${i+1}. <strong>${opp.artist_name}</strong> - Score: ${opp.tubebuddy_score}/100<br>`;
                    });
                    document.getElementById('system-status').innerHTML = html;
                }
            }
        </script>
    </body>
    </html>
    """

    return HTMLResponse(content=html_content)


@router.post("/resume-tubebuddy-scoring")
def resume_tubebuddy_scoring(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Reprendre les calculs TubeBuddy pour les artistes marqués needs_scoring=True"""
    try:
        from app.services.process_manager import ProcessManager
        from app.services.tubebuddy_processor import TubeBuddyProcessor
        import asyncio

        # Vérifier qu'aucun processus n'est en cours
        process_manager = ProcessManager(db)
        if process_manager.has_running_process():
            running = process_manager.get_running_process()
            raise HTTPException(
                status_code=409, 
                detail=f"Un processus {running.process_type} est déjà en cours depuis {running.started_at}"
            )

        # Démarrer en arrière-plan
        async def tubebuddy_task():
            processor = TubeBuddyProcessor(db)
            await processor.run_async()

        background_tasks.add_task(lambda: asyncio.run(tubebuddy_task()))
        
        return {
            "message": "Calculs TubeBuddy démarrés en arrière-plan",
            "type": "tubebuddy",
            "status": "started"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erreur reprise calculs TubeBuddy: {str(e)}"
        )


@router.get("/process-status")
def get_process_status(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Récupérer le statut des processus de scoring"""
    try:
        from app.services.process_manager import ProcessManager
        
        artist_service = ArtistService(db)
        process_manager = ProcessManager(db)

        total_artists = artist_service.count_all_artists()
        scored_artists = artist_service.count_artists_with_scores()
        pending_scoring = artist_service.count_artists_needing_scoring()

        # Dernière date de scoring
        last_score = artist_service.get_latest_score()
        last_scoring_date = last_score.created_at.isoformat() if last_score else None

        # Processus en cours
        current_process = process_manager.get_running_process()
        
        result = {
            "total_artists": total_artists,
            "scored_artists": scored_artists,
            "pending_scoring": pending_scoring,
            "last_scoring": last_scoring_date
        }
        
        # Ajouter les infos du processus en cours
        if current_process:
            result.update({
                "current_process": current_process.to_dict(),
                "is_running": True
            })
        else:
            result["is_running"] = False

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erreur récupération statut processus: {str(e)}"
        )


@router.get("/system-status")
def get_system_status(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Récupérer le statut général du système"""
    try:
        from app.services.source_extractor import SourceExtractor

        artist_service = ArtistService(db)
        extractor = SourceExtractor(db)

        total_artists = artist_service.count_all_artists()
        top_scored = artist_service.count_artists_with_score_above(80)

        sources_config = extractor.sources_config
        youtube_channels = len(sources_config.get("youtube_channels", []))
        spotify_playlists = len(sources_config.get("spotify_playlists", []))

        return {
            "total_artists": total_artists,
            "youtube_channels": youtube_channels,
            "spotify_playlists": spotify_playlists,
            "top_scored": top_scored,
            "sources_configured": youtube_channels + spotify_playlists
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erreur statut système: {str(e)}"
        )