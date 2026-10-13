# Reprise du projet — SaaS RH

## Contexte

Exercice de formation sur l’intégration LLM et RAG. Le projet est une API Python/FastAPI. L’utilisateur souhaite avancer en comprenant et en écrivant lui-même le code ; l’assistant sert de compagnon de développement, explique et guide, sans coder à sa place sauf demande explicite.

## État actuel

- L’étape 0 (environnement FastAPI) est terminée : `uv`, Python 3.11, FastAPI, tests Pytest et Ruff sont en place.
- Les routes principales sont déclarées et les tests simples ont été ajoutés, notamment le test SSE minimal.
- L’étape 2 (données sources) a été réalisée : politiques RH, offre, CV exemples et agenda sont organisés dans `src/saas_rh/data/`.
- Les textes de l’offre et des deux CV ont été relus après correction des coupures de mots et nettoyage des espaces. Le contenu est cohérent avec le PDF.
- Le dépôt était propre avant la création de ce fichier de reprise.

## Étape en cours : parsing structuré des CV

Le DTO existe déjà dans `src/saas_rh/candidates/schemas.py` : `CandidateParseResponse` contient `skills`, `years_of_experience`, `education_level`, `match_score` (0–100) et `warning_points`. Il correspond aux champs demandés dans l’énoncé ; il n’est pas nécessaire de redéfinir le contrat.

La route `POST /api/candidates/parse`, dans `src/saas_rh/api/routers/candidates.py`, valide qu’on fournit exactement un texte ou un fichier, puis renvoie encore une erreur 501. Le parsing métier n’est donc pas implémenté. Le plan prévoit de commencer par le CV texte, puis d’ajouter l’extraction PDF.

## Prochaine reprise

1. Parcourir les exercices Python du dossier parent (`../exercice_*.py`, corrections, `../llm_service.py`) pour retrouver les approches déjà vues en formation.
2. S’appuyer sur ces exemples pour concevoir le service de parsing, sans surarchitecturer la couche FastAPI.
3. Clarifier le fournisseur/modèle LLM disponible et la façon dont les exercices garantissent une sortie structurée validable par Pydantic.
4. Avancer d’abord sur le traitement de `cv_text`, puis prévoir les tests attendus par le PDF : Jean Dupont score > 80 avec FastAPI/RAG ; Sophie Martin score < 40 ; réponse LLM invalide détectée.

Le PDF source est à la racine : `Projet SaaS RH & Assistant de Recrutement.pdf`. Le plan complet est dans `PLAN_PROJET.md`.
