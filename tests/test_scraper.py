from datetime import datetime, timezone

import pytest

from milhas_bot import scraper
from milhas_bot.scraper import FeedError, matches_keywords, build_keyword_pattern, normalize

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Teste</title>
  <item>
    <title>Livelo: transferência com 100% de BÔNUS para a Smiles</title>
    <link>https://exemplo.com/livelo-smiles</link>
    <pubDate>Mon, 26 Oct 2026 14:30:00 +0000</pubDate>
  </item>
  <item>
    <title>Promoção de passagens para Lisboa</title>
    <link>https://exemplo.com/lisboa</link>
    <pubDate>Mon, 26 Oct 2026 10:00:00 +0000</pubDate>
  </item>
  <item>
    <title>Esfera libera compra de pontos com desconto</title>
    <link>https://exemplo.com/esfera</link>
  </item>
  <item>
    <title>Itaú: transferências bonificadas</title>
    <link>https://exemplo.com/itau</link>
    <pubDate>Sun, 25 Oct 2026 09:00:00 +0000</pubDate>
  </item>
</channel></rss>"""


def test_normalize_remove_acentos():
    assert normalize("Itaú BÔNUS") == "itau bonus"


def test_match_ignora_acento_e_caixa():
    p = build_keyword_pattern(["bônus", "Itaú"])
    assert matches_keywords("100% DE BONUS", p)
    assert matches_keywords("itaú pontos", p)
    assert not matches_keywords("Passagens baratas", p)


def test_nao_casa_no_meio_da_palavra():
    p = build_keyword_pattern(["azul"])
    assert not matches_keywords("Fim do desazulamento", p)


def test_parse_filtra_apenas_relevantes():
    offers = scraper.parse_offers(SAMPLE_RSS)
    titles = [o["title"] for o in offers]
    assert len(offers) == 3
    assert "Promoção de passagens para Lisboa" not in titles


def test_parse_campos_e_datas():
    offers = scraper.parse_offers(SAMPLE_RSS)
    first = offers[0]
    assert first["link"] == "https://exemplo.com/livelo-smiles"
    assert first["published"] == datetime(2026, 10, 26, 14, 30, tzinfo=timezone.utc)
    assert offers[1]["published"] is None  # item sem pubDate
    assert len(first["id"]) == 40


def test_parse_respeita_limit():
    assert len(scraper.parse_offers(SAMPLE_RSS, limit=1)) == 1


def test_keywords_vazias_levantam_erro():
    with pytest.raises(ValueError):
        build_keyword_pattern(["", "  "])


def test_feed_invalido():
    with pytest.raises(FeedError):
        scraper.parse_offers("isto não é xml nem rss")


def test_multiplos_feeds_isola_falhas_e_deduplica(monkeypatch):
    def fake_fetch(url, timeout=0):
        if "quebrado" in url:
            raise FeedError("falhou")
        return SAMPLE_RSS.encode()

    monkeypatch.setattr(scraper, "fetch_feed", fake_fetch)
    offers = scraper.get_offers_from_feeds(
        ["https://a.com/feed", "https://quebrado.com/feed", "https://b.com/feed"]
    )
    assert len(offers) == 3  # duplicatas entre a.com e b.com removidas
    assert offers[0]["published"] >= offers[1]["published"]  # ordenado desc
