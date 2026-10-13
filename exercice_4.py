# # Exercice 4 : Moteur RAG & Anti-Hallucination sur Documentation Technique
#
# ## Objectif
# Implémenter un système de **Retrieval-Augmented Generation (RAG)** avec une base de données vectorielle locale (`ChromaDB`) pour permettre à un assistant de répondre à des questions techniques complexes tout en évitant les hallucinations.
#
# ## Consignes
# 1. Créez un fichier `exercice_4_rag.py`.
# 2. Installez et importez `chromadb` (`pip install chromadb`).
# 3. Définissez la liste de documents suivants représentant la documentation interne d'une infrastructure Cloud :
#
# ```python
# DOCUMENTS_CLOUD = [
#     {
#         "id": "doc_1",
#         "texte": "En cas d'erreur HTTP 502 Bad Gateway sur les conteneurs Docker, effectuer un redémarrage du service via la commande 'docker compose restart api'. Si l'erreur persiste plus de 5 minutes, basculer le trafic sur le cluster de secours."
#     },
#     {
#         "id": "doc_2",
#         "texte": "La rétention des sauvegardes de bases de données PostgreSQL est de 30 jours pour la production et 7 jours pour les environnements de staging. Les restaurations doivent être validées par le Lead DevOps."
#     },
#     {
#         "id": "doc_3",
#         "texte": "Pour renouveler un certificat SSL/TLS expiré, exécuter le script '/scripts/renew_cert.sh --domain example.com'. Le délai de propagation du nouveau certificat est d'environ 15 minutes."
#     },
#     {
#         "id": "doc_4",
#         "texte": "L'accès en SSH aux serveurs de production nécessite impérativement un VPN actif et l'utilisation d'une clé RSA de minimum 4096 bits associée au module YubiKey."
#     }
# ]

import chromadb
import os

from dotenv import load_dotenv
from openai import OpenAI


class RAGIndexer:
    documents_to_index: list

    def __init__(self, collection_name: str, documents_to_index: list):
        self.chroma_client = chromadb.Client()
        self.collection = self.chroma_client.get_or_create_collection(name=collection_name)
        self.documents_to_index = documents_to_index
        self._indexer_documents()

    def _indexer_documents(self):
        textes = [doc["texte"] for doc in self.documents_to_index]
        ids = [doc["id"] for doc in self.documents_to_index]

        self.collection.add(
            documents=textes,
            ids=ids,
        )
        print(f"{len(textes)} documents indexé")

    def query(self, question) -> dict:
        return self.collection.query(
            query_texts=[question],
            n_results=2
        )


class RAGAssistant:
    system_prompt: str
    base_url: str
    api_key: str
    model_name: str
    indexer: RAGIndexer

    def __init__(self, rag_indexer: RAGIndexer, base_url: str, api_key: str, model_name: str, system_prompt: str):
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key,
        )
        self.model_name = model_name
        self.system_prompt = system_prompt
        self.indexer = rag_indexer

    def poser_question_rag(self, question) -> str:
        results = self.indexer.query(question)

        docs_pertinents = results["documents"][0]
        contexte_extrait = "\n-".join(docs_pertinents)

        # print("Contextes pertinents retrouvés : ")
        # for doc in docs_pertinents:
        #     print(f"{doc}")
        # print("-" * 20)

        prompt = f"""
        {self.system_prompt}

        CONTEXTE :
        {contexte_extrait}
        """

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": question},
            ],
            temperature=0.0
        )
        return response.choices[0].message.content


if __name__ == "__main__":
    load_dotenv()
    DOCUMENTS_CLOUD = [
        {
            "id": "doc_1",
            "texte": "En cas d'erreur HTTP 502 Bad Gateway sur les conteneurs Docker, effectuer un redémarrage du service via la commande 'docker compose restart api'. Si l'erreur persiste plus de 5 minutes, basculer le trafic sur le cluster de secours."
        },
        {
            "id": "doc_2",
            "texte": "La rétention des sauvegardes de bases de données PostgreSQL est de 30 jours pour la production et 7 jours pour les environnements de staging. Les restaurations doivent être validées par le Lead DevOps."
        },
        {
            "id": "doc_3",
            "texte": "Pour renouveler un certificat SSL/TLS expiré, exécuter le script '/scripts/renew_cert.sh --domain example.com'. Le délai de propagation du nouveau certificat est d'environ 15 minutes."
        },
        {
            "id": "doc_4",
            "texte": "L'accès en SSH aux serveurs de production nécessite impérativement un VPN actif et l'utilisation d'une clé RSA de minimum 4096 bits associée au module YubiKey."
        }
    ]

    indexer = RAGIndexer(
        collection_name="technical_docs",
        documents_to_index=DOCUMENTS_CLOUD
    )

    assistant = RAGAssistant(
        rag_indexer=indexer,
        system_prompt=(
            "Tu es un assistant support client strict. "
            "Réponds à la question de l'utilisateur uniquement en t'appuyant sur les documents fournis dans le contexte. "
            "Si la réponse n'est pas contenue dans le contexte, dis poliment que tu ne sais pas. "
        ),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key=os.getenv("GEMINI_API_KEY"),
        model_name="gemini-3.1-flash-lite",
        # base_url="https://openrouter.ai/api/v1",
        # api_key=os.getenv("OPENROUTER_API_KEY"),
        # model_name="openrouter/free",
    )

    q1 = "Comment réagir si les conteneurs renvoient une erreur 502 et quelle est la règle de sauvegarde pour PostgreSQL ?"
    print(f"Question 1 : {q1}")
    rep1 = assistant.poser_question_rag(q1)
    print(f"\n Réponse RAG : {rep1}")

    print("-" * 60)

    q2 = "Quelle est la procédure pour augmenter la mémoire RAM d'un cluster Kubernetes ?"
    print(f"Question 2 : {q2}")
    rep2 = assistant.poser_question_rag(q2)
    print(f"\n Réponse RAG : {rep2}")

    print("-" * 60)

    q3 = "Est-ce que tu as bien mangé à midi ?"
    print(f"Question 3 : {q3}")
    rep3 = assistant.poser_question_rag(q3)
    print(f"\n Réponse RAG : {rep3}")
