from qdrant_client import QdrantClient
from dotenv import load_dotenv
import os
load_dotenv(override=True)
# Replace with your Qdrant cluster URL and API key
QDRANT_CLOUD_URL = os.getenv('QDRANT_CLOUD_URL')
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')

client = QdrantClient(
    url=QDRANT_CLOUD_URL,
    api_key=QDRANT_API_KEY,
)