from cryptography.fernet import Fernet
from app.config import settings


def get_fernet() -> Fernet:
    if not settings.repo_encryption_key:
        raise ValueError("REPO_ENCRYPTION_KEY environment variable is required for private repo support")
    return Fernet(settings.repo_encryption_key.encode())


def encrypt_token(plaintext: str) -> str:
    return get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    return get_fernet().decrypt(ciphertext.encode()).decode()
