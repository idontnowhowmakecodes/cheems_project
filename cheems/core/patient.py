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
        """Valida que la edad esté dentro del rango permitido para el examen STAT (1 a 3 años / 12 a 36 meses)."""
        if not (12 <= self.age_months <= 36):
            raise ValueError(
                f"La edad del paciente ({self.age_months} meses) está fuera del rango válido "
                f"para la evaluación STAT (12 a 36 meses / 1 a 3 años)."
            )

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
