import sqlite3
import subprocess
import sys
from pathlib import Path

from base import creer_tables


def lancer(dossier: Path, erreur: bool = False) -> subprocess.CompletedProcess[str]:
    commande = [sys.executable, str(Path(__file__).with_name("main.py"))]
    if erreur:
        commande.append("--erreur")
    return subprocess.run(commande, cwd=dossier, capture_output=True, text=True, check=False)


def test_pipeline(tmp_path: Path) -> None:
    resultat = lancer(tmp_path)
    assert resultat.returncode == 0, resultat.stdout + resultat.stderr
    connexion = sqlite3.connect(tmp_path / "transactions.db")
    try:
        assert connexion.execute("SELECT COUNT(*) FROM fichiers").fetchone() == (3,)
        assert connexion.execute("SELECT COUNT(*), SUM(depasse_5000) FROM transactions").fetchone() == (18, 6)
        attendus = [
            ("banque", "BNPPARIBAS", 3_705_000),
            ("banque", "COMMERZBANK", 2_227_740),
            ("destinataire", "ES9121000418450200051332", 5_932_740),
            ("origine", "DE89370400440532013000", 2_227_740),
            ("origine", "FR7630006000011234567890189", 3_705_000),
        ]
        assert connexion.execute("SELECT * FROM resultats ORDER BY categorie, identifiant").fetchall() == attendus
        assert connexion.execute("""
            SELECT iban_origine, SUM(montant) FROM transactions GROUP BY iban_origine ORDER BY iban_origine
        """).fetchall() == [("DE89370400440532013000", 2_227_740), ("FR7630006000011234567890189", 3_705_000)]
        assert connexion.execute("""
            SELECT iban_destinataire, SUM(montant) FROM transactions GROUP BY iban_destinataire
        """).fetchall() == [("ES9121000418450200051332", 5_932_740)]
        assert connexion.execute("SELECT montant, devise, depasse_5000 FROM transactions ORDER BY id LIMIT 1").fetchone() == (125_000, "EUR", 0)
        deuxieme = lancer(tmp_path)
        assert deuxieme.returncode == 0
        assert deuxieme.stdout.count("déjà traité") == 3
        assert connexion.execute("SELECT COUNT(*), SUM(depasse_5000) FROM transactions").fetchone() == (18, 6)
        assert connexion.execute("SELECT COUNT(*) FROM fichiers").fetchone() == (3,)
        assert connexion.execute("SELECT * FROM resultats ORDER BY categorie, identifiant").fetchall() == attendus
    finally:
        connexion.close()


def test_contenu_identique_et_nom_different(tmp_path: Path) -> None:
    assert lancer(tmp_path).returncode == 0
    contenu = (tmp_path / "transactions_1.csv").read_bytes()
    (tmp_path / "copie.csv").write_bytes(contenu)
    resultat = lancer(tmp_path)
    assert resultat.returncode == 0
    assert "copie.csv : déjà traité" in resultat.stdout
    connexion = sqlite3.connect(tmp_path / "transactions.db")
    try:
        assert connexion.execute("SELECT COUNT(*) FROM transactions").fetchone() == (18,)
        assert connexion.execute("SELECT COUNT(*) FROM fichiers").fetchone() == (3,)
    finally:
        connexion.close()


def test_meme_nom_et_contenu_different(tmp_path: Path) -> None:
    assert lancer(tmp_path).returncode == 0
    fichier = tmp_path / "transactions_1.csv"
    fichier.write_bytes(fichier.read_bytes().replace(b"1250.00", b"1251.00"))
    resultat = lancer(tmp_path)
    assert resultat.returncode == 0
    assert "transactions_1.csv : importé" in resultat.stdout
    connexion = sqlite3.connect(tmp_path / "transactions.db")
    try:
        assert connexion.execute("SELECT COUNT(*) FROM transactions").fetchone() == (24,)
        assert connexion.execute("SELECT COUNT(*) FROM fichiers").fetchone() == (4,)
        assert connexion.execute("SELECT montant FROM resultats WHERE categorie = 'origine' AND identifiant LIKE 'FR%'").fetchone() == (4_940_100,)
        assert lancer(tmp_path).returncode == 0
        assert connexion.execute("SELECT COUNT(*) FROM transactions").fetchone() == (24,)
    finally:
        connexion.close()


def test_echec_et_reprise(tmp_path: Path) -> None:
    resultat = lancer(tmp_path, erreur=True)
    assert resultat.returncode == 1
    assert "transactions_2.csv : rejeté" in resultat.stdout
    connexion = sqlite3.connect(tmp_path / "transactions.db")
    try:
        assert connexion.execute("SELECT COUNT(*), SUM(depasse_5000) FROM transactions").fetchone() == (12, 4)
        assert connexion.execute("SELECT nom FROM fichiers ORDER BY nom").fetchall() == [("transactions_1.csv",), ("transactions_3.csv",)]
        assert connexion.execute("SELECT COUNT(*) FROM transactions WHERE datetime_transaction LIKE '2024-03-02%'").fetchone() == (0,)
        assert connexion.execute("SELECT montant FROM resultats WHERE categorie = 'destinataire'").fetchone() == (3_955_160,)
        fichier = tmp_path / "transactions_2.csv"
        fichier.write_bytes(fichier.read_bytes().replace(b"abc", b"7400.50"))
        assert lancer(tmp_path).returncode == 0
        assert connexion.execute("SELECT COUNT(*), SUM(depasse_5000) FROM transactions").fetchone() == (18, 6)
        assert connexion.execute("SELECT montant FROM resultats WHERE categorie = 'destinataire'").fetchone() == (5_932_740,)
    finally:
        connexion.close()


def test_erreur_insertion(tmp_path: Path) -> None:
    connexion = sqlite3.connect(tmp_path / "transactions.db")
    try:
        creer_tables(connexion)
        connexion.execute("""
            CREATE TRIGGER erreur BEFORE INSERT ON transactions
            WHEN NEW.datetime_transaction = '2024-03-02T10:00:00'
            BEGIN SELECT RAISE(ABORT, 'insertion impossible'); END;
        """)
        resultat = lancer(tmp_path)
        assert resultat.returncode == 1
        assert "insertion impossible" in resultat.stdout
        assert connexion.execute("SELECT COUNT(*) FROM transactions").fetchone() == (12,)
        assert connexion.execute("SELECT COUNT(*) FROM fichiers").fetchone() == (2,)
        assert connexion.execute("SELECT COUNT(*) FROM transactions WHERE datetime_transaction LIKE '2024-03-02%'").fetchone() == (0,)
        assert connexion.execute("SELECT montant FROM resultats WHERE categorie = 'destinataire'").fetchone() == (3_955_160,)
    finally:
        connexion.close()
