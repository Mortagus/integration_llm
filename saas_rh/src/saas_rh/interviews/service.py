from saas_rh.interviews.mock_data import AGENDA_RECRUTEUR


def rechercher_creneaux_entretien(date: str) -> list[str]:
    """Retourne les heures disponibles pour une date donnée."""
    return AGENDA_RECRUTEUR.get(date, [])


def reserver_entretien(
        candidat_nom: str,
        date: str,
        heure: str,
        email: str,
) -> dict:
    """Réserve un créneau et confirme la réservation."""
    if date in AGENDA_RECRUTEUR and heure in AGENDA_RECRUTEUR[date]:
        AGENDA_RECRUTEUR[date].remove(heure)
        return {
            "statut": "SUCCES",
            "message": f"Entretien confirmé pour {candidat_nom} le {date} à {heure}. Invitation envoyée à {email}.",
        }

    return {
        "statut": "ERREUR",
        "message": "Créneau indisponible.",
    }
