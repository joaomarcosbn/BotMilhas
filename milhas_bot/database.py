"""Persistência no Firestore para evitar o reprocessamento de ofertas.

Cada oferta vira um documento em `<FIRESTORE_COLLECTION>/<sha1_do_link>`.
Como o ID do documento é o próprio SHA-1, a checagem de duplicidade é uma
leitura direta por ID (rápida e barata) e a gravação usa `create()`, que é
atômica: se dois processos tentarem salvar a mesma oferta, só um consegue.

==========================  CONFIGURAÇÃO DAS CREDENCIAIS  ==========================
1) Firebase Console > seu projeto > Build > Firestore Database > "Criar banco de dados"
   (modo Native). Com o Admin SDK as regras de segurança não se aplicam, então pode
   manter o modo de produção (bloqueado para clientes).

2) Firebase Console > Configurações do projeto > Contas de serviço >
   "Gerar nova chave privada". Salve o JSON como `firebase-credentials.json`
   na raiz do projeto (já está no .gitignore — NUNCA faça commit dele).

3) LOCAL — no `.env`:
       FIREBASE_CREDENTIALS_PATH=./firebase-credentials.json

4) RENDER — duas opções (use apenas uma):
   a) Variável de ambiente (mais simples): gere o base64 do arquivo e cole em
      Environment > FIREBASE_CREDENTIALS_JSON
          Linux:  base64 -w0 firebase-credentials.json
          macOS:  base64 -i firebase-credentials.json
      (O JSON puro também funciona, mas o base64 evita problemas com quebras de linha.)
   b) Secret File: Environment > Secret Files > crie `firebase-credentials.json`
      com o conteúdo do JSON; ele fica em /etc/secrets/firebase-credentials.json.
      Defina FIREBASE_CREDENTIALS_PATH=/etc/secrets/firebase-credentials.json

Prioridade: FIREBASE_CREDENTIALS_JSON > FIREBASE_CREDENTIALS_PATH.
=====================================================================================
"""
from __future__ import annotations

import base64
import binascii
import json
import logging
from pathlib import Path
from typing import Any, Mapping

import firebase_admin
from firebase_admin import credentials, firestore
from google.api_core.exceptions import AlreadyExists, GoogleAPIError

from milhas_bot import config

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Falha de configuração ou de comunicação com o Firestore."""


# --------------------------------------------------------------------------- #
# Credenciais e inicialização
# --------------------------------------------------------------------------- #
def _load_credentials() -> credentials.Certificate:
    raw = (config.FIREBASE_CREDENTIALS_JSON or "").strip()
    if raw:
        try:
            if not raw.startswith("{"):
                raw = base64.b64decode(raw, validate=True).decode("utf-8")
            return credentials.Certificate(json.loads(raw))
        except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise DatabaseError(
                "FIREBASE_CREDENTIALS_JSON inválido: use o JSON puro ou o JSON em base64."
            ) from exc

    path = config.FIREBASE_CREDENTIALS_PATH
    if path and Path(path).is_file():
        return credentials.Certificate(path)

    raise DatabaseError(
        "Credenciais do Firebase não encontradas. Defina FIREBASE_CREDENTIALS_JSON "
        "ou FIREBASE_CREDENTIALS_PATH (veja as instruções no topo de database.py)."
    )


def init_firestore() -> Any:
    """Inicializa o Firebase Admin (uma única vez) e devolve o cliente Firestore."""
    try:
        firebase_admin.get_app()
    except ValueError:  # app default ainda não existe
        firebase_admin.initialize_app(_load_credentials())
    return firestore.client()


# --------------------------------------------------------------------------- #
# Repositório (recebe o cliente por injeção -> fácil de testar com um fake)
# --------------------------------------------------------------------------- #
class OfferRepository:
    def __init__(self, client: Any, collection: str = config.FIRESTORE_COLLECTION) -> None:
        self._collection = client.collection(collection)

    @staticmethod
    def _validate_id(offer_id: str) -> None:
        if not offer_id or "/" in offer_id:
            raise ValueError(f"offer_id inválido: {offer_id!r}")

    def is_processed(self, offer_id: str) -> bool:
        self._validate_id(offer_id)
        try:
            return self._collection.document(offer_id).get().exists
        except GoogleAPIError as exc:
            raise DatabaseError(f"Erro ao consultar a oferta {offer_id}: {exc}") from exc

    def save(self, offer_id: str, offer_data: Mapping[str, Any]) -> bool:
        """Salva a oferta. Retorna True se foi gravada agora, False se já existia."""
        self._validate_id(offer_id)
        payload = {**offer_data, "processed_at": firestore.SERVER_TIMESTAMP}
        try:
            self._collection.document(offer_id).create(payload)
        except AlreadyExists:
            logger.debug("Oferta %s já existia no banco.", offer_id)
            return False
        except GoogleAPIError as exc:
            raise DatabaseError(f"Erro ao salvar a oferta {offer_id}: {exc}") from exc
        return True


# --------------------------------------------------------------------------- #
# API pública de módulo (repositório criado sob demanda)
# --------------------------------------------------------------------------- #
_repository: OfferRepository | None = None


def get_repository() -> OfferRepository:
    global _repository
    if _repository is None:
        _repository = OfferRepository(init_firestore())
    return _repository


def is_offer_processed(offer_id: str) -> bool:
    """True se o SHA-1 da oferta já existe no Firestore."""
    return get_repository().is_processed(offer_id)


def save_offer(offer_id: str, offer_data: dict) -> bool:
    """Registra a oferta como processada (True = nova, False = já existia)."""
    return get_repository().save(offer_id, offer_data)
