import requests
from bs4 import BeautifulSoup
import re
import time
import logging
from typing import Optional, Dict, Any
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime
from app.database.db_config import DatabaseConnection

class KoutchoumiScraper:
    def __init__(self):
        """Initialise le scraper avec les configurations nécessaires"""
        self.base_urls = {
            'Yaoundé': "https://koutchoumi.com/appartements-a-louer-a-yaounde-cameroun.html",
            'Douala': "https://koutchoumi.com/appartements-a-louer-a-douala-cameroun.html"
        }
        self.db = DatabaseConnection()
        self.session = self._init_session()
        
        # Configuration du logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
    def _init_session(self) -> requests.Session:
        """Initialise une session HTTP avec retry et timeout"""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7'
        })
        return session

    def determiner_categorie(self, prix: int) -> str:
        """Détermine la catégorie de l'appartement en fonction du prix"""
        if prix < 100000:
            return "Low Cost"
        elif prix < 300000:
            return "Moyen"
        else:
            return "Luxueux"

    def extract_apartment_info(self, card, ville: str) -> Optional[Dict[str, Any]]:
        """Extrait les informations d'un appartement depuis une carte"""
        try:
            # Extraction du prix
            price_element = card.find('h2', class_='text-primary')
            if not price_element:
                return None

            prix_text = price_element.get_text(strip=True)
            prix_match = re.search(r'(\d+[\s\d]*)\s*F', prix_text)
            prix = int(prix_match.group(1).replace(' ', '')) if prix_match else 0

            # Extraction du quartier
            quartier_match = re.search(r'\|\s*(.*?),', prix_text)
            quartier = quartier_match.group(1).strip() if quartier_match else ''

            # Extraction du nombre de chambres
            description = card.find('h3', class_='card-title')
            if not description:
                return None

            description_text = description.get_text(strip=True)
            chambres_match = re.search(r'(\d+)\s*chambre', description_text.lower())
            nb_chambres = int(chambres_match.group(1)) if chambres_match else 0

            # Extraction de l'URL
            url_element = card.find('a', href=True)
            url = url_element['href'] if url_element else ''
            if url and not url.startswith('http'):
                url = f"https://koutchoumi.com{url}"

            # Extraction de la popularité
            popularite = 0
            views_span = card.find_all('span')
            for span in views_span:
                if 'vues' in span.text.lower():
                    views_match = re.search(r'(\d+)\s*vues', span.text)
                    popularite = int(views_match.group(1)) if views_match else 0
                    break

            return {
                'titre': f"{prix} F | {quartier}, {ville}",
                'ville': ville,
                'quartier': quartier,
                'prix': prix,
                'nb_chambres': nb_chambres,
                'description': description_text,
                'popularite': popularite,
                'url_annonce': url,
                'categorie': self.determiner_categorie(prix),
                'date_ajout': datetime.now(),
                'derniere_maj': datetime.now()
            }

        except Exception as e:
            self.logger.error(f"Erreur lors de l'extraction des données : {str(e)}")
            return None

    def scrape_page(self, url: str, ville: str) -> Optional[str]:
        """Scrape une page et retourne l'URL de la page suivante"""
        try:
            self.logger.info(f"Scraping de l'URL : {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            apartment_cards = soup.find_all('div', class_='card card-list')
            
            for card in apartment_cards:
                data = self.extract_apartment_info(card, ville)
                if data:
                    # Vérification de l'existence
                    existing = self.db.db.apartments.find_one({"url_annonce": data['url_annonce']})
                    
                    if not existing:
                        self.db.save_apartment(data)
                        self.logger.info(f"✅ Nouvel appartement ajouté: {data['titre'][:50]}...")
                    else:
                        # Mise à jour
                        self.db.db.apartments.update_one(
                            {"url_annonce": data['url_annonce']},
                            {"$set": {
                                "prix": data['prix'],
                                "popularite": data['popularite'],
                                "description": data['description'],
                                "derniere_maj": datetime.now()
                            }}
                        )
                        self.logger.info(f"🔄 Appartement mis à jour: {data['titre'][:50]}...")

            # Recherche de la page suivante
            next_page = None
            pagination = soup.find('ul', class_='pagination')
            if pagination:
                current_page = pagination.find('li', class_='active')
                if current_page:
                    next_li = current_page.find_next_sibling('li')
                    if next_li and next_li.find('a'):
                        next_url = next_li.find('a')['href']
                        if not next_url.startswith('http'):
                            next_page = f"https://koutchoumi.com{next_url}"

            time.sleep(2)  # Délai pour éviter la surcharge
            return next_page

        except Exception as e:
            self.logger.error(f"Erreur lors du scraping de la page : {str(e)}")
            return None

    def scrape_city(self, ville: str):
        """Scrape tous les appartements d'une ville"""
        if ville not in self.base_urls:
            self.logger.error(f"❌ URL non trouvée pour {ville}")
            return

        self.logger.info(f"Début du scraping pour {ville}")
        current_url = self.base_urls[ville]
        page_number = 1

        while current_url:
            self.logger.info(f"📄 Page {page_number} de {ville}")
            next_url = self.scrape_page(current_url, ville)
            
            if not next_url:
                break

            current_url = next_url
            page_number += 1
            
            # Comptage
            count = self.db.db.apartments.count_documents({"ville": ville})
            self.logger.info(f"Total d'appartements pour {ville} : {count}")

        self.logger.info(f"Scraping terminé pour {ville}!")

    def run(self):
        """Lance le scraping pour toutes les villes"""
        self.logger.info("Début du scraping")
        for ville in self.base_urls.keys():
            self.scrape_city(ville)
            time.sleep(5)  # Pause entre les villes
        self.logger.info("Scraping terminé!")

if __name__ == "__main__":
    scraper = KoutchoumiScraper()
    scraper.run()