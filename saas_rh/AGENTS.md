# Repository Guidelines

## Structure du projet et architecture

Le dépôt ne contient pour l’instant que le cahier des charges. Le projet sera une API Python 3.11+ basée sur FastAPI, organisée comme un monolithe modulaire.

- `src/main.py` : création de l’application FastAPI et enregistrement des routes.
- `src/api/` : routes HTTP et schémas de transport.
- `src/candidates/`, `src/rag/`, `src/agent/`, `src/interviews/` : logique métier par domaine.
- `src/shared/` : configuration et clients LLM/vector store communs.
- `data/` : politiques RH et jeux de données fictifs versionnés.
- `tests/` : tests reflétant la structure de `src/`; `docs/` : choix d’architecture.

Les routes valident l’entrée, appellent un service et traduisent le résultat HTTP. Isolez l’extraction PDF, la recherche vectorielle et la réservation derrière des protocoles testables sans réseau.

## Commandes de développement

Utilisez `uv` comme gestionnaire de dépendances :

```bash
uv sync                                  # installe les dépendances verrouillées
uv run fastapi dev src/main.py            # lance l’API locale
uv run pytest                             # exécute les tests
uv run ruff check . && uv run ruff format --check .  # contrôle le style
```

Documentez les commandes supplémentaires dans `README.md`.

## Conventions Python

Utilisez Python 3.11+, quatre espaces, des annotations de type et des docstrings courtes pour les services métier. Appliquez Ruff; évitez les imports inutilisés et les `Any` non justifiés. Nommez modules, fonctions et variables en `snake_case`, classes et modèles Pydantic en `PascalCase`, et constantes en `UPPER_SNAKE_CASE`.

Définissez des modèles Pydantic explicites pour chaque requête, réponse et sortie LLM. Validez les données aux frontières et ne transformez jamais silencieusement une sortie invalide en succès. Conservez les endpoints du brief : `/api/candidates/parse`, `/api/rag/ask` et `/api/agent/chat`.

## Tests

Écrivez des tests unitaires et API avec `pytest`; nommez-les selon le comportement, par exemple `test_rag_refuse_une_regle_absente_du_contexte`. Couvrez les CV fort/faible match, le RAG sourcé et hors contexte, puis le flux « recherche avant réservation ». Simulez LLM, base vectorielle et e-mail : aucun test ne requiert clé API ou réseau.

## Commits, PR et sécurité

L’historique Git n’existe pas encore. Utilisez des commits impératifs et ciblés, par exemple `Ajoute le schéma de parsing candidat`. Chaque PR décrit le comportement, le besoin lié, les validations effectuées et, pour le streaming ou l’UI, une capture pertinente.

Placez les secrets dans `.env.local` ignoré, versionnez seulement `.env.example`, et ne journalisez jamais CV, adresses e-mail, jetons ni prompts complets. Si le contexte RAG ne répond pas à la question, l’API doit l’indiquer explicitement.
