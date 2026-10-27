"""Configuração central, carregada de variáveis de ambiente (.env)."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_FEED_URLS = (
    "https://passageirodeprimeira.com/feed/",
    "https://www.melhoresdestinos.com.br/feed",
)

# Palavras-chave padrão (comparadas sem acento e sem diferenciar maiúsculas).
DEFAULT_KEYWORDS = (
    "bônus",
    "bonus",
    "transferência",
    "compra de pontos",
    "Livelo",
    "Esfera",
    "Smiles",
    "Azul",
    "LATAM",
    "Itaú",
)


def _split_csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


FEED_URLS: list[str] = _split_csv(os.getenv("FEED_URLS")) or list(DEFAULT_FEED_URLS)
KEYWORDS: list[str] = _split_csv(os.getenv("KEYWORDS")) or list(DEFAULT_KEYWORDS)
MAX_ENTRIES: int = int(os.getenv("MAX_ENTRIES", "30"))
REQUEST_TIMEOUT: float = float(os.getenv("REQUEST_TIMEOUT", "15"))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
