import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from base import creer_tables, inserer_fichier
from generation import generer
from traitement import charger


@pytest.fixture
def connexion() -> Iterator[sqlite3.Connection]:
    base = sqlite3.connect(":memory:")
    creer_tables(base)
    yield base
    base.close()


@pytest.fixture
def fichier(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    generer()
    return tmp_path / "transactions_1.csv"


def test_generation(fichier: Path) -> None:
    chemins = sorted(fichier.parent.glob("*.csv"))
    assert len(chemins) == 3
    avant = [p.read_bytes() for p in chemins]
    for chemin in chemins:
        chemin.unlink()
    generer()
    assert [p.read_bytes() for p in chemins] == avant
    for chemin in chemins:
        donnees = charger(chemin)
        assert len(donnees) == 6
        assert sum(t["montant"] > 500_000 for t in donnees) == 2
        origines = [t["iban_origine"] for t in donnees]
        assert len(set(origines)) == 2
        assert all(origines.count(iban) == 3 for iban in origines)


@pytest.mark.parametrize("avant,apres", [
    ("7400.50", "abc"),
    ("7400.50", "NaN"),
    ("7400.50", "1.001"),
    ("7400.50", "1.00000000000000000000000000001"),
    ("7400.50", "-1"),
    ("2024-03-01T10:00:00", "date incorrecte"),
    ("7400.50,EUR", "7400.50"),
    ("7400.50,EUR", "7400.50,USD"),
])
def test_rejet_global(
    fichier: Path, connexion: sqlite3.Connection, avant: str, apres: str,
) -> None:
    contenu = fichier.read_text(encoding="utf-8")
    fichier.write_text(contenu.replace(avant, apres), encoding="utf-8")
    with pytest.raises(ValueError, match="Fichier rejeté"):
        inserer_fichier(connexion, fichier)
    assert connexion.execute("SELECT COUNT(*) FROM transactions").fetchone() == (0,)
    assert connexion.execute("SELECT COUNT(*) FROM fichiers").fetchone() == (0,)


def test_import(fichier: Path, connexion: sqlite3.Connection) -> None:
    for chemin in sorted(fichier.parent.glob("*.csv")):
        inserer_fichier(connexion, chemin)
    assert connexion.execute("SELECT COUNT(*), SUM(depasse_5000) FROM transactions").fetchone() == (18, 6)
    assert connexion.execute("""
        SELECT identifiant, montant FROM resultats
        WHERE categorie = 'banque' ORDER BY identifiant
    """).fetchall() == [("BNPPARIBAS", 3_705_000), ("COMMERZBANK", 2_227_740)]
    assert inserer_fichier(connexion, fichier) is False
    assert connexion.execute("SELECT COUNT(*) FROM transactions").fetchone() == (18,)


def test_rollback(fichier: Path, connexion: sqlite3.Connection) -> None:
    inserer_fichier(connexion, fichier)
    avant = connexion.execute("SELECT * FROM resultats ORDER BY categorie, identifiant").fetchall()
    connexion.execute("""
        CREATE TRIGGER erreur BEFORE INSERT ON resultats
        WHEN NEW.categorie = 'banque'
        BEGIN SELECT RAISE(ABORT, 'erreur test'); END;
    """)
    with pytest.raises(sqlite3.IntegrityError, match="erreur test"):
        inserer_fichier(connexion, fichier.parent / "transactions_2.csv")
    assert connexion.execute("SELECT COUNT(*) FROM transactions").fetchone() == (6,)
    assert connexion.execute("SELECT COUNT(*) FROM fichiers").fetchone() == (1,)
    assert connexion.execute("SELECT * FROM resultats ORDER BY categorie, identifiant").fetchall() == avant
