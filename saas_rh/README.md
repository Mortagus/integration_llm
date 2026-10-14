# SaaS RH

## Test fonctionnel du parsing candidat

Ce test appelle le vrai service LLM et reste désactivé pendant la suite Pytest habituelle. Pour l'exécuter :

```bash
SAAS_RH_RUN_FUNCTIONAL_TESTS=1 uv run pytest tests/test_candidates_functional.py
```

Le test réutilise le serveur à `http://127.0.0.1:8000` s'il répond sur `/health`, sinon il démarre Uvicorn et l'arrête à la fin. L'URL peut être modifiée avec `SAAS_RH_BASE_URL`. Le fournisseur actif est défini par `LLM_PROVIDER` dans le `.env` (`gemini` ou `anthropic`). Il faut renseigner la clé correspondante (`GEMINI_API_KEY` ou `ANTHROPIC_API_KEY`). Si le fichier local `src/saas_rh/data/candidates/20261014_test_cv.pdf` existe, le test l'envoie également à l'API. Les PDF de CV locaux sont ignorés par Git. Si une requête échoue avec une erreur serveur, la traceback apparaît dans le terminal qui exécute Uvicorn.

La route de parsing accepte le texte ou un fichier PDF. Le texte sélectionnable du PDF est extrait avec `pypdf`; les PDF scannés qui ne contiennent pas de texte sélectionnable nécessitent une étape OCR et ne sont pas pris en charge pour le moment.

Le parsing tente le modèle configuré (`GEMINI_MODEL` ou `ANTHROPIC_MODEL`), puis les modèles de repli configurés (`GEMINI_FALLBACK_MODELS` ou `ANTHROPIC_FALLBACK_MODELS`), séparés par des virgules. Il passe au modèle suivant après une erreur de disponibilité (404, 408, 429 ou erreur serveur 5xx) ; les erreurs de configuration, d'authentification et de format de requête arrêtent le traitement. Si tous les modèles échouent, la réponse 503 indique le dernier modèle essayé et le message du fournisseur.

Pour Anthropic, l'application utilise le SDK Python officiel et les sorties structurées `messages.parse` avec le schéma Pydantic du candidat. Un abonnement Claude Code n'est pas une clé API générique pour l'application : configurez une clé `ANTHROPIC_API_KEY` autorisée pour l'API Anthropic. Pour changer de fournisseur, modifiez `LLM_PROVIDER` dans le `.env`.

Si Anthropic répond que la clé n'est associée à aucun workspace, renseignez `ANTHROPIC_WORKSPACE_ID` avec l'identifiant du workspace dans le `.env`. Le client enverra alors l'en-tête `anthropic-workspace-id` à chaque requête. Dans l'Anthropic Console, les workspaces se gèrent dans **Settings → Workspaces** ; une clé créée depuis l'onglet **API Keys** d'un workspace y est déjà rattachée. Les clés API sont liées au workspace où elles ont été créées et ne peuvent pas être déplacées.
