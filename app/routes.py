from flask import Blueprint, render_template, redirect, url_for, request
from app.visualizations.charts import AppartementVisualizer
from app.models.enums import SalaryRange, PropertyCategory
from app.models.recommendation import ApartmentRecommender
from app.models.classification import ApartmentClassifier
from app.database.db_config import DatabaseConnection
from dataclasses import dataclass

main_bp = Blueprint('main', __name__)
visualizer = AppartementVisualizer()

@dataclass
class Location:
    ville: str
    quartier: str

@dataclass
class RecommendationRequest:
    location: Location
    tranche_salariale: SalaryRange
    nb_personnes: int

@main_bp.route('/')
@main_bp.route('/dashboard')
def index():
    """Page d'accueil - Vue globale"""
    stats = visualizer.get_stats_globales()
    visualizer.plot_distribution_chambres()
    visualizer.plot_top_appartements()
    
    return render_template('dashboard.html', 
                         stats=stats,
                         active_city='all',
                         active_page='dashboard',
                         page_title='Aperçu Global')

@main_bp.route('/ville/<ville>')
def ville_stats(ville):
    """Statistiques par ville"""
    try:
        if ville.lower() not in ['yaounde', 'douala']:
            return redirect(url_for('main.index'))
        
        # Convertir 'Yaounde' en 'Yaoundé' pour la requête MongoDB
        ville_db = 'Yaoundé' if ville.lower() == 'yaounde' else ville
        
        stats = visualizer.get_stats_globales(ville_db)
        visualizer.plot_distribution_chambres(ville_db)
        visualizer.plot_top_appartements(ville_db)
        
        return render_template('dashboard.html',
                             stats=stats,
                             active_city=ville.lower(),
                             active_page='dashboard',
                             page_title=f'Statistiques - {ville_db}')
    except Exception as e:
        print(f"Erreur: {str(e)}")
        return redirect(url_for('main.index'))



@main_bp.route('/data', methods=['GET', 'POST'])
def data():
    """Page des données, recommandations et classification"""
    
    # Instance du classificateur (toujours chargé pour GET et POST)
    classifier = ApartmentClassifier()
    df_classification = classifier.classify_apartments()
    classification_results = df_classification.to_dict('records') if df_classification is not None else None
    
    # Pour une requête GET, afficher uniquement le formulaire
    if request.method == 'GET':
        return render_template('data.html', 
                         active_page='data',
                         active_tab='recommendation',
                         page_title='Données',
                         recommendations=None,
                         classification_results=classification_results)
    
    # Pour une requête POST (soumission du formulaire)
    recommendations = None
    active_tab = 'recommendation'  # Forcer l'onglet recommandation pour voir les résultats
    
    try:
        # Récupération des données du formulaire
        city = request.form.get('city')
        location = request.form.get('location')
        salary_range = request.form.get('salary_range')
        num_occupants = request.form.get('num_occupants')
        
        print(f"Données reçues: ville={city}, quartier={location}, "
              f"salaire={salary_range}, occupants={num_occupants}")
        
        if not all([city, location, salary_range, num_occupants]):
            raise ValueError("Tous les champs sont requis")
        
        # Conversion de la tranche salariale
        salary_ranges = {
            '50.000 - 150.000 FCFA': SalaryRange.LOW,
            '150.000 - 300.000 FCFA': SalaryRange.MEDIUM_LOW,
            '300.000 - 500.000 FCFA': SalaryRange.MEDIUM,
            '500.000 - 800.000 FCFA': SalaryRange.MEDIUM_HIGH,
            '800.000 - 1.500.000 FCFA': SalaryRange.HIGH,
            'Plus de 1.500.000 FCFA': SalaryRange.VERY_HIGH
        }
        
        tranche = salary_ranges.get(salary_range)
        if not tranche:
            print(f"Tranche salariale invalide: {salary_range}")
            raise ValueError(f"Tranche salariale non reconnue: {salary_range}")
        
        # Création de la requête
        request_obj = RecommendationRequest(
            location=Location(ville=city, quartier=location),
            tranche_salariale=tranche,
            nb_personnes=int(num_occupants)
        )
        
        # Initialisation du recommender avec la connexion DB
        db = DatabaseConnection()
        recommender = ApartmentRecommender(db)
        
        # Obtention des recommandations
        recommendations = recommender.get_recommendations(request_obj)
        print(f"Recommandations obtenues: {recommendations}")
        
    except ValueError as e:
        print(f"Erreur de validation: {str(e)}")
        recommendations = {
            'status': 'error',
            'message': str(e),
            'recommendations': []
        }
    except Exception as e:
        print(f"Erreur inattendue: {str(e)}")
        recommendations = {
            'status': 'error',
            'message': "Une erreur inattendue s'est produite",
            'recommendations': []
        }
    
    return render_template('data.html', 
                     active_page='data',
                     active_tab=active_tab,
                     page_title='Données',
                     recommendations=recommendations,
                     classification_results=classification_results)


@main_bp.route('/about')
def about():
    """Page À propos"""
    return render_template('about.html', 
                         active_page='about',
                         page_title='À Propos')