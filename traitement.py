import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation, localcontext
from io import StringIO
from pathlib import Path
from typing import TypedDict


class Transaction(TypedDict):
    datetime_transaction: str
    iban_origine: str
    pays_source: str
    banque_source: str
    iban_destinataire: str
    pays_destinataire: str
    montant: int
    devise: str


def charger(chemin: Path) -> list[Transaction]:
    return lire_csv(chemin.read_bytes())


def lire_csv(contenu: bytes) -> list[Transaction]:
    transactions: list[Transaction] = []
    colonnes = [
        "datetime_transaction", "iban_origine", "pays_source", "banque_source",
        "iban_destinataire", "pays_destinataire", "montant", "devise",
    ]
    try:
        with StringIO(contenu.decode("utf-8"), newline="") as fichier:
            reader = csv.reader(fichier, strict=True)
            if next(reader, None) != colonnes:
                raise ValueError("En-tête incorrect")
            for ligne in reader:
                if len(ligne) != 8 or any(champ.strip() == "" for champ in ligne):
                    raise ValueError("Colonnes manquantes ou incorrectes")
                date, origine, pays, banque, destination, pays_dest, texte, devise = ligne
                datetime.fromisoformat(date)
                if "T" not in date or devise != "EUR":
                    raise ValueError("Date incorrecte ou devise différente de EUR")
                try:
                    montant = Decimal(texte)
                except InvalidOperation as erreur:
                    raise ValueError("Montant non numérique") from erreur
                if not montant.is_finite() or montant < 0:
                    raise ValueError("Montant incorrect")
                with localcontext() as contexte:
                    contexte.prec = max(28, len(montant.as_tuple().digits) + 2)
                    centimes = montant * 100
                if centimes != centimes.to_integral_value():
                    raise ValueError("Montant avec plus de deux décimales")
                if centimes > 9_223_372_036_854_775_807:
                    raise ValueError("Montant trop grand pour SQLite")
                transactions.append(Transaction(
                    datetime_transaction=date, iban_origine=origine,
                    pays_source=pays, banque_source=banque,
                    iban_destinataire=destination, pays_destinataire=pays_dest,
                    montant=int(centimes), devise=devise,
                ))
    except (ValueError, InvalidOperation, csv.Error) as erreur:
        raise ValueError(f"Fichier rejeté : {erreur}") from erreur
    return transactions


def sommes_origines(transactions: list[Transaction]) -> dict[str, int]:
    resultat: dict[str, int] = {}
    for t in transactions:
        iban = t["iban_origine"]
        resultat[iban] = resultat.get(iban, 0) + t["montant"]
    return resultat


def sommes_banques(transactions: list[Transaction]) -> dict[str, int]:
    resultat: dict[str, int] = {}
    for t in transactions:
        banque = t["banque_source"]
        resultat[banque] = resultat.get(banque, 0) + t["montant"]
    return resultat


def sommes_destinataires(transactions: list[Transaction]) -> dict[str, int]:
    resultat: dict[str, int] = {}
    for t in transactions:
        iban = t["iban_destinataire"]
        resultat[iban] = resultat.get(iban, 0) + t["montant"]
    return resultat


def drapeaux(transactions: list[Transaction]) -> list[bool]:
    return [t["montant"] > 500_000 for t in transactions]
