import chromadb

class RAGIndexer:
    documentsToIndex: list

    def __init__(self, collectionName: str, documentsToIndex: list):
        self.chroma_client = chromadb.Client()
        self.collection = self.chroma_client.get_or_create_collection(name=collectionName)
        self.documentsToIndex = documentsToIndex
        self._indexer_documents()

    def _indexer_documents(self):
        textes = [doc["texte"] for doc in self.documentsToIndex]
        ids = [doc["id"] for doc in self.documentsToIndex]

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