"""Pruebas unitarias para el módulo de seguridad y cifrado médico en CHEEMS."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from cheems.database.sqlite_repository import SessionRepository
from cheems.security.crypto import MedicalDataCryptor
from cheems.utils.exporters import anonymize_session_data


class TestMedicalSecurity(unittest.TestCase):
    """Verificación de seguridad criptográfica y protección de PII."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.key_path = Path(self.temp_dir.name) / ".test_security_key"
        self.db_path = Path(self.temp_dir.name) / "test_medical.db"
        self.cryptor = MedicalDataCryptor(key_path=self.key_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_encryption_decryption_cycle(self):
        """Verifica que el texto plano se cifre y se descifre de forma exacta."""
        raw_text = "Paciente Juan Pérez, Diagnóstico Reservado: Observación F84.0"
        encrypted = self.cryptor.encrypt_text(raw_text)

        self.assertNotEqual(raw_text, encrypted)
        self.assertTrue(encrypted.startswith("ENC:"))

        decrypted = self.cryptor.decrypt_text(encrypted)
        self.assertEqual(raw_text, decrypted)

    def test_encryption_tampering_fails(self):
        """Verifica que modificar el ciphertext o nonce dispare excepción de autenticidad."""
        raw_text = "Datos Clínicos Confidenciales"
        encrypted = self.cryptor.encrypt_text(raw_text)
        
        # Corromper el payload
        corrupted = encrypted[:-4] + "AAAA"
        with self.assertRaises(ValueError):
            self.cryptor.decrypt_text(corrupted)

    def test_pseudonymization_deterministic(self):
        """Verifica que la pseudonimización sea determinista y enmascare el ID."""
        patient_id = "P-2026-999"
        anon_1 = MedicalDataCryptor.pseudonymize_id(patient_id)
        anon_2 = MedicalDataCryptor.pseudonymize_id(patient_id)

        self.assertEqual(anon_1, anon_2)
        self.assertTrue(anon_1.startswith("ANON-"))
        self.assertNotIn(patient_id, anon_1)

    def test_sqlite_at_rest_encryption(self):
        """Verifica que en el archivo SQLite los datos sensibles residan cifrados."""
        repo = SessionRepository(database_path=self.db_path, cryptor=self.cryptor)
        
        # Guardar paciente
        repo.save_patient(
            patient_id="P-001",
            full_name="Carlos Santana Silva",
            age_months=24,
            evaluator="Dra. Valdivia",
        )
        
        # Guardar sesión y finalizar con summary
        repo.start_session(session_id="S-001", instruction="Prueba de imitación motora", source="cam_0")
        summary_payload = {"risk": "ALTO", "notes": "Falta contacto visual sostenido"}
        repo.finish_session(session_id="S-001", summary=summary_payload)
        
        # 1. Recuperar mediante el repositorio (debe devolver descifrado)
        patient_data = repo.get_patient("P-001")
        self.assertEqual(patient_data["full_name"], "Carlos Santana Silva")

        stored_session, _, _ = repo.load_report_data("S-001")
        self.assertEqual(stored_session.instruction, "Prueba de imitación motora")
        self.assertEqual(stored_session.summary["notes"], "Falta contacto visual sostenido")

        # 2. Inspección directa de bajo nivel en SQLite (debe estar cifrado con prefijo ENC:)
        raw_conn = sqlite3.connect(self.db_path)
        row_pat = raw_conn.execute("SELECT encrypted_full_name FROM patients WHERE patient_id = 'P-001'").fetchone()
        self.assertTrue(row_pat[0].startswith("ENC:"))
        self.assertNotIn("Carlos Santana", row_pat[0])

        row_ses = raw_conn.execute("SELECT instruction, summary_json FROM sessions WHERE id = 'S-001'").fetchone()
        self.assertTrue(row_ses[0].startswith("ENC:"))
        self.assertTrue(row_ses[1].startswith("ENC:"))
        self.assertNotIn("imitación motora", row_ses[0])
        self.assertNotIn("contacto visual", row_ses[1])
        raw_conn.close()
        repo.close()

    def test_anonymize_session_data(self):
        """Verifica que el anonimizador enmascare nombres y PII en reportes."""
        session_data = {
            "session_id": "S-100",
            "patient": {
                "patient_id": "P-777",
                "full_name": "María Gómez",
                "age_months": 30,
                "notes": "Diagnóstico previo familiar",
            },
            "overall_risk": "Riesgo Alto",
        }
        anon = anonymize_session_data(session_data)
        
        self.assertNotEqual(anon["patient"]["patient_id"], "P-777")
        self.assertTrue(anon["patient"]["patient_id"].startswith("ANON-"))
        self.assertNotIn("María Gómez", anon["patient"]["full_name"])
        self.assertEqual(anon["overall_risk"], "Riesgo Alto")


if __name__ == "__main__":
    unittest.main()
