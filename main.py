from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from chat import chat  # Import the core chat function
import uvicorn

# Initialize the FastAPI application
app = FastAPI(
    title="La Maison Chatbot API",
    description="An API that powers MiMi, a chatbot for La Maison restaurant.",
    version="1.0.0"
)

# Request model for the /chat endpoint
class ChatRequest(BaseModel):
    query: str        # The user's message
    session_id: str   # Unique session identifier to maintain conversation history

@app.post("/chat", summary="Chat with MiMi", response_description="Chatbot response")
async def chat_endpoint(request: ChatRequest):
    """
    Endpoint to send a message to MiMi, the La Maison chatbot.

    This endpoint takes a user query and a session ID,
    then returns a structured chatbot response including any images if relevant.

    Args:
        request (ChatRequest): A JSON body with 'query' (user message) and 'session_id'.

    Returns:
        JSON object containing:
        - response: The assistant's message as a string.
        - images: A dictionary of any related images (if generated).
    """
    try:
        print(f"🛎️ [REQUEST] Query: {request.query} | Session ID: {request.session_id}")
        response = chat(request.query, request.session_id)
        print(f"✅ [RESPONSE] {response}")
        return response
    except Exception as e:
        print(f"❗ [ERROR] Exception in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Run the FastAPI server when the script is executed directly
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
