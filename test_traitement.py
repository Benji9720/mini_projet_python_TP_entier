from traitement import Transaction, drapeaux, sommes_banques, sommes_destinataires, sommes_origines


def transaction(montant: int, origine: str, banque: str, destination: str) -> Transaction:
    return Transaction(
        datetime_transaction="2024-03-01T09:00:00", iban_origine=origine,
        pays_source="FR", banque_source=banque, iban_destinataire=destination,
        pays_destinataire="DE", montant=montant, devise="EUR",
    )


def test_sommes() -> None:
    donnees = [
        transaction(10, "FR1", "A", "DE1"),
        transaction(20, "FR1", "A", "DE2"),
        transaction(600_000, "FR2", "A", "DE1"),
        transaction(100, "FR2", "B", "DE1"),
    ]
    copie = [t.copy() for t in donnees]
    assert sommes_origines(donnees) == {"FR1": 30, "FR2": 600_100}
    assert sommes_banques(donnees) == {"A": 600_030, "B": 100}
    assert sommes_destinataires(donnees) == {"DE1": 600_110, "DE2": 20}
    assert donnees == copie


def test_drapeaux() -> None:
    donnees = [transaction(m, "FR1", "A", "DE1") for m in [499_999, 500_000, 500_001]]
    copie = [t.copy() for t in donnees]
    assert drapeaux(donnees) == [False, False, True]
    assert donnees == copie


def test_vide() -> None:
    assert sommes_origines([]) == {}
    assert sommes_banques([]) == {}
    assert sommes_destinataires([]) == {}
    assert drapeaux([]) == []
