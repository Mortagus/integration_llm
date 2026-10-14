# Reprise du projet — SaaS RH

## Contexte

Exercice de formation sur l’intégration LLM et RAG. Le projet est une API Python/FastAPI. L’utilisateur souhaite avancer en comprenant et en écrivant lui-même le code ; l’assistant sert de compagnon de développement, explique et guide, sans coder à sa place sauf demande explicite.

## État actuel

- L’étape 0 (environnement FastAPI) est terminée : `uv`, Python 3.11, FastAPI, tests Pytest et Ruff sont en place.
- Les routes principales sont déclarées et les tests simples ont été ajoutés, notamment le test SSE minimal.
- L’étape 2 (données sources) a été réalisée : politiques RH, offre, CV exemples et agenda sont organisés dans `src/saas_rh/data/`.
- Les textes de l’offre et des deux CV ont été relus après correction des coupures de mots et nettoyage des espaces. Le contenu est cohérent avec le PDF.
- Le service `CandidateParserService` est implémenté dans `src/saas_rh/candidates/service.py`. Il utilise `chat.completions.parse` et `CandidateParseResponse` pour extraire le profil à partir du CV texte.
- Le client du fournisseur choisi (`OpenAI` compatible Gemini ou SDK `Anthropic`) est créé pendant le cycle de vie FastAPI et fermé à l'arrêt. La dépendance `get_candidate_parser_service` fournit le `CandidateParserService` à la route via `Depends`.
- Le fournisseur du parsing candidat se choisit avec `LLM_PROVIDER` (`gemini` ou `anthropic`). Le SDK Python Anthropic est installé et son client est construit dans le cycle de vie FastAPI ; les deux fournisseurs utilisent `CandidateParseResponse` en sortie structurée. Les URL, modèles et modèles de repli sont configurés dans le `.env` à la racine du dossier de formation.
- `POST /api/candidates/parse` analyse du texte ou extrait le texte sélectionnable d'un PDF avec `pypdf`. Les PDF scannés sans couche texte ne sont pas encore pris en charge (OCR à prévoir). Sans la clé du fournisseur sélectionné, la route répond 503.
- `CandidateParserService` tente les modèles configurés pour le fournisseur actif dans l'ordre et bascule après des erreurs temporaires ou de modèle indisponible. Si toute la liste échoue, l'erreur 503 contient le nom du dernier modèle tenté et le message renvoyé par le fournisseur. Les tests unitaires couvrent ce message, le basculement, l'absence de repli sur une erreur 400 et le rejet d'une sortie structurée absente.
- Le test fonctionnel opt-in vérifie maintenant les deux CV : score supérieur à 80 et présence de FastAPI pour Jean Dupont, score inférieur à 40 pour Sophie Martin. Ce parcours réel n'a pas encore été rejoué après son extension.
- La configuration Anthropic accepte `ANTHROPIC_WORKSPACE_ID` et envoie l'en-tête `anthropic-workspace-id` lorsque cette valeur est renseignée. Un test unitaire vérifie la construction du client sans appel réseau.

## Étape en cours : validation fonctionnelle du parsing

Le DTO existe dans `src/saas_rh/candidates/schemas.py` : `CandidateParseResponse` contient `skills`, `years_of_experience`, `education_level`, `match_score` (0–100) et `warning_points`. Le test TDD de parsing PDF a d'abord échoué sur le statut 501, puis est passé après l'ajout de l'extracteur et du branchement dans la route. Le test unitaire utilise un parseur simulé ; le test fonctionnel opt-in envoie aussi le CV PDF local à l'API réelle quand ce fichier est présent.

## Prochaine reprise

1. Renseigner `ANTHROPIC_WORKSPACE_ID` dans le `.env` si la clé Anthropic n'est pas liée à un workspace, puis relancer le test fonctionnel avec Gemini puis Anthropic et vérifier les résultats des deux CV ainsi que le basculement entre modèles. Une clé `ANTHROPIC_API_KEY` valide doit être disponible pour Anthropic.
2. Rejouer le parsing réel des deux CV texte et le nouveau flux PDF avec Gemini puis Anthropic ; vérifier les scores attendus et le basculement entre modèles. Ces appels fonctionnels nécessitent une clé valide pour chaque fournisseur.

Le PDF source est à la racine : `Projet SaaS RH & Assistant de Recrutement.pdf`. Le plan complet est dans `PLAN_PROJET.md`.
