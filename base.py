import hashlib
import sqlite3
from pathlib import Path
from time import sleep

from traitement import lire_csv, drapeaux, sommes_banques, sommes_destinataires, sommes_origines


def creer_tables(connexion: sqlite3.Connection) -> None:
    connexion.execute("PRAGMA foreign_keys = ON")
    connexion.executescript("""
        CREATE TABLE IF NOT EXISTS fichiers (
            empreinte TEXT PRIMARY KEY,
            nom TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY,
            fichier TEXT NOT NULL REFERENCES fichiers(empreinte),
            datetime_transaction TEXT NOT NULL,
            iban_origine TEXT NOT NULL,
            pays_source TEXT NOT NULL,
            banque_source TEXT NOT NULL,
            iban_destinataire TEXT NOT NULL,
            pays_destinataire TEXT NOT NULL,
            montant INTEGER NOT NULL CHECK(montant >= 0),
            devise TEXT NOT NULL CHECK(devise = 'EUR'),
            depasse_5000 INTEGER NOT NULL CHECK(depasse_5000 IN (0, 1))
        );
        CREATE TABLE IF NOT EXISTS resultats (
            categorie TEXT NOT NULL,
            identifiant TEXT NOT NULL,
            montant INTEGER NOT NULL CHECK(typeof(montant) = 'integer'),
            PRIMARY KEY(categorie, identifiant)
        );
    """)


def inserer(
    connexion: sqlite3.Connection, nom: str, empreinte: str, contenu: bytes,
) -> bool:
    with connexion:
        curseur = connexion.execute("""
            INSERT INTO fichiers VALUES (?, ?)
            ON CONFLICT(empreinte) DO NOTHING
        """, (empreinte, nom))
        if curseur.rowcount == 0:
            return False
        transactions = lire_csv(contenu)
        for t, alerte in zip(transactions, drapeaux(transactions)):
            connexion.execute("""
                INSERT INTO transactions VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                empreinte, t["datetime_transaction"], t["iban_origine"],
                t["pays_source"], t["banque_source"], t["iban_destinataire"],
                t["pays_destinataire"], t["montant"], t["devise"], int(alerte),
            ))
        totaux = [
            ("origine", sommes_origines(transactions)),
            ("banque", sommes_banques(transactions)),
            ("destinataire", sommes_destinataires(transactions)),
        ]
        for categorie, sommes in totaux:
            for identifiant, montant in sommes.items():
                connexion.execute("""
                    INSERT INTO resultats VALUES (?, ?, ?)
                    ON CONFLICT(categorie, identifiant)
                    DO UPDATE SET montant = montant + excluded.montant
                """, (categorie, identifiant, montant))
    return True


def inserer_fichier(connexion: sqlite3.Connection, chemin: Path) -> bool:
    contenu = chemin.read_bytes()
    empreinte = hashlib.sha256(contenu).hexdigest()
    tentative = 0
    while True:
        try:
            return inserer(connexion, chemin.name, empreinte, contenu)
        except sqlite3.OperationalError as erreur:
            tentative += 1
            if erreur.sqlite_errorcode & 255 != sqlite3.SQLITE_BUSY or tentative == 3:
                raise
            sleep(0.1 * tentative)
