"""Modelo de Paciente para el sistema CHEEMS."""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Patient:
    """Representa a un paciente toddler a ser evaluado (Rango de edad: 12 a 36 meses / 1 a 3 años)."""

    patient_id: str
    full_name: str
    age_months: int
    birth_date: Optional[date] = None
    sex: str = "Unspecified"
    evaluator: str = "Especialista CHEEMS"
    notes: str = ""
    created_at: date = field(default_factory=date.today)

    def __post_init__(self) -> None:
        """Valida la edad general."""
        if self.age_months < 1:
            raise ValueError("La edad debe ser al menos 1 mes.")

    def validate_for_test(self, test_type: str) -> tuple[bool, str]:
        """Validación dinámica según el test seleccionado."""
        if test_type == "stat" and not (12 <= self.age_months <= 36):
            return False, f"STAT: edad {self.age_months}m fuera de rango (12-36m)."
        if test_type == "ados2" and self.age_months < 12:
            return False, f"ADOS-2: edad {self.age_months}m menor al mínimo (12m)."
        return True, "Edad válida."

    @property
    def age_years(self) -> float:
        """Devuelve la edad calculada en años."""
        return round(self.age_months / 12.0, 1)

    def to_dict(self) -> dict:
        """Convierte los datos del paciente a un diccionario serializable."""
        return {
            "patient_id": self.patient_id,
            "full_name": self.full_name,
            "age_months": self.age_months,
            "age_years": self.age_years,
            "birth_date": self.birth_date.isoformat() if self.birth_date else None,
            "sex": self.sex,
            "evaluator": self.evaluator,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
        }
