from app.config import settings
from app.providers.pinecone_provider import PineconeProvider

if __name__ == "__main__":
    if not settings.pinecone_api_key:
        raise SystemExit("PINECONE_API_KEY is required")
    PineconeProvider.create_index_if_needed()
    print(f"Pinecone index ready: {settings.pinecone_index_name}")
