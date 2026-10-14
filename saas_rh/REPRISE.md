# Reprise du projet — SaaS RH

## Contexte

Exercice de formation sur l’intégration LLM et RAG. Le projet est une API Python/FastAPI. L’utilisateur souhaite avancer en comprenant et en écrivant lui-même le code ; l’assistant sert de compagnon de développement, explique et guide, sans coder à sa place sauf demande explicite.

## État actuel

- L’étape 0 (environnement FastAPI) est terminée : `uv`, Python 3.11, FastAPI, tests Pytest et Ruff sont en place.
- Les routes principales sont déclarées et testées. `POST /api/agent/chat` diffuse la réponse de l'agent en SSE avec des événements de texte, d'appel d'outil, de résultat d'outil, d'erreur et de fin.
- L’étape 2 (données sources) a été réalisée : politiques RH, offre, CV exemples et agenda sont organisés dans `src/saas_rh/data/`.
- Les textes de l’offre et des deux CV ont été relus après correction des coupures de mots et nettoyage des espaces. Le contenu est cohérent avec le PDF.
- Le service `CandidateParserService` est implémenté dans `src/saas_rh/candidates/service.py`. Il utilise les sorties structurées OpenAI/Gemini ou Anthropic pour extraire les faits du CV, puis calcule lui-même le score avec `calculate_match_score` dans `src/saas_rh/candidates/scoring.py`.
- Le client du fournisseur choisi (`OpenAI` compatible Gemini ou SDK `Anthropic`) est créé pendant le cycle de vie FastAPI et fermé à l'arrêt. La dépendance `get_candidate_parser_service` fournit le `CandidateParserService` à la route via `Depends`.
- Le fournisseur du parsing candidat se choisit avec `LLM_PROVIDER` (`gemini` ou `anthropic`). Le SDK Python Anthropic est installé et son client est construit dans le cycle de vie FastAPI ; les deux fournisseurs utilisent `CandidateParseResponse` en sortie structurée. Les URL, modèles et modèles de repli sont configurés dans le `.env` à la racine du dossier de formation.
- `POST /api/candidates/parse` analyse du texte ou extrait le texte sélectionnable d'un PDF avec `pypdf`. Les PDF scannés sans couche texte ne sont pas encore pris en charge (OCR à prévoir). Sans la clé du fournisseur sélectionné, la route répond 503.
- `CandidateParserService` tente les modèles configurés pour le fournisseur actif dans l'ordre et bascule après des erreurs temporaires ou de modèle indisponible. Si toute la liste échoue, l'exception interne conserve le dernier modèle et le détail fournisseur pour le diagnostic, tandis que la route renvoie un message générique 503 au client. Les tests unitaires couvrent le basculement, l'absence de repli sur une erreur 400 et le rejet d'une sortie structurée absente.
- Le test fonctionnel opt-in vérifie les deux CV : score supérieur à 80 et présence de FastAPI pour Jean Dupont, score inférieur à 40 pour Sophie Martin. Il peut aussi envoyer le PDF local à l'API réelle. Après le remplacement du score LLM par le barème déterministe, l'utilisateur a relancé ce test avec Gemini et en a confirmé le succès.
- La configuration Anthropic accepte `ANTHROPIC_WORKSPACE_ID` et envoie l'en-tête `anthropic-workspace-id` lorsque cette valeur est renseignée. Un test unitaire vérifie la construction du client sans appel réseau.

## Parsing candidat — terminé

Le DTO d'extraction `CandidateParseEvidence` contient les compétences, les années d'expérience générales, le niveau d'études, les points de vigilance et les preuves explicites de leadership. `CandidateParseResponse` expose `skills`, `years_of_experience`, `education_level`, `match_score` (0–100) et `warning_points`.

Le score est déterminé par neuf critères de poids égal : les sept compétences obligatoires de l'offre, l'expérience et le leadership. L'expérience est plafonnée à cinq ans. Python sans version précisée vaut 90 % des points de son critère ; LLM + ChromaDB sans architecture RAG décrite vaut 75 % ; RAG explicitement décrit vaut le maximum. Aucun point de leadership n'est donné sans preuve explicite. Le diplôme est extrait mais ne compte pas, car l'offre ne le demande pas. Pour les éléments connus du CV de Jean, le calcul donne 85/100.

Le calcul pur est couvert dans `tests/test_candidate_scoring.py`, notamment pour Jean, la preuve RAG indirecte ou explicite, Python de base et Python 3.11+. Les tests du service vérifient aussi que le score renvoyé est calculé à partir des faits extraits, plutôt que fourni par le LLM. Le test TDD de parsing PDF a d'abord échoué sur le statut 501, puis est passé après l'ajout de l'extracteur et du branchement dans la route. Le test fonctionnel opt-in envoie aussi le CV PDF local à l'API réelle quand ce fichier est présent.

## Étape 4 : Assistant RH RAG — terminée

`RAGService` indexe les politiques dans ChromaDB, récupère les passages pertinents et génère une réponse limitée au contexte avec ses sources. Les deux scénarios du PDF sont couverts : réponse sur les RTT et le CET, et abstention sur la prime de naissance absente. La compatibilité de l'appel Anthropic est couverte par un test de régression. Le travail est enregistré dans le commit `1d5415d` (`Ajoute le service RAG sur ChromaDB`).

## Outils d’entretien et tool calling — terminés

Les étapes ci-dessous seront mises à jour et marquées **faites** au fur et à mesure de leur validation.

- [x] **1. Clarifier les contrats des outils** — `InterviewSlotSearchInput` valide une date ; `InterviewReservationInput` valide le nom, la date, l'heure et la forme de l'e-mail du candidat ; `InterviewReservationResult` distingue `SUCCEEDED` de `UNAVAILABLE`. Les heures disponibles de la réponse HTTP sont typées en chaînes (`list[str]`).
- [x] **2. Fiabiliser l’agenda en mémoire** — `InterviewScheduleRepository` travaille sur une copie par processus de l’agenda initial ; il retourne une copie des créneaux disponibles et protège la vérification/réservation par un verrou. `InterviewService` reçoit ce dépôt par injection et est initialisé dans le lifespan FastAPI.
- [x] **3. Tester les outils métier** — `tests/test_interviews_service.py` couvre la recherche d’une date connue ou inconnue, la réservation réussie, le refus d’une seconde réservation, la copie des créneaux et l’isolation entre dépôts. Un test concurrent vérifie qu’une seule réservation du même créneau réussit.
- [x] **4. Relier `GET /api/interviews/slots`** — la route utilise `InterviewService` et les tests API vérifient les créneaux, une date sans disponibilité et les paramètres invalides. `candidate_id` reste obligatoire et positif selon le contrat du PDF, mais n'influence pas la recherche car l'agenda mocké est global et aucune donnée ne relie un identifiant à un candidat.
- [x] **5. Définir les outils exposés au LLM** — `interviews/tools.py` maintient une définition commune de `search_interview_slots` et `reserve_interview_slot`, puis produit les formats OpenAI/Gemini et Anthropic. Les paramètres proviennent des schémas Pydantic ; les descriptions imposent de chercher avant de réserver et de ne pas confirmer un échec. Tests de schéma présents dans `tests/test_interview_tools.py`.
- [x] **6. Préparer le service agent** — `AgentService` reçoit le client LLM et `InterviewService` par injection, conserve l'historique et traite les appels d'outils pour OpenAI/Gemini et Anthropic. Il limite les tours, valide les arguments avec Pydantic et refuse une réservation si le créneau n'a pas été retourné par une recherche précédente. Il est initialisé dans le lifespan et accessible via `get_agent_service`. Les tests unitaires couvrent les deux formats fournisseur, la limite et le garde-fou de réservation.
- [x] **7. Tester le scénario complet avec des dépendances simulées** — `tests/test_agent_scenario.py` simule les réponses du LLM et vérifie, pour OpenAI/Gemini et Anthropic, la recherche le `2026-10-15`, la réservation effective du créneau choisi pour Jean Dupont et le statut `SUCCEEDED` transmis avant confirmation. Aucun e-mail ni appel fournisseur réel n'est effectué par ces tests.
- [x] **8. Relier `POST /api/agent/chat` et diffuser les événements SSE** — la route transmet le message à `AgentService` et diffuse les fragments texte, appels et résultats d'outils, puis l'événement `done`. En cas de problème, elle diffuse `error` puis `done` avec le statut d'erreur. Les tests simulés couvrent les événements de route ainsi que le streaming OpenAI et Anthropic, sans appel réseau.

## Interface web et validation finale

L'interface est implémentée et a été testée manuellement par l'utilisateur. Elle présente les quatre parcours : parsing candidat, assistant RH RAG, consultation de l'agenda et chat de l'agent. Les résultats sont affichés avec une présentation adaptée à chaque parcours ; le chat rend visibles le texte en streaming et les actions de l'agent.

La dernière suite automatisée standard exécutée après le traitement de S-05 a donné **49 tests réussis, 3 ignorés**. Les trois tests ignorés sont fonctionnels et opt-in : ils nécessitent un serveur local et des appels réels au fournisseur LLM. Les changements ultérieurs de Q-03 et D-01 restent à valider par une prochaine exécution. Les tests RAG fonctionnels avaient réussi lors d'une précédente exécution opt-in ; après le changement de calcul, le test de parsing candidat a été relancé avec Gemini et l'utilisateur en a confirmé le succès.

Les trois démonstrations fonctionnelles du PDF restent les scénarios de référence : parsing des deux CV, question RAG répondue puis refusée, et recherche/réservation d'un entretien. Les tests fonctionnels réels n'ont pas été activés lors de la validation standard ; ils restent à exécuter séparément si l'on souhaite vérifier l'intégration avec le fournisseur configuré.

Le PDF évoque aussi l'envoi d'invitations et la mise à jour des statuts candidats dans la description générale de l'agent. Le scénario de validation demandé se limite à la recherche et à la réservation, et ces fonctions supplémentaires ne sont pas implémentées.

## Vérifications parsing à rejouer (facultatif)

La validation fonctionnelle opt-in avec Gemini est réussie pour le parsing candidat et le RAG. La bascule entre modèles n'a pas été vérifiée et n'est pas requise pour clôturer cette étape. Si la clé Anthropic n'est pas liée à un workspace, renseigner `ANTHROPIC_WORKSPACE_ID` dans le `.env`.

Le PDF source est à la racine : `Projet SaaS RH & Assistant de Recrutement.pdf`. Le plan complet est dans `PLAN_PROJET.md`.

## Suivi des constats de `AUDIT.md`

Les points sont conservés dans l'ordre de priorité établi après la revue. `[x]` signifie que le traitement indiqué est implémenté ; `[ ]` signifie qu'il reste à traiter, qu'il est partiel ou qu'il a été accepté hors périmètre. Les notes précisent ces cas.

### À prendre au sérieux, même pour l’exercice

- [x] **Q-01 — Faux positifs dans le score** : correspondances par mots entiers et test de régression, pour éviter par exemple que « Storage » corresponde à « RAG ».
- [x] **S-01 — Boucle bloquante pendant le chat** : itération du générateur synchrone dans un thread pour ne pas bloquer la boucle d’événements.
- [x] **S-03 — Absence de limites** : limites ajoutées pour le texte et les PDF candidats, les questions RAG, les messages et l’historique de l’agent, ainsi que les sorties LLM.
- [ ] **L-01 — CV contrôlé par le candidat envoyé au LLM** : atténuation partielle. Le prompt précise que le CV est une donnée non fiable et le transmet comme contenu délimité ; aucune vérification indépendante des faits extraits n’est mise en place, faute de source de vérité. Le score doit rester interprété comme une estimation fondée sur l’extraction du modèle.
- [x] **Q-02 — Diplôme obligatoire** : le niveau d’études est facultatif ; le modèle doit renvoyer `null` si le CV ne le précise pas.
- [x] **S-04 — Message d’erreur fournisseur renvoyé au client** : la route renvoie une erreur générique ; le détail fournisseur reste dans l’exception interne et les journaux contrôlés.
- [x] **Q-03 — « Invitation envoyée »** : formulation exigée par l’exercice conservée, avec la précision qu’il s’agit d’une simulation et qu’aucun e-mail réel n’a été envoyé.

### Importants seulement si le projet est exposé ou utilisé en conditions réelles

- [ ] **S-02 — Pas d’authentification ni de limitation de débit** : explicitement hors périmètre retenu ; le projet est un exercice local de formation et n’est pas destiné à être exposé publiquement.
- [x] **D-01 — Données personnelles envoyées au fournisseur** : masquage de données personnelles courantes avant l’appel LLM. Le masquage repose sur des motifs et ne garantit pas l’anonymisation de tout texte libre ; utiliser des CV fictifs pour l’exercice.
- [ ] **D-02 — Score et libellé de verdict** : le score reste indicatif et le libellé de verdict n’a pas été modifié.
- [ ] **L-03 — Historique falsifiable par le client** : la taille de l’historique est bornée dans S-03, mais son contenu fourni par le client reste falsifiable.
- [ ] **S-06 — Documentation et en-têtes HTTP** : pas de changement ; l’accès à `/docs` est conservé pour l’exercice local.
- [ ] **S-07 — CVE ChromaDB** : point laissé en veille ; le statut des avis n’a pas été vérifié dans ce suivi.

### À arbitrer selon l’énoncé ou à classer comme amélioration

- [ ] **C-01 — Indexation RAG au démarrage** : conflit documentaire non arbitré. `PLAN_PROJET.md` demande l’indexation au démarrage, tandis que `AGENTS.md` décrit l’indexation à la première question.
- [ ] **L-02 — Sources affichées après un refus** : comportement non modifié ; aucun seuil de distance n’a été calibré.
- [x] **S-05 — Erreurs incohérentes** : erreurs d’intégration rendues explicites dans les routes (statuts HTTP adaptés et messages génériques) ; les échecs survenant après le début du streaming restent signalés par un événement SSE `error`.
- [ ] **Q-05 — `assert` dans les routes** : amélioration non appliquée.
- [ ] **Q-06 — Tests des routes appelés directement** : couverture HTTP via client de test à compléter.
- [ ] **Q-07 — Formatage Ruff** : vérification et corrections à faire.
- [ ] **O-01 — Erreurs du chat sans trace serveur** : journalisation des erreurs inattendues du chat à compléter.
- [ ] **G-01 — `.gitignore`** : nettoyage non appliqué.
- [ ] **Q-04 — Configuration au démarrage** : amélioration non appliquée.
- [ ] **Q-08 — Code mort** : nettoyage non appliqué.
- [ ] **Q-09 — Fallback et température** : amélioration non appliquée.
- [ ] **A-01/A-02 — Abstraction des SDK et refactor de `main.py`** : améliorations de maintenance non appliquées.
- [ ] **A-03 — Cohérence des dépendances** : vérification non appliquée.
- [ ] **C-02 — Noms des outils, formats et fonctionnalités non implémentées** : pas de changement ; à rouvrir seulement si l’évaluation exige les noms exacts, l’envoi d’invitations ou la mise à jour des statuts.
