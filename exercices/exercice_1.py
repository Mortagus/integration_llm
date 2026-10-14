from llm_service import LLMService, LLMResponse


def analyser_code(code_source: str) -> LLMResponse:
    # Ton implémentation
    service = LLMService()
    return service.interroger_llm(
        temperature=0.2,
        question=code_source
    )


def calculer_cout(prompt_tokens: int, completion_tokens: int):
    # Ton implémentation
    input_token_price = 0.15
    output_token_price = 0.60

    return ((prompt_tokens * input_token_price) + (completion_tokens * output_token_price)) / 1000000
