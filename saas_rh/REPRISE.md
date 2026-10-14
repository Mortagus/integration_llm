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

## Parsing candidat — terminé

Le DTO existe dans `src/saas_rh/candidates/schemas.py` : `CandidateParseResponse` contient `skills`, `years_of_experience`, `education_level`, `match_score` (0–100) et `warning_points`. Le test TDD de parsing PDF a d'abord échoué sur le statut 501, puis est passé après l'ajout de l'extracteur et du branchement dans la route. Le test unitaire utilise un parseur simulé ; le test fonctionnel opt-in envoie aussi le CV PDF local à l'API réelle quand ce fichier est présent.

## Étape 4 : Assistant RH RAG — terminée

`RAGService` indexe les politiques dans ChromaDB, récupère les passages pertinents et génère une réponse limitée au contexte avec ses sources. Les deux scénarios du PDF sont couverts : réponse sur les RTT et le CET, et abstention sur la prime de naissance absente. La compatibilité de l'appel Anthropic est couverte par un test de régression. Le travail est enregistré dans le commit `1d5415d` (`Ajoute le service RAG sur ChromaDB`).

## Prochaine étape : outils d’entretien et tool calling

Les étapes ci-dessous seront mises à jour et marquées **faites** au fur et à mesure de leur validation.

- [x] **1. Clarifier les contrats des outils** — `InterviewSlotSearchInput` valide une date ; `InterviewReservationInput` valide le nom, la date, l'heure et la forme de l'e-mail du candidat ; `InterviewReservationResult` distingue `SUCCEEDED` de `UNAVAILABLE`. Les heures disponibles de la réponse HTTP sont typées en chaînes (`list[str]`).
- [x] **2. Fiabiliser l’agenda en mémoire** — `InterviewScheduleRepository` travaille sur une copie par processus de l’agenda initial ; il retourne une copie des créneaux disponibles et protège la vérification/réservation par un verrou. `InterviewService` reçoit ce dépôt par injection et est initialisé dans le lifespan FastAPI.
- [x] **3. Tester les outils métier** — `tests/test_interviews_service.py` couvre la recherche d’une date connue ou inconnue, la réservation réussie, le refus d’une seconde réservation, la copie des créneaux et l’isolation entre dépôts. Un test concurrent vérifie qu’une seule réservation du même créneau réussit.
- [x] **4. Relier `GET /api/interviews/slots`** — la route utilise `InterviewService` et les tests API vérifient les créneaux, une date sans disponibilité et les paramètres invalides. `candidate_id` reste obligatoire et positif selon le contrat du PDF, mais n'influence pas la recherche car l'agenda mocké est global et aucune donnée ne relie un identifiant à un candidat.
- [x] **5. Définir les outils exposés au LLM** — `interviews/tools.py` maintient une définition commune de `search_interview_slots` et `reserve_interview_slot`, puis produit les formats OpenAI/Gemini et Anthropic. Les paramètres proviennent des schémas Pydantic ; les descriptions imposent de chercher avant de réserver et de ne pas confirmer un échec. Tests de schéma présents dans `tests/test_interview_tools.py`.
- [x] **6. Préparer le service agent** — `AgentService` reçoit le client LLM et `InterviewService` par injection, conserve l'historique et traite les appels d'outils pour OpenAI/Gemini et Anthropic. Il limite les tours, valide les arguments avec Pydantic et refuse une réservation si le créneau n'a pas été retourné par une recherche précédente. Il est initialisé dans le lifespan et accessible via `get_agent_service`. Les tests unitaires couvrent les deux formats fournisseur, la limite et le garde-fou de réservation.
- [x] **7. Tester le scénario complet avec des dépendances simulées** — `tests/test_agent_scenario.py` simule les réponses du LLM et vérifie, pour OpenAI/Gemini et Anthropic, la recherche le `2026-10-15`, la réservation effective du créneau choisi pour Jean Dupont et le statut `SUCCEEDED` transmis avant confirmation. Aucun e-mail ni appel fournisseur réel n'est effectué par ces tests.

Le tool calling métier est implémenté et testé au niveau de `AgentService`. La route `/api/agent/chat` reste encore un stub ; son raccord au service et l'émission des événements SSE (texte et actions d'outils) constituent l'étape suivante.

## Vérifications parsing à rejouer (facultatif)

Relancer les tests fonctionnels des deux CV texte et du PDF avec Gemini puis Anthropic, vérifier les scores attendus et le basculement entre modèles. Ces appels nécessitent une clé valide pour chaque fournisseur. Si la clé Anthropic n'est pas liée à un workspace, renseigner `ANTHROPIC_WORKSPACE_ID` dans le `.env`.

Le PDF source est à la racine : `Projet SaaS RH & Assistant de Recrutement.pdf`. Le plan complet est dans `PLAN_PROJET.md`.
