import csv
from pathlib import Path


def generer(erreur: bool = False) -> None:
    colonnes = [
        "datetime_transaction", "iban_origine", "pays_source", "banque_source",
        "iban_destinataire", "pays_destinataire", "montant", "devise",
    ]
    origines = [
        ("FR7630006000011234567890189", "FR", "BNPPARIBAS"),
        ("DE89370400440532013000", "DE", "COMMERZBANK"),
    ]
    montants = ["1250.00", "7400.50", "5000.00", "25.10", "6100.00", "0.20"]
    for jour in range(1, 4):
        chemin = Path(f"transactions_{jour}.csv")
        if chemin.exists() and not (erreur and jour == 2):
            continue
        with chemin.open("w", newline="", encoding="utf-8") as fichier:
            writer = csv.writer(fichier)
            writer.writerow(colonnes)
            for i, montant in enumerate(montants):
                if erreur and jour == 2 and i == 1:
                    montant = "abc"
                iban, pays, banque = origines[i % 2]
                writer.writerow([
                    f"2024-03-{jour:02d}T{9 + i:02d}:00:00", iban, pays, banque,
                    "ES9121000418450200051332", "ES", montant, "EUR",
                ])


if __name__ == "__main__":
    generer()
