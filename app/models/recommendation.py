from dataclasses import dataclass
from typing import Optional, List, Dict
import pandas as pd
import numpy as np
import logging
from functools import lru_cache
from difflib import get_close_matches

logger = logging.getLogger(__name__)

@dataclass
class Location:
    ville: str
    quartier: str

@dataclass
class SalaryRange:
    min_rent: float
    max_rent: float
    label: str

    @staticmethod
    def LOW():
        return SalaryRange(0, 50_000, "Bas")
    
    @staticmethod
    def MEDIUM():
        return SalaryRange(50_000, 150_000, "Moyen")
    
    @staticmethod
    def MEDIUM_HIGH():
        return SalaryRange(150_000, 300_000, "Moyen-Haut")
    
    @staticmethod
    def HIGH():
        return SalaryRange(300_000, float('inf'), "Haut")

@dataclass
class RecommendationRequest:
    location: Location
    tranche_salariale: SalaryRange
    nb_personnes: int

@dataclass
class ApartmentStats:
    avg_price: float
    median_price: float
    min_price: float
    max_price: float
    avg_popularity: float
    max_popularity: float
    count: int

class Formatter:
    @staticmethod
    def price(price: float) -> str:
        if price == 0:
            return "Prix non disponible"
        return f"{int(price):,} FCFA"

    @staticmethod
    def percentage(value: float) -> str:
        if value is None or value == 0:
            return "N/A"
        return f"{value:.0f}%"

    @staticmethod
    def views(views: int) -> str:
        return f"{int(views)} vues"

    @staticmethod
    def rooms(rooms: int) -> str:
        return f"{int(rooms)} Ch."

class ApartmentScorer:
    def __init__(self, weights=None):
        self.weights = weights or {
            'price': 0.35,
            'popularity': 0.20,
            'location': 0.25,
            'rooms': 0.20
        }

    def calculate_score(self, apt: pd.Series, request: RecommendationRequest, 
                       stats: ApartmentStats) -> float:
        try:
            scores = {
                'price': self._price_score(
                    apt['prix'], 
                    request.tranche_salariale.max_rent, 
                    stats.avg_price
                ),
                'popularity': self._popularity_score(
                    apt['popularite'], 
                    stats.max_popularity
                ),
                'location': self._location_score(apt, request.location),
                'rooms': self._rooms_score(
                    apt['nb_chambres'], 
                    request.nb_personnes
                )
            }
            
            weighted_score = sum(
                score * self.weights[key] 
                for key, score in scores.items()
            )
            
            modifiers = self._calculate_modifiers(apt, request)
            
            return min(1.0, weighted_score * modifiers)
        except Exception as e:
            logger.error(f"Erreur lors du calcul du score: {str(e)}")
            return 0

    def _price_score(self, price: float, max_budget: float, avg_price: float) -> float:
        if price == 0:
            return 0
        if max_budget == float('inf'):
            return np.exp(-price / (2 * avg_price))
        if price > max_budget:
            return 0
        budget_ratio = price / max_budget
        if budget_ratio <= 0.7:
            return 1.0
        return 1 - ((budget_ratio - 0.7) / 0.3)

    def _popularity_score(self, popularity: float, max_popularity: float) -> float:
        if max_popularity == 0:
            return 0
        return np.sqrt(popularity / max_popularity)

    def _location_score(self, apt: pd.Series, location: Location) -> float:
        if apt['ville'].lower() != location.ville.lower():
            return 0
        
        apt_quartier = apt['quartier'].lower()
        search_quartier = location.quartier.lower()
        
        if apt_quartier == search_quartier:
            return 1.0
        elif apt_quartier.startswith(search_quartier) or search_quartier.startswith(apt_quartier):
            return 0.9
        elif get_close_matches(search_quartier, [apt_quartier], n=1, cutoff=0.8):
            return 0.8
        return 0.5

    def _rooms_score(self, rooms: int, nb_personnes: int) -> float:
        required = max(1, (nb_personnes + 1) // 2)
        if rooms < required:
            return 0
        if rooms == required:
            return 1.0
        return 1 - (0.1 * (rooms - required))

    def _calculate_modifiers(self, apt: pd.Series, request: RecommendationRequest) -> float:
        modifier = 1.0
        if apt['popularite'] > 90:
            modifier *= 1.1
        required_rooms = max(1, (request.nb_personnes + 1) // 2)
        if apt['nb_chambres'] > required_rooms + 2:
            modifier *= 0.9
        return modifier

class ApartmentRecommender:
    def __init__(self, db_connection):
        self.db = db_connection
        self.scorer = ApartmentScorer()
        self._load_data()
        
    def _load_data(self):
        try:
            apartments = self.db.get_all_apartments()
            if not apartments:
                raise Exception("Aucune donnée d'appartement disponible")
                
            self.df = pd.DataFrame(apartments)
            self._preprocess_data()
            self._init_ville_quartiers()
            
            logger.info(f"Données chargées avec succès: {len(self.df)} appartements")
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement des données: {str(e)}")
            raise

    def _preprocess_data(self):
        # Conversion des prix en float
        self.df['prix'] = pd.to_numeric(self.df['prix'], errors='coerce')
        self.df = self.df[self.df['prix'] > 0]
        
        # Conversion du nombre de chambres
        self.df['nb_chambres'] = pd.to_numeric(self.df['nb_chambres'], errors='coerce')
        
        # Normalisation des chaînes
        self.df['ville'] = self.df['ville'].str.strip().str.title()
        self.df['quartier'] = self.df['quartier'].str.strip().str.title()
        
        # Préparation des prix formatés
        self.df['prix_display'] = self.df['prix'].apply(Formatter.price)
        
        # Gestion de la popularité
        if 'vues' in self.df.columns:
            self.df['popularite'] = pd.to_numeric(self.df['vues'], errors='coerce').fillna(0)
        else:
            self.df['popularite'] = 50

    def get_recommendations(self, request: RecommendationRequest, limit: int = 6) -> Dict:
        try:
            mask = (
                (self.df['ville'].str.lower() == request.location.ville.lower()) &
                (self.df['prix'] <= request.tranche_salariale.max_rent) &
                (self.df['nb_chambres'] >= max(1, (request.nb_personnes + 1) // 2))
            )
            
            filtered_df = self.df[mask].copy()
            
            if len(filtered_df) == 0:
                return self._build_empty_response(request, "Aucune offre ne correspond à vos critères")
            
            stats = self.get_stats(request.location.ville)
            filtered_df['score'] = filtered_df.apply(
                lambda x: self.scorer.calculate_score(x, request, stats),
                axis=1
            )
            
            search_quartier = request.location.quartier.lower()
            quartier_exact = filtered_df[
                filtered_df['quartier'].str.lower().apply(lambda x: 
                    x == search_quartier or
                    x.startswith(search_quartier) or
                    search_quartier.startswith(x) or
                    bool(get_close_matches(search_quartier, [x], n=1, cutoff=0.8))
                )
            ]

            if len(quartier_exact) == 0:
                best_matches = filtered_df.nlargest(limit, 'score')
                message = (
                    f"Aucune offre disponible dans le quartier {request.location.quartier}. "
                    f"Voici {len(best_matches)} suggestions dans d'autres quartiers de {request.location.ville}"
                )
            else:
                best_matches = quartier_exact.nlargest(limit, 'score')
                message = f"Trouvé {len(best_matches)} offre(s) dans {request.location.quartier}"

            results = []
            for _, apt in best_matches.iterrows():
                formatted_apt = self.format_apartment(apt, request, stats)
                results.append(formatted_apt)

            return {
                'status': 'success',
                'message': message,
                'recommendations': results,
                'summary': {
                    'ville': request.location.ville,
                    'quartier': request.location.quartier,
                    'budget_max': (
                        "Illimité" if request.tranche_salariale.max_rent == float('inf')
                        else Formatter.price(request.tranche_salariale.max_rent)
                    ),
                    'nb_personnes': request.nb_personnes,
                    'chambres_min': max(1, (request.nb_personnes + 1) // 2),
                    'total_results': len(filtered_df),
                    'stats': {
                        'prix_moyen': Formatter.price(stats.avg_price),
                        'prix_median': Formatter.price(stats.median_price),
                        'nb_total': stats.count
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche: {str(e)}")
            return self._build_empty_response(request, f"Une erreur est survenue: {str(e)}")

    def format_apartment(self, apt: pd.Series, request: RecommendationRequest,
                        stats: ApartmentStats) -> dict:
        score = self.scorer.calculate_score(apt, request, stats)
        
        strong_points = []
        attention_points = []
        
        if apt['prix'] <= request.tranche_salariale.max_rent * 0.7:
            strong_points.append("Prix très avantageux (30% sous budget)")
        elif apt['prix'] > request.tranche_salariale.max_rent * 0.9:
            attention_points.append("Prix proche du budget maximum")

        if apt['popularite'] > stats.avg_popularity * 1.5:
            strong_points.append("Très recherché")
            if apt['popularite'] > stats.avg_popularity * 2:
                attention_points.append("Forte demande - Décision rapide conseillée")

        return {
            'id': str(apt.get('_id', '')),
            'titre': apt['titre'],
            'prix': Formatter.price(apt['prix']),
            'prix_raw': float(apt['prix']),
            'quartier': f"{apt['quartier']}, {apt['ville']}",
            'nb_chambres': Formatter.rooms(apt['nb_chambres']),
            'popularite': Formatter.views(apt['popularite']),
            'score': Formatter.percentage(score * 100),
            'points_forts': strong_points,
            'points_attention': attention_points
        }

    def _build_empty_response(self, request: RecommendationRequest, message: str) -> Dict:
        return {
            'status': 'error',
            'message': message,
            'recommendations': [],
            'summary': {
                'ville': request.location.ville,
                'quartier': request.location.quartier,
                'budget_max': (
                    "Illimité" if request.tranche_salariale.max_rent == float('inf')
                    else Formatter.price(request.tranche_salariale.max_rent)
                ),
                'nb_personnes': request.nb_personnes,
                'chambres_min': max(1, (request.nb_personnes + 1) // 2),
                'total_results': 0,
                'stats': {
                    'prix_moyen': "0 FCFA",
                    'prix_median': "0 FCFA",
                    'nb_total': 0
                }
            }
        }

    def get_stats(self, ville: Optional[str] = None) -> ApartmentStats:
        try:
            df = self.df if ville is None else self.df[
                self.df['ville'].str.lower() == ville.lower()
            ]
            
            if len(df) == 0:
                return ApartmentStats(0, 0, 0, 0, 0, 0, 0)
            
            return ApartmentStats(
                avg_price=df['prix'].mean(),
                median_price=df['prix'].median(),
                min_price=df['prix'].min(),
                max_price=df['prix'].max(),
                avg_popularity=df['popularite'].mean(),
                max_popularity=df['popularite'].max(),
                count=len(df)
            )
        except Exception as e:
            logger.error(f"Erreur lors du calcul des statistiques: {str(e)}")
            return ApartmentStats(0, 0, 0, 0, 0, 0, 0)

    def _init_ville_quartiers(self):
        self.ville_quartiers = {}
        for ville in self.df['ville'].unique():
            quartiers = self.df[self.df['ville'] == ville]['quartier'].unique()
            self.ville_quartiers[ville] = set(quartiers)

    @lru_cache(maxsize=128)
    def verify_ville_quartier(self, ville: str, quartier: str) -> bool:
        ville_lower = ville.lower()
        quartier_lower = quartier.lower()
        
        if ville_lower not in {v.lower() for v in self.ville_quartiers.keys()}:
            return False
            
        quartiers = {q.lower() for q in self.ville_quartiers[ville]}
        return (
            quartier_lower in quartiers or
            any(q.startswith(quartier_lower) or quartier_lower.startswith(q) 
                for q in quartiers) or
            bool(get_close_matches(quartier_lower, quartiers, n=1, cutoff=0.8))
        )
    
    