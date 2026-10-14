from collections.abc import Sequence

from anthropic import Anthropic
from chromadb.api.models.Collection import Collection
from openai import OpenAI

from saas_rh.data.rag.mock_data import POLITIQUES_RH
from saas_rh.rag.schemas import RagAskResponse, RagSource

NO_CONTEXT_RESPONSE = (
    "Je ne trouve pas cette information dans les politiques RH fournies."
)


class RAGService:
    """Indexes HR policies and answers questions using retrieved passages."""

    def __init__(
        self,
        collection: Collection,
        llm_client: OpenAI | Anthropic,
        model_name: str,
        result_count: int = 2,
    ) -> None:
        self.collection = collection
        self.llm_client = llm_client
        self.model_name = model_name
        self.result_count = result_count
        self._policies_indexed = False

    def index_policies(
        self,
        policies: Sequence[dict[str, str]] | None = None,
    ) -> None:
        """Create or update the policy records without duplicating them."""
        indexed_policies = POLITIQUES_RH if policies is None else policies
        self.collection.upsert(
            ids=[policy["id"] for policy in indexed_policies],
            documents=[policy["texte"] for policy in indexed_policies],
            metadatas=[{"title": policy["titre"]} for policy in indexed_policies],
        )
        self._policies_indexed = True

    def answer_question(self, question: str) -> RagAskResponse:
        """Retrieve policy passages and generate a grounded, sourced answer."""
        if not self._policies_indexed:
            self.index_policies()
        results = self.collection.query(
            query_texts=[question],
            n_results=self.result_count,
        )
        ids_by_query = results.get("ids") or [[]]
        documents_by_query = results.get("documents") or [[]]
        metadatas_by_query = results.get("metadatas") or [[]]
        ids = ids_by_query[0] if ids_by_query else []
        documents = documents_by_query[0] if documents_by_query else []
        metadatas = metadatas_by_query[0] if metadatas_by_query else []

        sources = [
            RagSource(
                id=ids[index] if index < len(ids) else f"policy_{index + 1}",
                title=(
                    metadatas[index].get("title", "Politique RH")
                    if index < len(metadatas) and metadatas[index]
                    else "Politique RH"
                ),
                excerpt=document,
            )
            for index, document in enumerate(documents)
            if document
        ]
        if not sources:
            return RagAskResponse(content=NO_CONTEXT_RESPONSE, sources=[])

        context = "\n\n".join(
            f"[Source {source.id} — {source.title}]\n{source.excerpt}"
            for source in sources
        )
        system_prompt = (
            "Tu es un assistant RH. Réponds à la question uniquement à partir du "
            "contexte documentaire ci-dessous. N'ajoute aucune règle ou information "
            "qui n'y figure pas. Si le contexte ne permet pas de répondre, dis "
            f"exactement : « {NO_CONTEXT_RESPONSE} ». Cite les identifiants des "
            "sources utilisées dans ta réponse.\n\nContexte documentaire :\n"
            f"{context}"
        )
        answer = self._generate_answer(question, system_prompt)
        return RagAskResponse(content=answer, sources=sources)

    def _generate_answer(self, question: str, system_prompt: str) -> str:
        if isinstance(self.llm_client, Anthropic):
            response = self.llm_client.messages.create(
                model=self.model_name,
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": question}],
            )
            answer = "\n".join(
                block.text for block in response.content if block.type == "text"
            )
        else:
            response = self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question},
                ],
                temperature=0.0,
            )
            answer = response.choices[0].message.content

        if not answer or not answer.strip():
            raise ValueError("Le LLM n'a pas retourné de réponse RH valide.")
        return answer.strip()
