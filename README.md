# Formation « Développement IA » — intégration de LLM

Ce dépôt rassemble le travail de la formation sur l'intégration de LLM.

## Projet principal : SaaS RH

Le projet final est dans le dossier [`saas_rh/`](saas_rh/) : une API FastAPI d'assistant de recrutement (parsing de CV, assistant RH RAG, agent de planification d'entretiens avec streaming SSE) et son interface web.

**Pour l'installer, le lancer et le tester, voir [`saas_rh/README.md`](saas_rh/README.md).** Sans clé API, l'application démarre et les tests passent ; seules les routes qui appellent un LLM ont besoin d'une clé.

Les documents de suivi sont dans `saas_rh/` : `PLAN_PROJET.md` (plan), `REPRISE.md` (avancement), `AUDIT.md` et `AUDIT_2.md` (revues de sécurité et de qualité).

## Exercices de cours

Le dossier [`exercices/`](exercices/) contient les exemples, exercices et corrections intermédiaires de la formation (`example_*.py`, `exemple_rag_1.py`, `exercice_*.py`, `llm_service.py`, `rag_indexer.py`, `main.py`). Ils ne font pas partie du projet final. Ils lisent leurs clés dans un fichier `.env` local, non versionné, et se lancent depuis ce dossier (`main.py` importe `exercice_1.py`, qui importe `llm_service.py`).

Ces scripts n'ont pas de fichier de dépendances propre : leurs bibliothèques (`openai`, `chromadb`, `python-dotenv`, `pydantic`) sont celles installées par `uv sync` dans `saas_rh/`, et `exercice_2.py` utilise aussi `EmailStr`, qui demande `email-validator`.
