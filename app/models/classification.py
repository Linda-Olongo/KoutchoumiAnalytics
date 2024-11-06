"""
Classification des appartements à Yaoundé et Douala.

Ce module permet de classifier les appartements en trois catégories
(Low Cost, Moyen, Luxueux) en se basant sur les prix et le nombre
de chambres. La classification est unifiée pour les deux villes.

Distribution typique obtenue :
- Low Cost  : ~35-40% des appartements
- Moyen     : ~45-50% des appartements
- Luxueux   : ~15-20% des appartements

Caractéristiques moyennes par catégorie :
- Low Cost  : ~250k FCFA, 2 chambres
- Moyen     : ~700k FCFA, 2-3 chambres
- Luxueux   : ~1.8M FCFA, 3+ chambres
"""

try:
    from ..database.db_config import DatabaseConnection
except ImportError:
    from app.database.db_config import DatabaseConnection

import pandas as pd

class ApartmentClassifier:
    def __init__(self):
        self.db = DatabaseConnection()
    
    def get_apartments_data(self):
        """Récupère les données des appartements depuis MongoDB"""
        try:
            # Pipeline d'agrégation MongoDB pour obtenir les champs nécessaires
            pipeline = [
                {
                    "$match": {
                        "prix": {"$exists": True, "$ne": None},
                        "nb_chambres": {"$exists": True, "$ne": None},
                        "popularite": {"$exists": True, "$ne": None}
                    }
                },
                {
                    "$project": {
                        "_id": 1,
                        "titre": 1,
                        "prix": 1,
                        "nb_chambres": 1,
                        "quartier": 1,
                        "ville": 1,
                        "popularite": 1
                    }
                }
            ]
            
            return list(self.db.db.apartments.aggregate(pipeline))
        except Exception as e:
            print(f"Erreur lors de la récupération des données: {e}")
            return []
    
    def get_category(self, row):
        """
        Détermine la catégorie d'un appartement.
        
        Règles de classification :
        - Low Cost  : ≤ 350k FCFA
        - Moyen     : Entre 350k et 1.5M FCFA
        - Luxueux   : ≥ 1.5M FCFA ou ≥ 1M FCFA avec ≥ 4 chambres
        
        Args:
            row (pd.Series): Ligne de données contenant prix et nb_chambres
            
        Returns:
            str: Catégorie de l'appartement ('Low Cost', 'Moyen', ou 'Luxueux')
        """
        prix = float(row['prix'])
        chambres = float(row['nb_chambres'])
        
        if prix <= 350000:
            return "Low Cost"
        elif prix >= 1500000 or (prix >= 1000000 and chambres >= 4):
            return "Luxueux"
        else:
            return "Moyen"
    
    def classify_apartments(self):
        """Classifie les appartements et retourne les résultats"""
        data = self.get_apartments_data()
        if not data:
            print("Aucune donnée trouvée dans la base de données")
            return None
        
        # Convertir les données MongoDB en DataFrame
        df = pd.DataFrame(data)
        df['categorie'] = df.apply(self.get_category, axis=1)
        
        self.display_results(df)
        return df
    
    def display_results(self, df):
        """Affiche les résultats détaillés de la classification"""
        print("\n=== CLASSIFICATION DES APPARTEMENTS ===")
        print("\nCritères de classification:")
        print("- Low Cost  : ≤ 350k FCFA")
        print("- Moyen     : Entre 350k et 1.5M FCFA")
        print("- Luxueux   : ≥ 1.5M FCFA ou ≥ 1M FCFA avec ≥ 4 chambres")
        print(f"\nNombre total d'appartements : {len(df)}\n")
        
        for category in ['Low Cost', 'Moyen', 'Luxueux']:
            category_df = df[df['categorie'] == category]
            count = len(category_df)
            if count == 0:
                continue
                
            percentage = (count / len(df)) * 100
            print(f"{category.upper()} ({count} appartements - {percentage:.1f}%)")
            print("-" * 80)
            
            top_5 = category_df.nlargest(5, 'popularite')
            
            for _, apt in top_5.iterrows():
                print(f"Titre    : {apt['titre']}")
                print(f"Prix     : {apt['prix']:,} FCFA")
                print(f"Quartier : {apt['quartier']}, {apt['ville']}")
                print(f"Vue      : {apt['popularite']} vues")
                print("- " * 20)
            
            print(f"\nStatistiques de la catégorie {category}:")
            print(f"Prix moyen     : {category_df['prix'].mean():,.0f} FCFA")
            print(f"Prix médian    : {category_df['prix'].median():,.0f} FCFA")
            print(f"Chambres moy.  : {category_df['nb_chambres'].mean():.1f}")
            print(f"Popularité moy.: {category_df['popularite'].mean():.1f} vues")
            print("=" * 80 + "\n")
    
    def get_recommendations(self, ville, salaire, quartier=None, nb_personnes=1):
        """
        Recommande des appartements basés sur les critères de l'utilisateur
        """
        try:
            # Calculer le budget maximum (30% du salaire)
            budget_max = salaire * 0.3
            
            # Calculer le nombre minimum de chambres nécessaire
            min_chambres = (nb_personnes + 1) // 2  # 2 personnes max par chambre
            
            # Construire le filtre MongoDB
            filter_query = {
                "ville": ville,
                "prix": {"$lte": budget_max},
                "nb_chambres": {"$gte": min_chambres}
            }
            
            if quartier:
                filter_query["quartier"] = quartier
            
            # Récupérer les recommandations
            recommendations = list(self.db.db.apartments.find(
                filter_query
            ).sort("popularite", -1).limit(5))
            
            return recommendations
            
        except Exception as e:
            print(f"Erreur lors de la recherche de recommandations: {e}")
            return []

if __name__ == "__main__":
    classifier = ApartmentClassifier()
    classifier.classify_apartments()