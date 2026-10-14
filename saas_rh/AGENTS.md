# Consignes du dépôt SaaS RH

## Architecture

Ce projet de formation est une API Python 3.11+ avec FastAPI, structurée en domaines.

- `src/saas_rh/main.py` crée l’application, configure les clients partagés dans le lifespan FastAPI et enregistre les routeurs.
- `src/saas_rh/api/routers/` contient les routes HTTP. Elles valident les entrées, appellent un service fourni par `Depends` et traduisent les erreurs métier en réponses HTTP.
- `src/saas_rh/api/dependencies.py` fournit aux routes les services conservés dans `app.state`.
- `src/saas_rh/candidates/`, `src/saas_rh/rag/` et `src/saas_rh/interviews/` contiennent les schémas et la logique de leur domaine. Les SDK LLM, ChromaDB et les autres dépendances externes sont injectés dans les services.
- `src/saas_rh/data/` contient les politiques RH, les CV fictifs et les créneaux fictifs. Garder les données dans ces modules et la logique dans les domaines correspondants.
- `tests/` contient les tests par domaine et parcours.

Consulter `PLAN_PROJET.md` pour les objectifs et critères fonctionnels. Consulter `REPRISE.md` en début de session ou après une interruption pour retrouver l’avancement. Garder ce document comme source de suivi ; le mettre à jour au point de reprise de fin de journée ou lorsque l’utilisateur le demande, pas à chaque modification.

## LLM et configuration

`LLM_PROVIDER` sélectionne `gemini` ou `anthropic`. Le lifespan crée un client partagé, le transmet aux services et le ferme à l’arrêt. Les routes récupèrent les services via les dépendances FastAPI ; ne créez pas de client LLM dans une route ou à chaque requête.

Les clés et réglages locaux sont chargés depuis l’environnement ou le `.env` ignoré à la racine du dossier de formation. Ne jamais afficher, journaliser, versionner ou copier une clé. Les PDF personnels placés dans `src/saas_rh/data/candidates/` sont également ignorés par Git ; les tests doivent pouvoir fonctionner sans eux.

## Parsing candidat

`CandidateParserService` produit `CandidateParseResponse` à partir d’un CV texte. La route `/api/candidates/parse` accepte exactement un champ `cv_text` ou un fichier `cv_file`. Pour un PDF, `CandidatePdfTextExtractor` extrait le texte sélectionnable avant l’appel au parseur ; un PDF sans texte lisible reçoit une erreur explicite. Les tests ordinaires utilisent un parseur simulé. Le test fonctionnel opt-in peut appeler un vrai fournisseur LLM et le serveur local.

## RAG

`RAGService` indexe les politiques de `data/rag/mock_data.py` au démarrage de l’application dans une collection ChromaDB persistante avec des identifiants stables et `upsert`, puis recherche les passages utiles et demande au LLM une réponse limitée à ce contexte. La réponse `RagAskResponse` contient le texte et les sources retrouvées. Le dossier `.chroma/` est local et ignoré par Git. Le premier indexage peut télécharger le modèle d’embedding par défaut de ChromaDB.

Conserver les sources avec chaque passage jusqu’à la réponse HTTP. Si le contexte ne permet pas de répondre, l’assistant doit le dire et ne pas inventer de politique. Tester cette règle avec une question couverte et une question absente des politiques.

## Conventions et commandes

Utiliser `uv` pour gérer l’environnement et les dépendances. Depuis le dossier `saas_rh` :

```bash
uv sync
uv run uvicorn saas_rh.main:app --reload
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Les tests unitaires et API ne doivent pas appeler de fournisseur LLM ni dépendre d’un modèle d’embedding téléchargé. Simuler les clients LLM et la collection vectorielle aux tests ; réserver les appels réels aux tests fonctionnels opt-in. Tester les routes via leurs contrats observables et les services via leur interface publique.

Utiliser des annotations Python, des schémas Pydantic explicites et des noms `snake_case` pour modules, fonctions et variables, `PascalCase` pour classes. Ne pas transformer une sortie invalide ou une erreur d’intégration en succès.

## Sécurité et données

Ne jamais journaliser de CV, d’adresse e-mail, de clé, de jeton, de prompt complet ou de réponse contenant des données personnelles. Ne jamais versionner de secret ni de CV personnel. Garder dans Git les données fictives prévues pour les tests et les exemples.
