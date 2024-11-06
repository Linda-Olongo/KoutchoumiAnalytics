# app/models/enums.py

from enum import Enum
from typing import List, Dict, Any

class SalaryRange(Enum):
    """Tranches salariales adaptées au contexte camerounais"""
    VERY_LOW = (50_000, 100_000, "Très Bas", 0.30)  # Loyer max: 30,000
    LOW = (100_000, 200_000, "Bas", 0.35)  # Loyer max: 70,000
    MEDIUM_LOW = (200_000, 400_000, "Moyen Bas", 0.35)  # Loyer max: 140,000
    MEDIUM = (400_000, 800_000, "Moyen", 0.35)  # Loyer max: 280,000
    MEDIUM_HIGH = (800_000, 1_500_000, "Moyen Haut", 0.40)  # Loyer max: 600,000
    HIGH = (1_500_000, 3_000_000, "Haut", 0.40)  # Loyer max: 1,200,000
    VERY_HIGH = (3_000_000, float('inf'), "Très Haut", 0.45)  # Loyer max: >1,350,000

    @property
    def min_salary(self) -> float:
        return self.value[0]
    
    @property
    def max_salary(self) -> float:
        return self.value[1]
    
    @property
    def label(self) -> str:
        return self.value[2]
    
    @property
    def rent_ratio(self) -> float:
        return self.value[3]
    
    @property
    def max_rent(self) -> float:
        if self.max_salary == float('inf'):
            return float('inf')
        return self.max_salary * self.rent_ratio

    @classmethod
    def get_range_for_salary(cls, salary: float) -> 'SalaryRange':
        for range_type in cls:
            if range_type.min_salary <= salary < range_type.max_salary:
                return range_type
        return cls.VERY_HIGH

    @classmethod
    def get_all_ranges(cls) -> List[Dict[str, Any]]:
        ranges = []
        for salary_range in cls:
            max_rent = (
                f"> {int(salary_range.min_salary * salary_range.rent_ratio):,} FCFA" 
                if salary_range.max_salary == float('inf')
                else f"{int(salary_range.max_salary * salary_range.rent_ratio):,} FCFA"
            )
            
            ranges.append({
                'id': salary_range.name,
                'label': salary_range.label,
                'min_salary': f"{int(salary_range.min_salary):,} FCFA",
                'max_salary': (
                    f"> {int(salary_range.min_salary):,} FCFA"
                    if salary_range.max_salary == float('inf')
                    else f"{int(salary_range.max_salary):,} FCFA"
                ),
                'max_rent': max_rent
            })
        return ranges

class PropertyCategory(Enum):
    """Catégories de biens adaptées au marché camerounais"""
    SOCIAL = ("Social", 0, 50_000)
    ECONOMIQUE = ("Économique", 50_000, 150_000)
    MOYEN = ("Moyen", 150_000, 400_000)
    STANDING = ("Standing", 400_000, 1_000_000)
    HAUT_STANDING = ("Haut Standing", 1_000_000, float('inf'))

    @property
    def label(self) -> str:
        return self.value[0]
    
    @property
    def min_price(self) -> float:
        return self.value[1]
    
    @property
    def max_price(self) -> float:
        return self.value[2]

    @classmethod
    def categorize(cls, price: float) -> 'PropertyCategory':
        for category in cls:
            if category.min_price <= price < category.max_price:
                return category
        return cls.HAUT_STANDING