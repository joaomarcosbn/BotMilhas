import base64
import json

import pytest
from google.api_core.exceptions import AlreadyExists

from milhas_bot import config, database
from milhas_bot.database import DatabaseError, OfferRepository


# ---- Fake mínimo do cliente Firestore (sem rede, sem credenciais) ---------- #
class FakeSnapshot:
    def __init__(self, exists):
        self.exists = exists


class FakeDocRef:
    def __init__(self, store, doc_id):
        self.store, self.doc_id = store, doc_id

    def get(self):
        return FakeSnapshot(self.doc_id in self.store)

    def create(self, data):
        if self.doc_id in self.store:
            raise AlreadyExists("já existe")
        self.store[self.doc_id] = data


class FakeCollection:
    def __init__(self):
        self.store = {}

    def document(self, doc_id):
        return FakeDocRef(self.store, doc_id)


class FakeClient:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, FakeCollection())


@pytest.fixture
def repo():
    return OfferRepository(FakeClient(), collection="offers")


OFFER = {"title": "Livelo com bônus", "link": "https://exemplo.com/x", "published": None}


def test_oferta_nova_nao_esta_processada(repo):
    assert repo.is_processed("abc123") is False


def test_save_e_depois_is_processed(repo):
    assert repo.save("abc123", OFFER) is True
    assert repo.is_processed("abc123") is True


def test_save_duplicado_retorna_false_e_nao_sobrescreve(repo):
    repo.save("abc123", OFFER)
    assert repo.save("abc123", {"title": "outro"}) is False
    stored = repo._collection.store["abc123"]
    assert stored["title"] == "Livelo com bônus"


def test_save_adiciona_processed_at_sem_mutar_entrada(repo):
    data = dict(OFFER)
    repo.save("abc123", data)
    assert "processed_at" in repo._collection.store["abc123"]
    assert "processed_at" not in data


@pytest.mark.parametrize("bad_id", ["", "a/b"])
def test_id_invalido(repo, bad_id):
    with pytest.raises(ValueError):
        repo.is_processed(bad_id)
    with pytest.raises(ValueError):
        repo.save(bad_id, OFFER)


# ---- Carregamento de credenciais ------------------------------------------ #
@pytest.fixture
def fake_cert(monkeypatch):
    captured = {}
    monkeypatch.setattr(database.credentials, "Certificate", lambda src: captured.setdefault("src", src))
    return captured


def test_credenciais_json_puro(monkeypatch, fake_cert):
    monkeypatch.setattr(config, "FIREBASE_CREDENTIALS_JSON", json.dumps({"project_id": "p"}))
    database._load_credentials()
    assert fake_cert["src"] == {"project_id": "p"}


def test_credenciais_base64(monkeypatch, fake_cert):
    encoded = base64.b64encode(json.dumps({"project_id": "p"}).encode()).decode()
    monkeypatch.setattr(config, "FIREBASE_CREDENTIALS_JSON", encoded)
    database._load_credentials()
    assert fake_cert["src"] == {"project_id": "p"}


def test_credenciais_por_arquivo(monkeypatch, fake_cert, tmp_path):
    f = tmp_path / "cred.json"
    f.write_text("{}")
    monkeypatch.setattr(config, "FIREBASE_CREDENTIALS_JSON", None)
    monkeypatch.setattr(config, "FIREBASE_CREDENTIALS_PATH", str(f))
    database._load_credentials()
    assert fake_cert["src"] == str(f)


def test_credenciais_ausentes(monkeypatch):
    monkeypatch.setattr(config, "FIREBASE_CREDENTIALS_JSON", None)
    monkeypatch.setattr(config, "FIREBASE_CREDENTIALS_PATH", "/nao/existe.json")
    with pytest.raises(DatabaseError):
        database._load_credentials()


def test_credenciais_json_invalido(monkeypatch):
    monkeypatch.setattr(config, "FIREBASE_CREDENTIALS_JSON", "{quebrado")
    with pytest.raises(DatabaseError):
        database._load_credentials()
