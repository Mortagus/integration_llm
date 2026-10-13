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

## Étape 2 — Implémenter le métier sans LLM

Ajouter les politiques RH, l’offre de poste, les deux candidats exemples et l’agenda fictif donnés dans l’énoncé. Implémenter d’abord les outils déterministes : recherche de créneaux et réservation.

La réservation doit modifier l’agenda en mémoire et refuser un créneau déjà pris ou inexistant.

**Critère de fin :** les tests confirment qu’un créneau est trouvé, réservé, puis indisponible lors d’une seconde tentative.

## Étape 3 — Parsing structuré des CV

Commencer par le CV sous forme de texte ; ajouter l’extraction de texte PDF ensuite. Demander au LLM un résultat conforme à un modèle Pydantic : compétences, années d’expérience, études, score d’adéquation et points de vigilance.

La validation du modèle est obligatoire : une réponse LLM mal formée ne doit pas être retournée comme un succès. Prévoir une erreur lisible ou une stratégie de nouvelle tentative contrôlée.

**Critères de fin :**

- Jean Dupont obtient un score supérieur à 80 et fait ressortir FastAPI et RAG.
- Sophie Martin obtient un score inférieur à 40.
- Une sortie invalide du LLM est détectée.

## Étape 4 — Assistant RH RAG

Indexer au démarrage les quatre politiques RH fournies. À chaque question, rechercher les extraits pertinents, puis les fournir au LLM avec une consigne stricte : répondre uniquement avec ce contexte et signaler toute information absente.

La réponse doit renvoyer les documents ou extraits utilisés afin que l’utilisateur puisse vérifier son origine.

**Critères de fin :** la question sur les RTT et le CET est répondue avec source ; celle sur la prime de naissance est refusée car absente des politiques.

## Étape 5 — Agent et tool calling

Déclarer les fonctions de recherche et de réservation comme outils accessibles au LLM. Gérer une boucle d’agent qui conserve l’historique des messages et réinjecte le résultat de chaque outil avant de poursuivre.

Le scénario attendu est : demande de rendez-vous, recherche de disponibilités, choix/réservation, puis confirmation. L’agent ne doit pas inventer de disponibilité ni confirmer une réservation échouée.

**Critère de fin :** une demande pour Jean Dupont le `2026-10-15` déclenche la recherche puis réserve un créneau disponible.

## Étape 6 — Streaming SSE et interface

Faire diffuser par `/api/agent/chat` des événements SSE distincts : fragment de texte, appel d’outil, résultat d’outil, erreur et fin de réponse. Construire ensuite une interface minimale qui affiche le texte au fil de l’eau ainsi que les actions exécutées.

**Critère de fin :** un utilisateur voit la progression de la réponse et comprend quels outils l’agent a utilisés.

## Étape 7 — Validation finale

Exécuter les trois démonstrations de l’énoncé : parsing des deux CV, réponses RAG fondée et refusée, puis réservation d’entretien. Ajouter des tests unitaires pour les services et des tests API pour les parcours principaux. Les appels LLM, vector store et e-mail doivent être simulés dans les tests.

## Principes à préserver

- Commencer par les composants déterministes, puis brancher le LLM.
- Garder les routes HTTP minces et la logique métier testable.
- Valider toute donnée externe ou générée par le LLM avec Pydantic.
- Ne jamais inventer une règle RH lorsque le contexte RAG est insuffisant.
- Ne jamais versionner de clé API, de CV réel ou de donnée personnelle.
