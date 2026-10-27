"""Extração e filtragem de ofertas de milhas a partir de feeds RSS.

Camadas (cada uma testável isoladamente):
    fetch_feed()            -> I/O de rede (retorna bytes)
    parse_offers()          -> função pura: conteúdo XML -> ofertas filtradas
    get_offers()            -> orquestra um feed
    get_offers_from_feeds() -> orquestra vários feeds, com isolamento de falhas

Regra de filtragem (duas camadas): o título precisa conter
    1) um PROGRAMA (Livelo, Smiles, Itaú...) E
    2) uma AÇÃO/CONTEXTO (bônus, transferência, compra, desconto...).
"""
from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from calendar import timegm
from datetime import datetime, timezone
from typing import Iterable, TypedDict

import feedparser
import httpx

from milhas_bot import config

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; MilhasBot/1.0; +https://example.com/bot)"
_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


class Offer(TypedDict):
    id: str                     # hash SHA-1 estável do link (ID do documento no Firestore)
    title: str
    link: str
    published: datetime | None  # timezone-aware (UTC) ou None se o feed não informar


class FeedError(Exception):
    """Falha ao baixar ou interpretar um feed."""


# --------------------------------------------------------------------------- #
# Utilidades de texto e filtro
# --------------------------------------------------------------------------- #
def normalize(text: str) -> str:
    """Remove acentos e aplica casefold: 'Itaú' -> 'itau', 'BÔNUS' -> 'bonus'."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.casefold()


def build_keyword_pattern(keywords: Iterable[str]) -> re.Pattern[str]:
    """Compila um regex que casa o *início* de qualquer palavra-chave.

    \\b só no começo: 'transferencia' casa 'transferências' e 'esfera' casa
    'Esferas', mas nada casa no meio de outra palavra.
    """
    terms = [re.escape(normalize(k.strip())) for k in keywords if k and k.strip()]
    if not terms:
        raise ValueError("É necessário informar ao menos uma palavra-chave.")
    return re.compile(r"\b(?:" + "|".join(terms) + ")")


def matches_keywords(text: str, pattern: re.Pattern[str]) -> bool:
    return bool(pattern.search(normalize(text)))


def matches_offer(
    text: str,
    programs_pattern: re.Pattern[str],
    actions_pattern: re.Pattern[str],
) -> bool:
    """Validação em duas camadas: precisa de um programa E de uma ação."""
    normalized = normalize(text)
    return bool(programs_pattern.search(normalized)) and bool(actions_pattern.search(normalized))


# --------------------------------------------------------------------------- #
# Rede
# --------------------------------------------------------------------------- #
def fetch_feed(url: str, timeout: float = config.REQUEST_TIMEOUT) -> bytes:
    """Baixa o feed com timeout e User-Agent (feedparser sozinho não tem timeout)."""
    try:
        response = httpx.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, */*"},
            timeout=timeout,
            follow_redirects=True,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise FeedError(f"Erro ao baixar {url}: {exc}") from exc
    return response.content


# --------------------------------------------------------------------------- #
# Parsing (puro, sem rede)
# --------------------------------------------------------------------------- #
def _parse_published(entry: feedparser.FeedParserDict) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        parsed = entry.get(attr)
        if parsed:
            return datetime.fromtimestamp(timegm(parsed), tz=timezone.utc)
    return None


def _make_id(link: str) -> str:
    return hashlib.sha1(link.encode("utf-8")).hexdigest()


def parse_offers(
    content: bytes | str,
    programs: Iterable[str] | None = None,
    actions: Iterable[str] | None = None,
    limit: int = config.MAX_ENTRIES,
) -> list[Offer]:
    """Interpreta o XML do feed e devolve só entradas com programa E ação no título."""
    programs_pattern = build_keyword_pattern(programs or config.PROGRAMS)
    actions_pattern = build_keyword_pattern(actions or config.ACTIONS)
    parsed = feedparser.parse(content)

    if parsed.bozo and not parsed.entries:
        raise FeedError(f"Feed inválido: {parsed.get('bozo_exception')}")

    offers: list[Offer] = []
    for entry in parsed.entries[:limit]:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        if not title or not link:
            continue
        if not matches_offer(title, programs_pattern, actions_pattern):
            continue
        offers.append(
            Offer(
                id=_make_id(link),
                title=title,
                link=link,
                published=_parse_published(entry),
            )
        )
    return offers


# --------------------------------------------------------------------------- #
# API pública
# --------------------------------------------------------------------------- #
def get_offers(
    feed_url: str,
    programs: Iterable[str] | None = None,
    actions: Iterable[str] | None = None,
    limit: int = config.MAX_ENTRIES,
    timeout: float = config.REQUEST_TIMEOUT,
) -> list[Offer]:
    """Baixa um feed RSS e retorna as ofertas filtradas (id, título, link, data)."""
    content = fetch_feed(feed_url, timeout=timeout)
    offers = parse_offers(content, programs=programs, actions=actions, limit=limit)
    logger.info("%s: %d oferta(s) relevante(s)", feed_url, len(offers))
    return offers


def get_offers_from_feeds(
    feed_urls: Iterable[str] | None = None,
    programs: Iterable[str] | None = None,
    actions: Iterable[str] | None = None,
    limit: int = config.MAX_ENTRIES,
    timeout: float = config.REQUEST_TIMEOUT,
) -> list[Offer]:
    """Processa vários feeds; uma falha em um feed não derruba os demais.

    Remove duplicatas entre feeds (mesmo link) e ordena da mais recente para a mais antiga.
    """
    unique: dict[str, Offer] = {}
    for url in feed_urls or config.FEED_URLS:
        try:
            for offer in get_offers(url, programs, actions, limit, timeout):
                unique.setdefault(offer["id"], offer)
        except FeedError as exc:
            logger.warning("Feed ignorado: %s", exc)
    return sorted(unique.values(), key=lambda o: o["published"] or _EPOCH, reverse=True)


if __name__ == "__main__":  # teste manual: python -m milhas_bot.scraper
    logging.basicConfig(level=config.LOG_LEVEL, format="%(levelname)s %(message)s")
    for item in get_offers_from_feeds():
        when = item["published"].strftime("%d/%m %H:%M") if item["published"] else "s/ data"
        print(f"[{when}] {item['title']}\n    {item['link']}")
