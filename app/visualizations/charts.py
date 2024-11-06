import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
import os
from app.database.db_config import DatabaseConnection
from typing import Dict, Optional, List, Any
import logging
import unicodedata

class AppartementVisualizer:
    def __init__(self):
        """Initialise le visualiseur avec logging"""
        self.logger = logging.getLogger(__name__)
        self.image_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "images")
        os.makedirs(self.image_dir, exist_ok=True)
        self.db = DatabaseConnection()

    def cleanup_images(self):
        """Nettoie les anciennes images"""
        try:
            for filename in os.listdir(self.image_dir):
                if filename.startswith(('distribution_chambres_', 'top_appartements_')):
                    file_path = os.path.join(self.image_dir, filename)
                    os.remove(file_path)
        except Exception as e:
            self.logger.error(f"Erreur lors du nettoyage des images: {str(e)}")
    
    def _normalize_ville(self, ville: Optional[str]) -> str:
        """Normalise le nom de la ville pour les noms de fichiers"""
        if not ville:
            return "all"
        # Convertit les accents et normalise
        normalized = unicodedata.normalize('NFKD', ville).encode('ASCII', 'ignore').decode('ASCII')
        return normalized.lower()

    def get_stats_globales(self, ville: Optional[str] = None) -> Dict[str, Any]:
        """Récupère uniquement les statistiques essentielles : total appartements, quartiers et prix moyen"""
        try:
            # Construire le filtre MongoDB
            match_filter = {"prix": {"$gt": 0}}
            if ville:
                match_filter["ville"] = ville

            pipeline = [
                {"$match": match_filter},
                {"$group": {
                    "_id": None,
                    "total": {"$sum": 1},
                    "total_quartiers": {"$addToSet": "$quartier"},
                    "prix_moyen": {"$avg": "$prix"}
                }}
            ]

            result = list(self.db.db.apartments.aggregate(pipeline))

            if not result:
                return {}

            prix_moyen = f"{int(result[0]['prix_moyen']):,} FCFA"

            return {
                'total_appartements': result[0]['total'],
                'quartiers_couverts': len(result[0]['total_quartiers']),
                'prix_moyen': prix_moyen
            }

        except Exception as e:
            self.logger.error(f"Erreur lors de la génération des statistiques: {str(e)}")
            return {}

    def plot_distribution_chambres(self, ville: Optional[str] = None) -> str:
        """Génère le graphique de distribution des chambres"""
        try:
            # Construire le filtre MongoDB
            match_filter = {"prix": {"$gt": 0}, "nb_chambres": {"$ne": None}}
            if ville:
                match_filter["ville"] = ville

            pipeline = [
                {"$match": match_filter},
                {"$group": {
                    "_id": "$nb_chambres",
                    "count": {"$sum": 1},
                    "prix_moyen": {"$avg": "$prix"}
                }},
                {"$sort": {"_id": 1}}
            ]

            data = list(self.db.db.apartments.aggregate(pipeline))

            if not data:
                self.logger.warning("Aucune donnée trouvée pour la distribution des chambres")
                return ""

            plt.style.use('seaborn-v0_8-whitegrid')
            plt.rcParams['axes.grid'] = False

            plt.figure(figsize=(12, 6))

            nb_chambres = [d['_id'] for d in data]
            counts = [d['count'] for d in data]

            bars = plt.bar(nb_chambres, counts, color='#4169E1', alpha=0.7)

            plt.title(f"Distribution des Appartements par Nombre de Chambres{' à ' + ville if ville else ''}")
            plt.xlabel("Nombre de Chambres")
            plt.ylabel("Nombre d'Appartements")

            for bar in bars:
                height = bar.get_height()
                plt.text(bar.get_x() + bar.get_width()/2, height,
                        f'{int(height):,}',
                        ha='center', va='bottom')

            plt.xticks(nb_chambres)

            plt.gca().spines['top'].set_visible(False)
            plt.gca().spines['right'].set_visible(False)

            filename = f"distribution_chambres_{self._normalize_ville(ville)}.png"  # Correction du préfixe
            filepath = os.path.join(self.image_dir, filename)
            plt.savefig(filepath, bbox_inches='tight', dpi=300)
            plt.close()

            return filepath

        except Exception as e:
            self.logger.error(f"Erreur lors de la génération du graphique: {str(e)}")
            return ""

    def plot_top_appartements(self, ville: Optional[str] = None, limit: int = 5) -> str:
        """Génère le graphique des appartements les plus populaires"""
        try:
            # Construire le filtre MongoDB
            match_filter = {"prix": {"$gt": 0}}
            if ville:
                match_filter["ville"] = ville

            pipeline = [
                {"$match": match_filter},
                {"$sort": {"popularite": -1, "prix": 1}},
                {"$limit": limit},
                {"$project": {
                    "titre": 1,
                    "quartier": 1,
                    "prix": 1,
                    "popularite": 1,
                    "nb_chambres": 1
                }}
            ]

            data = list(self.db.db.apartments.aggregate(pipeline))

            if not data:
                self.logger.warning("Aucune donnée trouvée pour les tops appartements")
                return ""

            plt.style.use('seaborn-v0_8-whitegrid')
            plt.rcParams['axes.grid'] = False

            plt.figure(figsize=(14, 8))

            titres = [f"{d['prix']:,} FCFA | {d['quartier']} ({d['nb_chambres']} ch)" for d in data][::-1]
            popularite = [d['popularite'] for d in data][::-1]

            colors = plt.cm.viridis(np.linspace(0, 0.8, len(data)))
            bars = plt.barh(titres, popularite, color=colors, alpha=0.7)

            plt.title(f"Top {limit} Appartements les Plus Consultés{' à ' + ville if ville else ''}", 
                    pad=20, fontsize=12, fontweight='bold')
            plt.xlabel("Nombre de Vues", fontsize=10)

            for bar in bars:
                x_val = bar.get_width()
                y_val = bar.get_y() + bar.get_height()/2
                plt.text(x_val + (max(popularite) * 0.02),
                        y_val,
                        f'{int(x_val):,}',
                        va='center',
                        ha='left',
                        fontsize=9)

            plt.subplots_adjust(left=0.3)
            plt.margins(x=0.2)

            plt.gca().spines['top'].set_visible(False)
            plt.gca().spines['right'].set_visible(False)

            filename = f"top_appartements_{self._normalize_ville(ville)}.png"  # Utilisation de la normalisation améliorée
            filepath = os.path.join(self.image_dir, filename)
            plt.savefig(filepath, bbox_inches='tight', dpi=300)
            plt.close()

            return filepath

        except Exception as e:
            self.logger.error(f"Erreur lors de la génération du graphique: {str(e)}")
            return ""

if __name__ == "__main__":
    # Configuration du logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    visualizer = AppartementVisualizer()
    visualizer.cleanup_images()
    
    # Test des fonctionnalités
    for ville in [None, 'Yaoundé', 'Douala']:
        ville_name = ville if ville else "toutes les villes"
        print(f"\nGénération des visualisations pour {ville_name}")
        
        # Statistiques
        stats = visualizer.get_stats_globales(ville)
        print(f"\nStatistiques pour {ville_name}:")
        print(stats)
        
        # Graphiques
        dist_path = visualizer.plot_distribution_chambres(ville)
        top_path = visualizer.plot_top_appartements(ville)
        
        if dist_path:
            print(f"Graphique de distribution sauvegardé: {dist_path}")
        if top_path:
            print(f"Graphique des tops appartements sauvegardé: {top_path}")