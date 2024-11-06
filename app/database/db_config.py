from pymongo import MongoClient
import logging
import atexit
import ssl
import os

class DatabaseConnection:
    def __init__(self):
        # Récupération de l'URI depuis les variables d'environnement
        self.connection_string = os.environ.get('MONGODB_URI')
        
        if not self.connection_string:
            raise ValueError("MONGODB_URI n'est pas définie dans les variables d'environnement")
        
        # Configuration du logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
        self.logger = logging.getLogger(__name__)
        
        try:
            self.client = MongoClient(
                self.connection_string,
                serverSelectionTimeoutMS=30000,
                connectTimeoutMS=30000,
                retryWrites=True
            )
            # Tester la connexion
            self.client.admin.command('ping')
            self.db = self.client.koutchoumi_db
            self.logger.info("Connexion à MongoDB établie avec succès")
            atexit.register(self.cleanup)
        except Exception as e:
            self.logger.error(f"Erreur de connexion à MongoDB : {e}")
            raise

    def cleanup(self):
        """Ferme proprement la connexion"""
        try:
            if hasattr(self, 'client'):
                self.client.close()
                self.logger.info("Connexion MongoDB fermée avec succès")
        except Exception as e:
            self.logger.error(f"Erreur lors de la fermeture : {e}")

    def save_apartment(self, apartment_data):
        """Sauvegarde un appartement dans la collection"""
        try:
            result = self.db.apartments.insert_one(apartment_data)
            return str(result.inserted_id)
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde : {e}")
            return None

    def get_all_apartments(self):
        """Récupère tous les appartements"""
        try:
            return list(self.db.apartments.find())
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération : {e}")
            return []

    def get_apartments_by_city(self, city):
        """Récupère les appartements par ville"""
        try:
            return list(self.db.apartments.find({"ville": city}))
        except Exception as e:
            self.logger.error(f"Erreur lors de la recherche par ville : {e}")
            return []
    
    def get_apartments_by_criteria(self, criteria):
        """Récupère les appartements selon des critères spécifiques"""
        try:
            return list(self.db.apartments.find(criteria))
        except Exception as e:
            self.logger.error(f"Erreur lors de la recherche avec critères : {e}")
            return []

    def update_apartment(self, apartment_id, update_data):
        """Met à jour un appartement"""
        try:
            result = self.db.apartments.update_one(
                {"_id": apartment_id},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            self.logger.error(f"Erreur lors de la mise à jour : {e}")
            return False

    def delete_apartment(self, apartment_id):
        """Supprime un appartement"""
        try:
            result = self.db.apartments.delete_one({"_id": apartment_id})
            return result.deleted_count > 0
        except Exception as e:
            self.logger.error(f"Erreur lors de la suppression : {e}")
            return False

    def get_distinct_values(self, field):
        """Récupère les valeurs distinctes pour un champ donné"""
        try:
            return list(self.db.apartments.distinct(field))
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des valeurs distinctes : {e}")
            return []

    def count_apartments(self, criteria=None):
        """Compte le nombre d'appartements selon des critères optionnels"""
        try:
            return self.db.apartments.count_documents(criteria or {})
        except Exception as e:
            self.logger.error(f"Erreur lors du comptage : {e}")
            return 0

    def get_price_range(self):
        """Récupère la plage de prix des appartements"""
        try:
            result = list(self.db.apartments.aggregate([
                {
                    "$group": {
                        "_id": None,
                        "min_price": {"$min": "$prix"},
                        "max_price": {"$max": "$prix"}
                    }
                }
            ]))
            if result:
                return result[0]["min_price"], result[0]["max_price"]
            return None, None
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération de la plage de prix : {e}")
            return None, None

# Test de la connexion si ce fichier est exécuté directement
if __name__ == "__main__":
    try:
        db = DatabaseConnection()
        print("✅ Connexion à MongoDB réussie")
        print("✅ Base de données prête pour le scraping")
    except Exception as e:
        print(f"❌ Échec de la connexion : {e}")