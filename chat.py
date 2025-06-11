from langchain.embeddings import HuggingFaceEmbeddings
from vector_store import client
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage, SystemMessage
import os
from langchain_community.document_loaders import PyPDFLoader
from dotenv import load_dotenv
from db import collection
import datetime
import http.client
import json
load_dotenv()

# Load the LLM model
os.environ["GOOGLE_API_KEY"] = os.getenv('GOOGLE_API_KEY')
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

collection_name = "warda"
# Load the embedding model
embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

def query_qdrant(query, top_k=3):
    try:
        query_embedding = embedding_model.embed_query(query)
        search_results = client.search( 
            collection_name=collection_name,
            query_vector=query_embedding,
            limit=top_k
        )
        return [hit.payload["text"] for hit in search_results]

    except Exception as e:
        return f"Error during Qdrant query: {e}"


# Example to read an attachment (Assuming it is a text file for simplicity)
def load_attachment(file_path):
    loader = PyPDFLoader(file_path)
    pages = loader.load()
    return pages

llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash")


menu = load_attachment("menu.pdf")

def generate_images(llm_response_text):
    # 1. Ask the LLM to extract plate names
    extraction_prompt = f"""
You are an assistant that extracts dish or plate names from text.

From the following message, extract all plate or drink or dessert names or dishes mentioned. Return them as a comma-separated list with no extra text.

If there's no plate to mention just return 'No Plate'

Message:
\"\"\"{llm_response_text}\"\"\"
    """
    print("\n📤 [DEBUG] Sending extraction prompt to LLM...")
    llm_extraction = llm([HumanMessage(content=extraction_prompt)])
    print(llm_extraction)
    raw_output = llm_extraction.content.strip()
    print("✅ [DEBUG] Raw LLM Extraction Output:", raw_output)

    # 2. Parse the plate names
    if not raw_output or raw_output.lower() in ["none", "no plate"]:
        print("⚠️ [DEBUG] No plate names detected.")
        return None

    plates = [p.strip() for p in raw_output.split(",") if p.strip()]
    print("🍽️ [DEBUG] Extracted Plates:", plates)
    if not plates:
        print("⚠️ [DEBUG] Plates list is empty after parsing.")
        return None

    # 3. Fetch images using Serper.dev
    images = {}

    for plate in plates:
        try:
            print(f"\n🔎 [DEBUG] Searching images for plate: {plate}")
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

            image_urls = []

            # Fallback to standard image search
            if "images" in search_results:
                fallback_images = [img["imageUrl"] for img in search_results["images"][:3]]
                image_urls.extend(fallback_images)
                print(f"🖼️ [DEBUG] Found fallback images for {plate}: {fallback_images}")
            else:
                print(f"❌ [DEBUG] No fallback images found for {plate}")

            if image_urls:
                images[plate] = image_urls

        except Exception as e:
            print(f"❗ [ERROR] Error fetching images for {plate}: {e}")

    if images:
        print("\n✅ [DEBUG] Final Image Dictionary:", images)
    else:
        print("\n⚠️ [DEBUG] No images returned for any plate.")

    return images if images else None


def chat(query, session_id):
    print("🚀 [INFO] Chat function started")
    print(f"💬 [INPUT] Query: {query}")
    print(f"🧾 [INPUT] Session ID: {session_id}")

    try:
        print("🧠 [STEP] Setting up system message...")
        system_message = SystemMessage(content=f"""
You are "MiMi", a friendly and knowledgeable chatbot for "La Maison", a Tunisian restaurant located in Tunisia.

Your goal is to provide exceptional customer service in the **same language the user uses**.

You should greet the customer warmly **only once per session**, and avoid repeating the greeting in future messages.

Maintain a warm, conversational, and professional tone — be clear, direct, and helpful. Avoid overly formal or apologetic phrases like "Malheureusement...".

You are knowledgeable about the restaurant's current **menu, specials, and services**, and you're always ready to guide customers through the ordering process, recommend dishes, and help with reservations.

You must **only reference dishes, drinks, and items that are listed in the provided menu**. Do not invent, assume, or describe any items that are not explicitly included in the menu — even if asked by the user. Stay within the provided menu at all times.

Do not mention or explain how the menu is provided. The menu is your only source of truth for available offerings.

All prices mentioned are in **Tunisian Dinar (TND)**.
                                   
Your responses should be culturally appropriate, friendly, and professional.

In every interaction, you should:
1. Greet the customer (if not already done) using their language.
2. Provide clear information about the menu, dishes, and ingredients.
3. Offer helpful suggestions based on preferences, dietary restrictions, or any special requests — but only using items from the provided menu.
4. Make the ordering or reservation process as seamless as possible.
5. Use a tone that is friendly, respectful, and professional — but never robotic.
6. If a client is confused, explain things simply and helpfully.

IMPORTANT:
- Always respond in the same language used by the customer.
- Only greet once per session.
- Promote something special from the menu when appropriate.
- Always make the customer feel valued and welcome.
- ***DO NOT GREET MORE THAN ONE TIME***
- ***DO NOT use apologetic or distant language like "Malheureusement..." — be natural and direct.***
- ***DO NOT mention or refer to how the menu was retrieved or provided.***
- ***DO NOT describe, suggest, or answer questions about dishes that are not in the provided menu.***
""")  # Omitted for brevity, keep your original content here.

        print("🔍 [STEP] Querying Qdrant for context...")
        try:
            results = query_qdrant(query)
            print(f"📄 [CONTEXT] Retrieved context from Qdrant: {results}")
        except Exception as e:
            print(f"❗ [ERROR] Failed to query Qdrant: {e}")
            results = []

        print("🕑 [STEP] Retrieving session chat history from MongoDB...")
        all_messages = collection.find(
            {"session_id": session_id},
            sort=[("timestamp", 1)]
        )
        formatted_history = ""
        for message in all_messages:
            role = message["role"]
            content = message["content"]
            formatted_history += f"{role}: {content}\n\n"
        print("📚 [DEBUG] Chat History:\n", formatted_history)

        print("📜 [STEP] Formatting messages for LLM...")
        context = "\n".join(results)
        messages = [
            system_message,
            HumanMessage(content=f"Context:\n{context}\n\nChat History:{formatted_history}\n\nMenu:\n{menu}\n\nPlease provide a detailed and well-structured answer:{query}")
        ]

        print("🤖 [STEP] Sending prompt to LLM...")
        try:
            response = llm(messages)
            response_text = response.content.strip() if hasattr(response, "content") else str(response).strip()
            print("✅ [DEBUG] LLM Response:", response_text)
        except Exception as e:
            print(f"❗ [ERROR] LLM call failed: {e}")
            return {
                "response": "Something went wrong while generating a response. Please try again later.",
                "images": {}
            }

        print("🖼️ [STEP] Generating images from LLM response...")
        try:
            images = generate_images(response_text)
            print("✅ [DEBUG] Image generation completed.")
        except Exception as e:
            print(f"❗ [ERROR] Image generation failed: {e}")
            images = {}

        print("💾 [STEP] Saving user and assistant messages to MongoDB...")
        try:
            user_message = {
                "session_id": session_id,
                "role": "user",
                "content": query,
                "timestamp": datetime.datetime.utcnow()
            }
            assistant_message = {
                "session_id": session_id,
                "role": "assistant",
                "content": response_text,
                "timestamp": datetime.datetime.utcnow()
            }
            collection.insert_many([user_message, assistant_message])
            print("✅ [DEBUG] Messages saved successfully.")
        except Exception as e:
            print(f"❗ [ERROR] Failed to save messages to MongoDB: {e}")

        result = {
            "response": response_text,
            "images": images or {}
        }

        print("✅ [INFO] Chat function completed successfully.")
        return result

    except Exception as e:
        print(f"💥 [FATAL ERROR] An unexpected error occurred in chat function: {e}")
        return {
            "response": "A fatal error occurred. Please try again later.",
            "images": {}
        }

# # 🧪 Main block for testing
if __name__ == "__main__":
    test_query = "Hey"
    test_session_id = "debug-session-003"

    print("💬 [TEST] Sending query to chat...\n")
    reply = chat(test_query, test_session_id)
    print("\n🤖 [REPLY]:", reply)

    print("\n🖼️ [TEST] Searching images based on reply...\n")
    generate_images(reply)