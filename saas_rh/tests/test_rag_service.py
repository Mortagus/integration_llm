from types import SimpleNamespace
from unittest.mock import Mock

from anthropic import Anthropic

from saas_rh.data.rag.mock_data import POLITIQUES_RH
from saas_rh.llm.gateway import AnthropicGateway
from saas_rh.rag.schemas import RagAskResponse, RagSource
from saas_rh.rag.service import RAGService


def make_service(query_result: dict[str, list[list]]) -> tuple[RAGService, Mock, Mock]:
    collection = Mock()
    collection.query.return_value = query_result
    llm_gateway = Mock()
    llm_gateway.complete.return_value = "Réponse fondée."
    service = RAGService(
        collection=collection,
        llm_gateway=llm_gateway,
        model_name="modele-test",
    )
    return service, collection, llm_gateway


def test_index_policies_upserts_policy_text_and_metadata() -> None:
    service, collection, _ = make_service({})

    service.index_policies()

    call = collection.upsert.call_args.kwargs
    assert call["ids"] == [policy["id"] for policy in POLITIQUES_RH]
    assert call["documents"] == [policy["texte"] for policy in POLITIQUES_RH]
    assert call["metadatas"] == [{"title": policy["titre"]} for policy in POLITIQUES_RH]


def test_answer_question_returns_answer_and_cited_sources() -> None:
    service, collection, llm_client = make_service(
        {
            "ids": [["rh_doc_02"]],
            "documents": [["10 jours de RTT et 5 versables au CET."]],
            "metadatas": [[{"title": "Politique de Congés & RTT"}]],
            "distances": [[0.2]],
        }
    )

    response = service.answer_question("Combien de RTT peut-on placer dans le CET ?")

    assert response == RagAskResponse(
        content="Réponse fondée.",
        sources=[
            RagSource(
                id="rh_doc_02",
                title="Politique de Congés & RTT",
                excerpt="10 jours de RTT et 5 versables au CET.",
            )
        ],
    )
    collection.query.assert_called_once_with(
        query_texts=["Combien de RTT peut-on placer dans le CET ?"], n_results=2
    )
    system_prompt = llm_client.complete.call_args.args[1]
    assert "uniquement" in system_prompt
    assert "rh_doc_02" in system_prompt


def test_answer_question_abstains_when_collection_has_no_results() -> None:
    service, _, llm_client = make_service(
        {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    )

    response = service.answer_question("Quelle est la prime de naissance ?")

    assert response == RagAskResponse(
        content="Je ne trouve pas cette information dans les politiques RH fournies.",
        sources=[],
    )
    llm_client.complete.assert_not_called()


def test_answer_question_does_not_index_policies() -> None:
    service, collection, _ = make_service(
        {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    )

    service.answer_question("Question 1")
    service.answer_question("Question 2")

    collection.upsert.assert_not_called()
    assert collection.query.call_count == 2


def test_answer_question_supports_anthropic_messages_client() -> None:
    collection = Mock()
    collection.query.return_value = {
        "ids": [["rh_doc_02"]],
        "documents": [["Dix jours de RTT sont accordés."]],
        "metadatas": [[{"title": "Congés et RTT"}]],
    }
    client = Anthropic(api_key="test-api-key")
    client.messages.create = Mock(
        return_value=SimpleNamespace(
            content=[SimpleNamespace(type="text", text="Dix jours de RTT. [rh_doc_02]")]
        )
    )
    service = RAGService(collection, AnthropicGateway(client), "modele-anthropic")

    try:
        response = service.answer_question("Combien de RTT ?")
    finally:
        client.close()

    assert response.content == "Dix jours de RTT. [rh_doc_02]"
    client.messages.create.assert_called_once()
    assert "temperature" not in client.messages.create.call_args.kwargs
