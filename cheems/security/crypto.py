"""Módulo de seguridad criptográfica y privacidad de datos médicos para CHEEMS."""

import base64
import hashlib
import os
from pathlib import Path
from typing import Optional, Union
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


class MedicalDataCryptor:
    """Capa de cifrado autenticado AES-256-GCM para datos sensibles (PII/Biometría).
    
    Garantiza confidencialidad e integridad criptográfica en reposo conforme a
    normativas de protección de datos de salud (HIPAA / GDPR / Ley de Datos Personales).
    """

    def __init__(self, key_path: Optional[Path] = None, master_secret: Optional[str] = None) -> None:
        """Inicializa el motor criptográfico con una clave AES-256 de 32 bytes."""
        if key_path is None:
            key_path = Path("data/.security_key")
            
        self.key_path = key_path
        self._key = self._load_or_generate_key(master_secret)
        self._aesgcm = AESGCM(self._key)

    def _load_or_generate_key(self, master_secret: Optional[str]) -> bytes:
        """Carga o genera de forma determinista la clave AES-256 de la instalación."""
        if master_secret:
            # Derivación PBKDF2 de 256 bits a partir de secreto maestro
            salt = b"cheems_medical_salt_v1"
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            return kdf.derive(master_secret.encode("utf-8"))

        if self.key_path.exists():
            return self.key_path.read_bytes()

        # Generación de nueva clave criptográfica aleatoria de 256 bits (32 bytes)
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        key = AESGCM.generate_key(bit_length=256)
        self.key_path.write_bytes(key)
        return key

    def encrypt_text(self, plain_text: Optional[str]) -> Optional[str]:
        """Cifra un texto plano y lo devuelve codificado en Base64 seguro (nonce + ciphertext)."""
        if plain_text is None:
            return None
        if not plain_text:
            return ""

        nonce = os.urandom(12)  # 96-bit nonce estándar para AES-GCM
        ciphertext = self._aesgcm.encrypt(nonce, plain_text.encode("utf-8"), None)
        # Empaquetamos nonce (12 bytes) + ciphertext y codificamos a Base64
        payload = nonce + ciphertext
        return "ENC:" + base64.b64encode(payload).decode("ascii")

    def decrypt_text(self, encrypted_payload: Optional[str]) -> Optional[str]:
        """Descifra un texto codificado en Base64 validando autenticidad (MAC)."""
        if encrypted_payload is None:
            return None
        if not encrypted_payload or not encrypted_payload.startswith("ENC:"):
            return encrypted_payload  # Si no está cifrado (legacy), retorna directo

        raw_b64 = encrypted_payload[4:]
        try:
            payload = base64.b64decode(raw_b64.encode("ascii"))
            nonce = payload[:12]
            ciphertext = payload[12:]
            decrypted_bytes = self._aesgcm.decrypt(nonce, ciphertext, None)
            return decrypted_bytes.decode("utf-8")
        except Exception as err:
            raise ValueError(f"Fallo de autenticidad o clave inválida al descifrar: {err}")

    @staticmethod
    def pseudonymize_id(raw_id: str, salt: str = "cheems_anonymizer_salt") -> str:
        """Genera un identificador pseudónimo no reversible mediante SHA-256."""
        hasher = hashlib.sha256()
        hasher.update(salt.encode("utf-8"))
        hasher.update(raw_id.encode("utf-8"))
        return f"ANON-{hasher.hexdigest()[:12].upper()}"
