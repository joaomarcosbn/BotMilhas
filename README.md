# Milhas Bot

Monitora promoções de milhas/pontos via RSS e (nas próximas fases) notifica no Telegram.

## Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

## Uso e testes
```bash
python -m milhas_bot.scraper   # roda contra os feeds reais
pytest                         # testes offline
```

## Roadmap
- [x] Fase 1: scraper RSS
- [ ] Fase 2: Firestore (deduplicação)
- [ ] Fase 3: Telegram
- [ ] Fase 4: Deploy no Render (Background Worker / Cron Job)