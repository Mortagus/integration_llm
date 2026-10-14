# Audit n°2 — saas_rh

**Destinataire :** Ben
**Date :** 2026-10-14 (après le commit `1f289ac`)
**But :** vérifier que les corrections issues de `AUDIT.md` ont porté leurs fruits (sécurité, bonnes pratiques Python et FastAPI).

## 1. Périmètre et méthode

- **Lu :** `AUDIT.md`, `REPRISE.md`, `PLAN_PROJET.md`, `README.md`, `AGENTS.md`, le PDF de l'énoncé, tout `src/` (sauf les 150 dernières lignes de `app.js`) et `.gitignore`. `app.css` et `index.html` n'ont pas été relus. Les tests ont été balayés par recherche ciblée.
- **Exécuté :** `pytest` (51 réussis, 3 ignorés), `ruff check`, `ruff format --check`, `pip-audit`, `mypy`, un `ruff` étendu, des sondes HTTP avec parseur simulé.
- **Non testé :** appels réels aux fournisseurs LLM, déconnexion réelle d'un navigateur, valeurs du `.env`.

## 2. Verdict

**18 des 25 constats précédents sont réellement corrigés.** Les autres sont acceptés (S-02, S-06, S-07, L-03, C-02), partiels (L-01, D-01, D-02, Q-03) ou touchés par une régression (S-05). Quatre problèmes nouveaux ont été trouvés.

| Axe | Avant | Après audit n°2 |
|---|---|---|
| Conformité à l'exercice | B+ | A− |
| Qualité du code | B | B+ |
| Architecture | B | A− |
| Sécurité applicative | C | B− |
| Sécurité LLM | C+ | B− |
| Données personnelles | C+ | B− |

## 3. Nouveaux constats

| ID | Sévérité | Constat | Preuve |
|---|---|---|---|
| N-01 | Moyen | Régression de S-05 : une erreur fournisseur non rejouable (400, 401, 403) donne une 500. | Sonde : trois codes, trois `500`. |
| N-02 | Moyen | Le masquage des données personnelles supprime les dates d'expérience ; il n'a aucun test. | `03/2019 - 11/2021` devient `[TÉLÉPHONE SUPPRIMÉ]`. |
| N-03 | Moyen | La règle `.gitignore` du PDF personnel est ancrée sur `/saas_rh/…`. | Dans un clone sans dossier `saas_rh`, `cv.pdf` apparaît en `??`. |
| N-04 | Faible | Pas de `max_tokens` sur `parse_structured` OpenAI/Gemini ; aucun timeout client. | `gateway.py`, `application.py`. |
| N-05 | Faible | Typage affaibli par la refonte. | `mypy` : 24 erreurs. |
| N-06 | Faible | Pas de limite de taille de corps avant l'analyse du multipart. | 150 Mo lus en entier avant le 413. |
| N-07 | Info | Les helpers de `tools.py` ne servent plus qu'aux tests (duplication avec la passerelle). | Aucun usage dans `src/`. |

### N-01
La passerelle convertit les erreurs du SDK en `LLMProviderStatusError` (`RuntimeError`). La route `candidates.py` ne capture que `CandidateModelsUnavailableError`, les erreurs brutes des SDK et `ValueError`. Une clé invalide ou un modèle refusé tombe dans la 500 brute, avec traceback dans les logs.
**Correction :** capturer `LLMProviderStatusError` et renvoyer 503, avec un test de route.

### N-02
Le motif téléphone `(?:\d[\s()./-]*){9,15}` avale `01/2015 - 02/2019` (12 chiffres) : les dates disparaissent, donc `years_of_experience` et le score se dégradent. Oublis constatés : nom hors de la première ligne, URL LinkedIn sans libellé, adresse postale sans libellé, `Né à Lyon en 1985, marié`, parenthèse résiduelle sur `(06) 12…`.
**Correction :** exiger un format de téléphone réel, écrire `tests/test_privacy.py`, documenter que c'est une réduction et non une anonymisation.

### N-03
Le README prévoit le cas du clone direct de `saas_rh`, que la règle ancrée ne protège pas. Dans le dépôt actuel, aucun PDF personnel n'est suivi ni présent dans l'historique.
**Correction :** `src/saas_rh/data/candidates/*.pdf` sans préfixe.

### N-04
`REPRISE.md` (S-03) annonce des sorties LLM bornées ; c'est vrai pour Anthropic, RAG et agent, pas pour le parsing Gemini. Sans timeout, un fournisseur figé garde un thread du pool jusqu'à 10 minutes.
**Correction :** `max_tokens=4096` et `timeout=30`.

### N-05
`parse_structured` est typé `-> BaseModel | None` dans le `Protocol` ; `agent/service.py` réutilise le nom `request` pour deux types ; `application.py` réutilise `client` pour OpenAI puis Anthropic.

### N-06
Le 413 est correct mais intervient après réception complète. Acceptable en local ; derrière un proxy, limiter le corps (par exemple 6 Mo).

### N-07
La passerelle reconstruit les définitions d'outils au lieu d'utiliser `openai_interview_tools()` / `anthropic_interview_tools()`.

## 4. Vérification des 25 constats précédents

| Statut | Constats |
|---|---|
| Corrigé et vérifié | Q-01, S-01, S-03 (hors N-04), Q-02, C-01, Q-04, Q-05, Q-06, Q-07, Q-08, Q-09, O-01, A-01, A-02, A-03, S-04 (cas nominal), L-02 (cas nominal), G-01 (hors N-03) |
| Accepté, non corrigé | S-02, S-06, S-07, L-03, C-02 |
| Partiel | L-01, D-01, D-02, Q-03 |
| Régression | S-05 (N-01) |

Vérifié par sonde :
- **Q-01 :** `Cloud Storage` + `Data Averaging` donne 0 (11 avant).
- **S-01 :** `/health` répond en 0,00 s pendant un chat de 4 s (4,1 s avant) ; le flux SSE est correct.
- **S-03 :** texte de 20 001 caractères → 422 ; PDF de 6 Mo → 413 ; faux PDF → 422 ; texte et fichier, ou aucun → 400.
- **Sécurité :** pas de traversée de chemin sur `/static`, pas de CORS ouvert, pas de XSS (`textContent`), aucune clé dans l'historique Git.

Points partiels :
- **L-01 :** le JSON et la consigne d'ignorer les instructions du CV aident, mais rien n'est vérifié côté Python. Une liste de compétences gonflée atteint 100/100. Le `TODO` reste dans `candidates/service.py`.
- **D-01 :** voir N-02.
- **D-02 :** bandeau « à valider par un recruteur » présent ; le prompt n'interdisait pas de citer âge, santé ou origine dans `warning_points`.
- **Q-03 :** « Invitation envoyée à… » suivi de l'avertissement de simulation ; acceptable car imposé par l'énoncé.
- **L-02 :** le refus n'était détecté que par égalité stricte avec `NO_CONTEXT_RESPONSE` ; les distances Chroma restent inutilisées.
- **Non vérifié (S-01) :** comportement à la déconnexion du navigateur pendant un tour d'agent. À tester avec un vrai `uvicorn` et `curl --max-time`.

## 5. Documentation

- Légende de `REPRISE.md` : `[ ]` signifie « accepté hors périmètre », mais S-02, S-06, S-07, C-02 et L-03 étaient cochés `[x]`.
- Compteurs périmés (49 et 48 tests, alors que la suite en compte 51).
- Le README ne disait pas de garder le serveur sur `127.0.0.1` (S-02) ni de ne jamais lancer `chroma run` (S-07), et n'avait pas de section sur le traitement des données.

## 6. Bonnes pratiques

- `pyproject.toml` n'a pas de `[tool.ruff]` : règles par défaut seulement.
- `mypy` ou `pyright` absent du flux de travail.
- `../.env` en `644` et contient un `OPENROUTER_API_KEY` non utilisé par le code.
- `httpx2` (dépendance de dev) est légitime : `openai`, `anthropic` et Starlette l'utilisent.
- `pip-audit` : les mêmes 5 CVE `chromadb 1.5.9`, sans correctif ; risque faible car `PersistentClient` sans serveur.

## 7. Ordre de correction proposé

1. N-03 (`.gitignore`).
2. N-01 avec test de route.
3. N-02 avec `tests/test_privacy.py`.
4. N-04.
5. Variante de refus RAG (L-02) et déconnexion client (à tester à la main).
6. Mise à jour de `REPRISE.md`.

## 8. Statut après corrections (même jour)

N-01, N-02, N-03, N-04, N-05, N-07 et la variante de refus RAG (L-02) sont corrigés ; N-06 est accepté pour un usage local. Vérifications : `pytest` 67 réussis et 3 ignorés, `ruff check` et `ruff format --check` propres (règles étendues), `mypy` sans erreur. Le détail est dans `REPRISE.md`. Restent non vérifiés : la déconnexion du navigateur pendant un tour d'agent et les appels réels aux fournisseurs. Le timeout est de 60 s et non de 30 s comme proposé en section 3.
