import os
from langchain_pinecone import PineconeVectorStore
from langchain.embeddings.base import Embeddings
from dotenv import load_dotenv

load_dotenv()

# Simple mock embeddings class
class MockEmbeddings(Embeddings):
    def __init__(self):
        pass
    
    def embed_documents(self, texts):
        return [self._embed(text) for text in texts]
    
    def embed_query(self, text):
        return self._embed(text)
        
    def _embed(self, text):
        dim = 8
        vec = [0.0] * dim
        for i, c in enumerate(text):
            vec[i % dim] += ord(c)
        return [float(int(x) % 256) / 256 for x in vec]

class ComplianceRAG:
    def __init__(self):
        self.embeddings = MockEmbeddings()
        try:
            self.vectorstore = PineconeVectorStore(
                index_name="compliance-rules", 
                embedding=self.embeddings
            )
        except Exception as e:
            print(f"Note: Could not connect to Pinecone: {e}")
            self.vectorstore = None

    def get_rules_for_context(self, chunk_text):
        # Finds the most relevant rules from your policy.txt
        if self.vectorstore is None:
            return "No rules available - using mock data"
        try:
            docs = self.vectorstore.similarity_search(chunk_text, k=2)
            return "\n".join([d.page_content for d in docs])
        except Exception as e:
            return f"Could not retrieve rules: {e}"
