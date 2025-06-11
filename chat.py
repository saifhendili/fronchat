import os
import json
import http.client
import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
import fitz  # PyMuPDF for PDF parsing

from langchain.embeddings import HuggingFaceInferenceAPIEmbeddings
from langchain.vectorstores import Qdrant
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage, SystemMessage
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct

load_dotenv()

# === ENV Variables ===
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_CLOUD_URL = os.getenv("QDRANT_CLOUD_URL")

os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

# === MongoDB ===
mongo_client = MongoClient(os.getenv("MONGO_URI"))
collection = mongo_client["chatbot"]["messages"]

# === Embedding Model ===
embedding_model = HuggingFaceInferenceAPIEmbeddings(
    api_key=HF_TOKEN,
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

# === Qdrant Cloud Setup ===
client = QdrantClient(
    url=QDRANT_CLOUD_URL,
    api_key=QDRANT_API_KEY,
)
collection_name = "warda"

# === Load LLM ===
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash")

# === Load PDF Menu ===
def load_attachment(file_path):
    doc = fitz.open(file_path)
    return "\n".join([page.get_text() for page in doc])

menu = load_attachment("menu.pdf")

# === Query Qdrant ===
def query_qdrant(query, top_k=3):
    try:
        query_vector = embedding_model.embed_query(query)
        results = client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=top_k
        )
        return [hit.payload["text"] for hit in results]
    except Exception as e:
        return [f"Error during Qdrant query: {e}"]

# === Generate Images ===
def generate_images(text):
    extraction_prompt = f"""
You are an assistant that extracts dish or plate names from text.

From the following message, extract all plate or drink or dessert names or dishes mentioned. Return them as a comma-separated list with no extra text.

If there's no plate to mention just return 'No Plate'

Message:
\"\"\"{text}\"\"\"
    """
    llm_extraction = llm([HumanMessage(content=extraction_prompt)])
    raw_output = llm_extraction.content.strip()
    if not raw_output or raw_output.lower() in ["none", "no plate"]:
        return None
    plates = [p.strip() for p in raw_output.split(",") if p.strip()]
    images = {}
    for plate in plates:
        try:
            conn = http.client.HTTPSConnection("google.serper.dev")
            payload = json.dumps({"q": plate})
            headers = {
                'X-API-KEY': SERPER_API_KEY,
                'Content-Type': 'application/json'
            }
            conn.request("POST", "/images", payload, headers)
            res = conn.getresponse()
            data = res.read().decode("utf-8")
            search_results = json.loads(data)
            image_urls = [img["imageUrl"] for img in search_results.get("images", [])[:3]]
            if image_urls:
                images[plate] = image_urls
        except Exception as e:
            print(f"[Error Image]: {plate} - {e}")
    return images or None

# === Chat Function ===
def chat(query, session_id):
    try:
        system_message = SystemMessage(content=f"""
You are "MiMi", a friendly and knowledgeable chatbot for "La Maison", a Tunisian restaurant in Tunisia.

Respond in the same language as the user. Only greet once per session. Use only the provided menu. Prices are in TND. Never invent dishes.

Keep it warm, helpful, and conversational.
""")
        results = query_qdrant(query)
        all_messages = collection.find({"session_id": session_id}, sort=[("timestamp", 1)])
        history = "\n".join(f"{m['role']}: {m['content']}" for m in all_messages)

        messages = [
            system_message,
            HumanMessage(content=f"Context:\n{'\n'.join(results)}\n\nChat History:\n{history}\n\nMenu:\n{menu}\n\nAnswer this:\n{query}")
        ]
        response = llm(messages)
        response_text = response.content.strip()

        images = generate_images(response_text)

        # Save to Mongo
        collection.insert_many([
            {"session_id": session_id, "role": "user", "content": query, "timestamp": datetime.datetime.utcnow()},
            {"session_id": session_id, "role": "assistant", "content": response_text, "timestamp": datetime.datetime.utcnow()},
        ])

        return {"response": response_text, "images": images or {}}

    except Exception as e:
        return {"response": f"Error: {e}", "images": {}}

# === Test Block ===
if __name__ == "__main__":
    test = chat("Hello, what's the best couscous?", "debug-session")
    print(test)
