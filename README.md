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
pytest                         # testes offline (scraper + database com fake)
```

## Filtro em duas camadas
Uma oferta só passa se o título tiver um **programa** (`PROGRAMS`) **e** uma **ação** (`ACTIONS`).
Os padrões ficam em `milhas_bot/config.py` e podem ser sobrescritos no `.env`.

## Configurando o Firebase / Firestore
1. **Firebase Console** → crie um projeto → *Build > Firestore Database* → *Criar banco de dados* (modo Native).
2. *Configurações do projeto > Contas de serviço* → **Gerar nova chave privada**.
   Salve como `firebase-credentials.json` na raiz (já está no `.gitignore`; nunca faça commit).
3. **Local** (`.env`):
   ```
   FIREBASE_CREDENTIALS_PATH=./firebase-credentials.json
   ```
4. **Render** (escolha uma opção):
   - **Variável de ambiente:** `base64 -w0 firebase-credentials.json` (macOS: `base64 -i ...`) e cole o resultado em `FIREBASE_CREDENTIALS_JSON`.
   - **Secret File:** crie `firebase-credentials.json` em *Environment > Secret Files* e defina
     `FIREBASE_CREDENTIALS_PATH=/etc/secrets/firebase-credentials.json`.

`FIREBASE_CREDENTIALS_JSON` tem prioridade sobre `FIREBASE_CREDENTIALS_PATH`.

## Uso do banco
```python
from milhas_bot.scraper import get_offers_from_feeds
from milhas_bot.database import is_offer_processed, save_offer

for offer in get_offers_from_feeds():
    if is_offer_processed(offer["id"]):
        continue
    ...  # Fase 3: enviar ao Telegram
    save_offer(offer["id"], offer)
```

## Roadmap
- [x] Fase 1: scraper RSS
- [x] Fase 2: Firestore (deduplicação)
- [ ] Fase 3: Telegram
- [ ] Fase 4: Deploy no Render (Background Worker / Cron Job)
