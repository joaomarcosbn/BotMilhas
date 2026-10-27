"""Configuração central, carregada de variáveis de ambiente (.env)."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# Feeds de categorias específicas (menos ruído que os feeds raiz).
DEFAULT_FEED_URLS = (
    "https://passageirodeprimeira.com/categorias/promocoes/transferencia-de-pontos/feed/",
    "https://www.melhoresdestinos.com.br/promocoes/milhas/feed/",
)

# Camada 1 — programa/banco. Comparação sem acento, sem diferenciar maiúsculas,
# casando o início da palavra ("Esfera" casa "Esferas").
DEFAULT_PROGRAMS = (
    "Livelo",
    "Esfera",
    "Smiles",
    "LATAM",
    "Azul",
    "TudoAzul",
    "Itaú",
)

# Camada 2 — ação/contexto. Uma oferta precisa ter programa E ação.
DEFAULT_ACTIONS = (
    "bônus",
    "bonificad",      # bonificada, bonificado, bonificadas...
    "transferência",
    "transferir",
    "compra",         # compra, compras, comprar
    "desconto",
)


def _split_csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


FEED_URLS: list[str] = _split_csv(os.getenv("FEED_URLS")) or list(DEFAULT_FEED_URLS)
PROGRAMS: list[str] = _split_csv(os.getenv("PROGRAMS")) or list(DEFAULT_PROGRAMS)
ACTIONS: list[str] = _split_csv(os.getenv("ACTIONS")) or list(DEFAULT_ACTIONS)
MAX_ENTRIES: int = int(os.getenv("MAX_ENTRIES", "30"))
REQUEST_TIMEOUT: float = float(os.getenv("REQUEST_TIMEOUT", "15"))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

# Firebase / Firestore
FIREBASE_CREDENTIALS_PATH: str | None = os.getenv("FIREBASE_CREDENTIALS_PATH")
FIREBASE_CREDENTIALS_JSON: str | None = os.getenv("FIREBASE_CREDENTIALS_JSON")
FIRESTORE_COLLECTION: str = os.getenv("FIRESTORE_COLLECTION", "offers")
