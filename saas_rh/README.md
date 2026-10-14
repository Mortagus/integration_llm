# SaaS RH — Assistant de recrutement

Projet de formation « Développement IA » : une application RH qui combine extraction structurée de CV, recherche documentaire RAG et agent conversationnel avec appel d'outils.

## Objectifs

Le projet reprend les quatre piliers et les scénarios de validation du cahier des charges PDF :

1. **Parsing de CV** — extraire les compétences, l'expérience, la formation et les points de vigilance depuis du texte ou un PDF. Le LLM extrait les faits ; un calcul Python déterministe évalue l'adéquation au poste.
2. **Assistant RH RAG** — interroger les politiques RH, obtenir une réponse sourcée et refuser de répondre lorsqu'une information n'est pas documentée.
3. **Agent de planification** — rechercher et réserver un créneau d'entretien à l'aide d'outils métier. L'agenda est fictif et conservé en mémoire.
4. **Interface conversationnelle** — utiliser les parcours depuis une page web et suivre en temps réel la réponse de l'agent et les outils appelés grâce au streaming SSE.

Le scénario de démonstration couvre les deux CV exemples, les questions sur les RTT/CET et la prime de naissance, ainsi que la recherche et la réservation d'un entretien. L'envoi d'invitations et la mise à jour des statuts candidats sont hors du périmètre actuel.

## Stack technique

- **Python 3.11+**, **uv** pour l'environnement et les dépendances.
- **FastAPI** et **Uvicorn** pour l'API HTTP et le serveur local ; **Pydantic** pour valider les données et les sorties structurées.
- **Google Gemini** via le SDK **OpenAI** en mode compatible, ou **Anthropic** via son SDK Python. Le fournisseur se choisit par configuration.
- **ChromaDB** pour la base vectorielle persistante du RAG ; **pypdf** pour extraire le texte des PDF.
- **HTML, CSS et JavaScript** pour l'interface, servie par FastAPI ; **SSE** pour le chat en streaming.
- **Pytest** pour les tests et **Ruff** pour le lint.

## Prérequis

- Python 3.11 ou une version plus récente.
- [uv](https://docs.astral.sh/uv/).
- Une clé API Gemini ou Anthropic pour utiliser les fonctions qui appellent un LLM. Les tests unitaires et API simulés n'en ont pas besoin.

## Installer après un `git clone`

Depuis la racine du dépôt cloné, entre dans le dossier du projet puis installe les dépendances :

```bash
cd saas_rh
uv sync
```

Pour lancer l'application, crée le fichier local `.env` à partir du modèle et renseigne une clé ainsi qu'un modèle disponible :

```bash
cp .env.example .env
```

Dans `.env`, définis `LLM_PROVIDER` à `gemini` ou `anthropic`, puis renseigne la clé et le nom de modèle correspondants. Avec une clé Gemini, l'URL de base est également requise ; si une clé est présente mais qu'un réglage requis manque, l'application échoue au démarrage avec le nom de la variable manquante. Les clés ne doivent jamais être ajoutées à Git. Pour Anthropic, `ANTHROPIC_WORKSPACE_ID` est facultatif et ne sert que si la clé l'exige ; `ANTHROPIC_BASE_URL` peut rester vide pour utiliser le défaut du SDK.

Sans `.env` ni clé, l'application démarre quand même : l'interface et `/health` fonctionnent, `GET /api/interviews/slots` aussi, et les routes qui appellent un LLM (parsing, RAG, agent) répondent 503 « service non configuré ». Les tests n'ont pas besoin de clé non plus. Avec une clé, les politiques RH sont indexées **au démarrage** dans ChromaDB, ce qui peut télécharger un modèle d'embedding au premier lancement (connexion nécessaire, quelques instants).

Si le dépôt cloné ne contient pas de sous-dossier `saas_rh` parce que ce projet a été cloné directement, exécute les commandes depuis la racine du clone et omets `cd saas_rh`.

## Lancer l'application

Depuis le dossier `saas_rh` :

```bash
uv run uvicorn saas_rh.main:app --reload
```

Puis ouvre :

- Interface RH : <http://127.0.0.1:8000/>
- Documentation interactive de l'API : <http://127.0.0.1:8000/docs>
- Vérification du serveur : <http://127.0.0.1:8000/health>

Les routes principales sont `POST /api/candidates/parse`, `POST /api/rag/ask`, `GET /api/interviews/slots` et `POST /api/agent/chat`.

## Tester

La suite standard utilise des clients simulés et ne nécessite ni clé API, ni serveur lancé :

```bash
uv run pytest
```

Les tests fonctionnels avec de vrais appels LLM sont désactivés par défaut. Pour lancer toute la suite fonctionnelle, configure le fournisseur et sa clé dans `.env`, puis utilise un port dédié afin que les tests démarrent une instance avec la configuration courante :

```bash
SAAS_RH_RUN_FUNCTIONAL_TESTS=1 SAAS_RH_BASE_URL=http://127.0.0.1:8001 uv run pytest
```

Ces tests appellent réellement le fournisseur configuré et consomment son quota ou ses crédits. Si un serveur répond déjà sur l'URL choisie, les tests le réutilisent. Le port dédié évite généralement de réutiliser par erreur un serveur lancé avec une autre configuration.

Le test fonctionnel de parsing envoie les deux CV exemples et, si le fichier local existe, le PDF `src/saas_rh/data/candidates/20261014_test_cv.pdf`. Les PDF locaux sont ignorés par Git. Les PDF scannés sans texte sélectionnable ne sont pas pris en charge : l'extraction OCR reste à ajouter.

## Données et persistance

Les politiques RH, les CV exemples et l'agenda fictif sont dans `src/saas_rh/data/`. ChromaDB persiste son index dans `.chroma/` à la racine du projet par défaut ; `CHROMA_DB_PATH` permet de changer ce chemin (un chemin relatif est résolu depuis cette même racine). Au premier usage, ChromaDB peut télécharger son modèle d'embedding local. Les réservations d'entretien ne sont pas persistées et l'agenda est réinitialisé au redémarrage du serveur.

## Configuration

Les variables disponibles sont documentées dans [`.env.example`](.env.example). Le modèle principal est défini par `GEMINI_MODEL` ou `ANTHROPIC_MODEL`. Des modèles de repli facultatifs peuvent être listés, séparés par des virgules, dans `GEMINI_FALLBACK_MODELS` ou `ANTHROPIC_FALLBACK_MODELS` ; ils ne sont utilisés que pour le parsing des CV. Le RAG et l'agent utilisent uniquement le modèle principal. Le repli de l'agent n'est pas activé, car une reprise automatique autour d'outils qui modifient l'agenda demanderait une stratégie spécifique pour éviter de répéter une réservation.

Les appels Gemini compatibles OpenAI fixent `temperature=0.0`. Les appels Anthropic ne transmettent pas ce paramètre : ils utilisent le comportement par défaut du modèle. Leurs résultats ne sont donc pas configurés pour être déterministes ; le paramètre n'a pas été ajouté sans vérifier sa compatibilité avec les modèles configurés.

## Sécurité et données personnelles

Ce projet est un exercice local, sans authentification ni limitation de débit. Garde le serveur sur `127.0.0.1` (valeur par défaut d'`uvicorn`) et ne l'expose pas sur Internet sans ajouter ces protections, une limite de taille de corps de requête (6 Mo suffisent) et le masquage de `/docs`. Ne lance jamais de serveur ChromaDB (`chroma run`) : l'application n'utilise que le client embarqué, car les CVE connues de `chromadb` concernent son serveur HTTP.

Le texte d'un CV envoyé à l'analyse part chez le fournisseur LLM configuré (Gemini ou Anthropic). Un masquage par motifs retire avant l'envoi les e-mails, téléphones, liens de profil, l'en-tête de nom et les champs étiquetés (adresse, date de naissance…). C'est une réduction des données, pas une anonymisation : un nom ou une adresse dans le corps du texte peut passer. N'utilise que des CV fictifs pendant la formation. Le score est indicatif et doit être validé par un recruteur ; il ne constitue pas une décision de recrutement.

Pour poursuivre le travail, consulter [`PLAN_PROJET.md`](PLAN_PROJET.md) et [`REPRISE.md`](REPRISE.md).
