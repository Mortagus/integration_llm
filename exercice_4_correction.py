import os

import chromadb
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DOCUMENTS_CLOUD = [
    {
        "id": "doc_1",
        "texte": (
            "En cas d'erreur HTTP 502 Bad Gateway sur les conteneurs Docker, "
            "effectuer un redémarrage du service via la commande 'docker compose restart api'. "
            "Si l'erreur persiste plus de 5 minutes, basculer le trafic sur le cluster de secours."
        ),
    },
    {
        "id": "doc_2",
        "texte": (
            "La rétention des sauvegardes de bases de données PostgreSQL est de 30 jours "
            "pour la production et 7 jours pour les environnements de staging. "
            "Les restaurations doivent être validées par le Lead DevOps."
        ),
    },
    {
        "id": "doc_3",
        "texte": (
            "Pour renouveler un certificat SSL/TLS expiré, exécuter le script "
            "'/scripts/renew_cert.sh --domain example.com'. Le délai de propagation "
            "du nouveau certificat est d'environ 15 minutes."
        ),
    },
    {
        "id": "doc_4",
        "texte": (
            "L'accès en SSH aux serveurs de production nécessite impérativement un VPN actif "
            "et l'utilisation d'une clé RSA de minimum 4096 bits associée au module YubiKey."
        ),
    },
]


class ServiceRAGDevOps:
    def __init__(self):
        gemini_key = os.getenv("GEMINI_API_KEY")
        self.client = OpenAI(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=gemini_key
        )

        self.chroma_client = chromadb.Client()
        self.collection = self.chroma_client.get_or_create_collection(name="docs_devops")

        self._indexer_doc()

    def _indexer_doc(self):
        print("Indexing documents...")

        textes = [doc["texte"] for doc in DOCUMENTS_CLOUD]
        ids = [doc["id"] for doc in DOCUMENTS_CLOUD]

        self.collection.add(
            documents=textes,
            ids=ids,
        )

        print(f"{len(textes)} documents indexed")

    def interroger_rag(self, question: str) -> str:
        results = self.collection.query(
            query_texts=[question],
            n_results=2
        )

        docs_retrouves = results["documents"][0]
        contexte_formate = "\n- ".join(docs_retrouves)

        for doc in docs_retrouves:
            print(f"Documents → {doc}")

        print("-" * 60)

        system_prompt = ("Tu est un ingénieur support N1 spécialisé en infrastructure Cloud et devops. \n "
                         "Réponds à la demande de l'utilisateur UNIQUEMENT à partir du contexte technique ci-dessous. \n"
                         "CONSIGNE STRICTE : Si la réponse ne se trouve pas dans le contexte fourni, indique"
                         "clairement et poliment que tu ne trouves pas cette information dans la documentation interne. \n "
                         "N'invente aucune commande ni aucune procédure. \n\n"
                         f"--- CONTEXTE TECHNIQUE EXTRAIT ---\n- {contexte_formate}\n ")
        response = self.client.chat.completions.create(
            model="gemini-3.1-flash-lite",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            temperature=0.0,
        )

        return response.choices[0].message.content


if __name__ == "__main__":
    service_rag = ServiceRAGDevOps()

    q1 = "Comment réagir si les conteneurs renvoient une erreur 502 et quelle est la règle de sauvegarde pour PostgreSQL ?"
    print(f" Test 1 : \n {q1} \n")
    reponse1 = service_rag.interroger_rag(q1)
    print(f" Réponse assistant: \n {reponse1} \n")

    q2 = "Quelle est la procédure pour augmenter la mémoire RAM d'un cluster Kubernetes ?"
    print(f" Test 2 : \n {q2} \n")
    reponse2 = service_rag.interroger_rag(q2)
    print(f" Réponse assistant: \n {reponse2} \n")
