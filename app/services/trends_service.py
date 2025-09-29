"""
Service Google Trends pour obtenir les scores de popularité
Implémente la méthode de l'étude pour reproduire TubeBuddy
"""

import json
import logging
from typing import Dict, Optional
from pytrends.request import TrendReq
import redis
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class TrendsService:
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.pytrends = TrendReq(hl='en-US', tz=360)
        self.redis_client = redis_client

        # Cache TTL : 24h pour les trends (données Google mises à jour quotidiennement)
        self.cache_ttl = 24 * 60 * 60

    def get_trends_score(self, keyword: str) -> float:
        """
        Obtenir le score Google Trends pour un mot-clé (0-100)
        Avec cache Redis pour éviter les appels répétés
        """
        cache_key = f"trends:{keyword.lower()}"

        # Vérifier le cache Redis d'abord
        if self.redis_client:
            try:
                cached_score = self.redis_client.get(cache_key)
                if cached_score:
                    return float(cached_score.decode())
            except Exception as e:
                logger.warning(f"Erreur lecture cache trends: {e}")

        try:
            # Requête Google Trends (sans restriction YouTube pour plus de données)
            self.pytrends.build_payload([keyword], cat=0, timeframe='today 3-m', geo='US', gprop='')

            # Récupérer les données d'intérêt au fil du temps
            interest_over_time_df = self.pytrends.interest_over_time()

            if interest_over_time_df.empty:
                score = 0.0
            else:
                # Calculer la moyenne des 3 derniers mois pour lisser les variations
                if keyword in interest_over_time_df.columns:
                    recent_data = interest_over_time_df[keyword].tail(12)  # 3 derniers mois si données hebdomadaires
                    # Gérer les valeurs manquantes proprement
                    recent_data = recent_data.fillna(0).infer_objects(copy=False)
                    score = float(recent_data.mean())
                else:
                    score = 0.0

            # Mettre en cache
            if self.redis_client:
                try:
                    self.redis_client.setex(cache_key, self.cache_ttl, str(score))
                except Exception as e:
                    logger.warning(f"Erreur mise en cache trends: {e}")

            logger.info(f"Google Trends pour '{keyword}': {score}")
            return score

        except Exception as e:
            logger.error(f"Erreur Google Trends pour '{keyword}': {e}")
            return 0.0

    def get_batch_trends_scores(self, keywords: list) -> Dict[str, float]:
        """
        Obtenir les scores pour plusieurs mots-clés en une fois
        Plus efficace que des appels individuels
        """
        results = {}

        # Traiter par batch de 5 (limite Google Trends)
        batch_size = 5
        for i in range(0, len(keywords), batch_size):
            batch = keywords[i:i + batch_size]

            try:
                # Vérifier le cache pour ce batch
                cached_results = {}
                uncached_keywords = []

                if self.redis_client:
                    for keyword in batch:
                        cache_key = f"trends:{keyword.lower()}"
                        try:
                            cached_score = self.redis_client.get(cache_key)
                            if cached_score:
                                cached_results[keyword] = float(cached_score.decode())
                            else:
                                uncached_keywords.append(keyword)
                        except Exception:
                            uncached_keywords.append(keyword)
                else:
                    uncached_keywords = batch

                # Traiter les mots-clés non cachés
                if uncached_keywords:
                    self.pytrends.build_payload(uncached_keywords, cat=0, timeframe='today 3-m', geo='US', gprop='')
                    interest_over_time_df = self.pytrends.interest_over_time()

                    for keyword in uncached_keywords:
                        if keyword in interest_over_time_df.columns:
                            recent_data = interest_over_time_df[keyword].tail(12)
                            # Gérer les valeurs manquantes proprement
                            recent_data = recent_data.fillna(0).infer_objects(copy=False)
                            score = float(recent_data.mean()) if not recent_data.empty else 0.0
                        else:
                            score = 0.0

                        cached_results[keyword] = score

                        # Mettre en cache
                        if self.redis_client:
                            try:
                                cache_key = f"trends:{keyword.lower()}"
                                self.redis_client.setex(cache_key, self.cache_ttl, str(score))
                            except Exception as e:
                                logger.warning(f"Erreur cache batch trends: {e}")

                # Ajouter aux résultats
                results.update(cached_results)

            except Exception as e:
                logger.error(f"Erreur batch trends pour {batch}: {e}")
                # Remplir avec des scores par défaut
                for keyword in batch:
                    if keyword not in results:
                        results[keyword] = 0.0

        return results

    def get_related_queries(self, keyword: str) -> Dict:
        """
        Obtenir les requêtes associées pour identifier des opportunités
        Utile pour l'optimisation SEO YouTube
        """
        cache_key = f"trends_related:{keyword.lower()}"

        # Vérifier le cache
        if self.redis_client:
            try:
                cached_data = self.redis_client.get(cache_key)
                if cached_data:
                    return json.loads(cached_data.decode())
            except Exception as e:
                logger.warning(f"Erreur lecture cache related: {e}")

        try:
            self.pytrends.build_payload([keyword], cat=0, timeframe='today 3-m', geo='US', gprop='')

            # Récupérer les requêtes associées
            related_queries = self.pytrends.related_queries()

            result = {
                'rising': [],
                'top': []
            }

            if keyword in related_queries and related_queries[keyword]:
                if 'rising' in related_queries[keyword] and related_queries[keyword]['rising'] is not None:
                    result['rising'] = related_queries[keyword]['rising'].to_dict('records')

                if 'top' in related_queries[keyword] and related_queries[keyword]['top'] is not None:
                    result['top'] = related_queries[keyword]['top'].to_dict('records')

            # Mettre en cache pour 7 jours (données moins volatiles)
            if self.redis_client:
                try:
                    self.redis_client.setex(cache_key, 7 * 24 * 60 * 60, json.dumps(result))
                except Exception as e:
                    logger.warning(f"Erreur cache related queries: {e}")

            return result

        except Exception as e:
            logger.error(f"Erreur related queries pour '{keyword}': {e}")
            return {'rising': [], 'top': []}