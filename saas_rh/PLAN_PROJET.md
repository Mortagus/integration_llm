# Plan de mise en œuvre — SaaS RH et assistant de recrutement

Ce document découpe l’exercice en étapes indépendantes et vérifiables. L’objectif est de démontrer l’intégration d’un LLM, d’un RAG, du tool calling et du streaming SSE sans mélanger les responsabilités trop tôt.

## Objectif du projet

Construire une API Python/FastAPI capable de :

1. Extraire un profil candidat structuré depuis un CV texte ou PDF.
2. Répondre aux questions RH uniquement à partir de politiques internes indexées.
3. Planifier un entretien grâce à un agent qui appelle des outils métier.
4. Diffuser les réponses et les actions de l’agent en streaming SSE.

## Étape 0 — Préparer l’environnement FastAPI

Cette étape sert à créer un point de départ sain avant d’écrire une route. Installer Python 3.11+ et utiliser `uv` pour créer et isoler l’environnement du projet. Initialiser ensuite le manifeste `pyproject.toml`, puis ajouter FastAPI, Uvicorn, Pytest et Ruff.

Vérifier les bases : démarrer une application FastAPI minimale, ouvrir sa documentation interactive à l’adresse `/docs`, et exécuter un premier test. Ne pas encore intégrer de LLM, de base vectorielle ou de PDF.

À ce stade, comprendre le rôle de chaque élément : FastAPI reçoit les requêtes HTTP, Uvicorn exécute le serveur ASGI, Pydantic valide les données et Pytest vérifie le comportement.

**Critère de fin :** le projet possède un environnement reproductible, une application qui démarre localement, la page `/docs` accessible et un test qui passe.

## Étape 1 — Cadrer les contrats

Définir les routes et leurs modèles Pydantic avant d’implémenter les intégrations :

- `POST /api/candidates/parse`
- `POST /api/rag/ask`
- `POST /api/agent/chat`
- `GET /api/interviews/slots`

Prévoir des schémas explicites pour le profil candidat, les sources RAG, les résultats de réservation et les événements SSE.

**Critère de fin :** les requêtes, réponses et cas d’erreur sont documentés avec des exemples JSON, même si les premières routes utilisent des réponses fictives.

## Étape 2 — Rassembler les données sources

Rassembler les données sources fournies dans l’énoncé : politiques RH, offre de poste, deux candidats exemples et agenda fictif. Les organiser par domaine dans `src/saas_rh/data/`, sous forme de constantes Python. Cette étape ne comprend pas encore les fonctions de recherche ou de réservation.

**Critère de fin :** les quatre politiques, l’offre, les deux CV exemples et les créneaux de l’agenda sont présents, lisibles et fidèles à l’énoncé.

## Étape 3 — Parsing structuré des CV

Commencer par le CV sous forme de texte ; ajouter l’extraction de texte PDF ensuite. Demander au LLM un résultat conforme à un modèle Pydantic contenant les faits extraits du CV : compétences, années d’expérience, études, indices de leadership et points de vigilance. Le LLM ne décide pas du score : un calcul Python déterministe applique le barème à ces faits.

Le barème initial attribue un poids égal aux sept compétences obligatoires de l’offre, à l’expérience et au leadership. Les années d’expérience sont plafonnées au seuil demandé de cinq ans. Une mention professionnelle de Python sans version vaut 90 % des points du critère ; une simple notion de Python vaut 25 %. L’association LLM + ChromaDB sans description RAG vaut 75 % ; une architecture RAG explicitement décrite vaut le maximum. Le leadership ne rapporte des points qu’avec une preuve explicite. Le niveau d’études reste extrait, mais n’entre pas dans le score car l’offre n’impose pas de diplôme.

La validation du modèle est obligatoire : une réponse LLM mal formée ne doit pas être retournée comme un succès. Prévoir une erreur lisible ou une stratégie de nouvelle tentative contrôlée.

**Critères de fin :**

- Jean Dupont obtient un score supérieur à 80 et fait ressortir FastAPI et RAG.
- Sophie Martin obtient un score inférieur à 40.
- Une sortie invalide du LLM est détectée.

**État : implémenté.** Le calcul du score est isolé dans une fonction pure et couvert par des tests déterministes. Pour les éléments connus du CV de Jean, le barème produit 85/100. Le test fonctionnel opt-in avec Gemini a ensuite été relancé par l'utilisateur et est passé.

## Étape 4 — Assistant RH RAG

Indexer au démarrage les quatre politiques RH fournies. À chaque question, rechercher les extraits pertinents, puis les fournir au LLM avec une consigne stricte : répondre uniquement avec ce contexte et signaler toute information absente.

La réponse doit renvoyer les documents ou extraits utilisés afin que l’utilisateur puisse vérifier son origine.

**Critères de fin :** la question sur les RTT et le CET est répondue avec source ; celle sur la prime de naissance est refusée car absente des politiques.

## Étape 5 — Outils déterministes d’entretien

Implémenter les fonctions de recherche et de réservation à partir de l’agenda fictif. Garder les données initiales dans `data/` et gérer l’état modifiable de l’agenda en mémoire. La réservation doit refuser un créneau absent ou déjà pris.

**Critère de fin :** les tests confirment qu’un créneau est trouvé, réservé, puis indisponible lors d’une seconde tentative.

## Étape 6 — Agent et tool calling

Déclarer les fonctions de recherche et de réservation comme outils accessibles au LLM. Gérer une boucle d’agent qui conserve l’historique des messages et réinjecte le résultat de chaque outil avant de poursuivre.

Le scénario attendu est : demande de rendez-vous, recherche de disponibilités, choix/réservation, puis confirmation. L’agent ne doit pas inventer de disponibilité ni confirmer une réservation échouée.

**Critère de fin :** une demande pour Jean Dupont le `2026-10-15` déclenche la recherche puis réserve un créneau disponible.

## Étape 7 — Streaming SSE et interface

Faire diffuser par `/api/agent/chat` des événements SSE distincts : fragment de texte, appel d’outil, résultat d’outil, erreur et fin de réponse. Construire ensuite une interface minimale qui affiche le texte au fil de l’eau ainsi que les actions exécutées.

**Critère de fin :** un utilisateur voit la progression de la réponse et comprend quels outils l’agent a utilisés.

**État : terminé.** L'application propose une interface web avec un écran d'accueil et un parcours par pilier : parsing candidat, assistant RH RAG, consultation des créneaux et chat de l'agent. Les réponses sont présentées sous une forme adaptée à chaque parcours ; le chat affiche les événements SSE et les actions de l'agent.

## Étape 8 — Validation finale

Exécuter les trois démonstrations de l’énoncé : parsing des deux CV, réponses RAG fondée et refusée, puis réservation d’entretien. Ajouter des tests unitaires pour les services et des tests API pour les parcours principaux. Les appels LLM, vector store et e-mail doivent être simulés dans les tests.

**État : validation réussie.** Après l'ajout du calcul déterministe du score, `uv run pytest` a donné **48 tests réussis et 3 ignorés**. Les tests ignorés sont les tests fonctionnels opt-in qui nécessitent un serveur local et des appels LLM réels ; le test de parsing candidat a ensuite été relancé avec Gemini et confirmé comme réussi par l'utilisateur. Les tests fonctionnels RAG avaient aussi réussi lors d'une précédente exécution opt-in. L'interface a été vérifiée manuellement par l'utilisateur.

## Principes à préserver

- Commencer par les composants déterministes, puis brancher le LLM.
- Garder les routes HTTP minces et la logique métier testable.
- Valider toute donnée externe ou générée par le LLM avec Pydantic.
- Ne jamais inventer une règle RH lorsque le contexte RAG est insuffisant.
- Ne jamais versionner de clé API, de CV réel ou de donnée personnelle.
