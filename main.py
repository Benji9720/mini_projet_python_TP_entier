import argparse
import sqlite3
from pathlib import Path

from base import creer_tables, inserer_fichier
from generation import generer


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--erreur", action="store_true")
    arguments = parser.parse_args()
    code = 0
    try:
        generer(arguments.erreur)
        connexion = sqlite3.connect("transactions.db", timeout=0.1)
        try:
            creer_tables(connexion)
            for chemin in sorted(Path(".").glob("*.csv")):
                try:
                    if inserer_fichier(connexion, chemin):
                        print(f"{chemin.name} : importé")
                    else:
                        print(f"{chemin.name} : déjà traité")
                except (ValueError, sqlite3.Error, OSError, OverflowError) as erreur:
                    print(f"{chemin.name} : rejeté ({erreur})")
                    code = 1
            for categorie, identifiant, montant in connexion.execute(
                "SELECT * FROM resultats ORDER BY categorie, identifiant"
            ):
                print(categorie, identifiant, montant, "centimes")
        finally:
            connexion.close()
    except (sqlite3.Error, OSError) as erreur:
        print(f"Erreur : {erreur}")
        return 1
    return code


if __name__ == "__main__":
    raise SystemExit(main())
