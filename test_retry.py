import sqlite3
from pathlib import Path

import pytest

import base
from generation import generer


def test_retry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    generer()
    connexion = sqlite3.connect("test.db", timeout=0)
    verrou = sqlite3.connect("test.db", timeout=0)
    pauses: list[float] = []
    try:
        base.creer_tables(connexion)
        verrou.execute("BEGIN IMMEDIATE")

        def liberer(duree: float) -> None:
            pauses.append(duree)
            verrou.rollback()

        monkeypatch.setattr(base, "sleep", liberer)
        assert base.inserer_fichier(connexion, Path("transactions_1.csv")) is True
        assert pauses == [0.1]
        assert connexion.execute("SELECT COUNT(*) FROM transactions").fetchone() == (6,)
        assert connexion.execute("SELECT COUNT(*) FROM fichiers").fetchone() == (1,)
        assert connexion.execute("SELECT montant FROM resultats WHERE categorie = 'destinataire'").fetchone() == (1_977_580,)
        assert base.inserer_fichier(connexion, Path("transactions_1.csv")) is False
        assert connexion.execute("SELECT COUNT(*) FROM transactions").fetchone() == (6,)
    finally:
        verrou.close()
        connexion.close()


def test_limite_retry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    generer()
    connexion = sqlite3.connect("test.db", timeout=0)
    verrou = sqlite3.connect("test.db", timeout=0)
    pauses: list[float] = []
    try:
        base.creer_tables(connexion)
        verrou.execute("BEGIN IMMEDIATE")
        monkeypatch.setattr(base, "sleep", pauses.append)
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            base.inserer_fichier(connexion, Path("transactions_1.csv"))
        assert pauses == [0.1, 0.2]
        assert connexion.execute("SELECT COUNT(*) FROM fichiers").fetchone() == (0,)
        assert connexion.execute("SELECT COUNT(*) FROM transactions").fetchone() == (0,)
    finally:
        verrou.close()
        connexion.close()


@pytest.mark.parametrize("requete", [
    "DROP TABLE resultats",
    "CREATE TRIGGER erreur BEFORE INSERT ON resultats BEGIN SELECT RAISE(ABORT, 'contrainte'); END;",
])
def test_pas_de_retry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, requete: str) -> None:
    monkeypatch.chdir(tmp_path)
    generer()
    connexion = sqlite3.connect(":memory:")
    pauses: list[float] = []
    try:
        base.creer_tables(connexion)
        connexion.execute(requete)
        monkeypatch.setattr(base, "sleep", pauses.append)
        with pytest.raises((sqlite3.OperationalError, sqlite3.IntegrityError)):
            base.inserer_fichier(connexion, Path("transactions_1.csv"))
        assert pauses == []
        assert connexion.execute("SELECT COUNT(*) FROM fichiers").fetchone() == (0,)
        assert connexion.execute("SELECT COUNT(*) FROM transactions").fetchone() == (0,)
    finally:
        connexion.close()
