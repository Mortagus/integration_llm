import os
import chromadb
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DOCUMENTS_ENTREPRISE = [
    {
        "id": "doc_1",
        "texte": "Les retours de produits e-commerce sont acceptés sous 30 jours calendaires après réception. Le produit doit être neuf dans son emballage d'origine.",
    },
    {
        "id": "doc_2",
        "texte": "Les frais de port pour un retour produit sont intégralement pris en charge par l'entreprise uniquement si le produit est défectueux.",
    },
    {
        "id": "doc_3",
        "texte": "Pour la marque 'Bierwart', le délai de livraison standard en Belgique est de 48h ouvrées. Pour la France, compter 3 à 5 jours.",
    },
    {
        "id": "doc_4",
        "texte": "La garantie constructeur sur tous les appareils électroniques vendus est de 2 ans pièces et main d'œuvre.",
    },
]


class RAGService:
    def __init__(self):
        gemini_key = os.getenv("GEMINI_API_KEY")

        self.client = OpenAI(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=gemini_key,
        )
        self.chroma_client = chromadb.Client()
        self.collection = self.chroma_client.get_or_create_collection(name="faq_entreprise")

        self._indexer_documents()

    def _indexer_documents(self):
        textes = [doc["texte"] for doc in DOCUMENTS_ENTREPRISE]
        ids = [doc["id"] for doc in DOCUMENTS_ENTREPRISE]

        self.collection.add(
            documents=textes,
            ids=ids,
        )
        print(f"{len(textes)} documents indexé")

    def poser_question_rag(self, question: str) -> str:
        results = self.collection.query(
            query_texts=[question],
            n_results=2
        )

        print(f"{type(results)}")

        docs_pertinents = results["documents"][0]
        contexte_extrait = "\n-".join(docs_pertinents)

        print("Contextes pertinents retrouvés : ")
        for doc in docs_pertinents:
            print(f"{doc}")
        print("-" * 60)

        system_prompt = (
            "Tu est un assistant support client strict"
            "Réponds à la question de l'utilisateur uniquement en t'appuyant sur les documents fournis dans le contexte."
            "Si la réponse n'est pas contenue dans le contexte, dis poliment que tu ne sais pas "
            f"Contexte extrait du rag : {contexte_extrait}"
        )

        response = self.client.chat.completions.create(
            model="gemini-3.1-flash-lite",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            temperature=0.0
        )
        return response.choices[0].message.content


if __name__ == "__main__":
    rag = RAGService()

    q1 = "Quels sont les délais pour retourner un produit et qui paye ? "
    print(f"Question 1 : {q1}")
    rep1 = rag.poser_question_rag(q1)
    print(f"\n Réponse RAG : {rep1}")

    print("-" * 60)

    q2 = "Quelle est la politique de garantie pour les vélos ?"
    print(f"Question 2 : {q2}")
    rep2 = rag.poser_question_rag(q2)
    print(f"\n Réponse RAG : {rep2}")
