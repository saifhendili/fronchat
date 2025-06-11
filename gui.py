import streamlit as st
import random
import time
import requests
import json

# Initialize session ID
if "session_id" not in st.session_state:
    st.session_state.session_id = str(random.getrandbits(32))

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

st.title("M&W")

# Streamed response emulator
def response_generator(text):
    for word in text.split():
        yield word + " "
        time.sleep(0.03)

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        # Show images if included
        if message["role"] == "assistant" and "images" in message:
            for plate, url in message["images"].items():
                st.image(url, caption=plate)

# Accept user input
if prompt := st.chat_input("What is up?"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Display assistant response
    with st.chat_message("assistant", avatar="logo.jpeg"):
        with st.spinner("Le chef prépare ses suggestions... 🍽️"):
            # --- Make POST request to your API ---
            payload = {
                "query": prompt,
                "session_id": st.session_state.session_id
            }
            res = requests.post("https://20e2-197-8-177-181.ngrok-free.app/chat", json=payload)
            res_json = res.json()

            # --- Get response and image dict ---
            response_text = res_json["response"]
            image_dict = res_json.get("images", {})

            # --- Stream the assistant text ---
            response = st.write_stream(response_generator(response_text))

            # --- Show one image per plate ---
            images_to_show = {}
            for plate, urls in image_dict.items():
                if urls:
                    images_to_show[plate] = random.choice(urls)
                    st.image(images_to_show[plate], caption=plate)

    # Add response to history with images
    st.session_state.messages.append({
        "role": "assistant",
        "content": response_text,
        "images": images_to_show  # Store selected images in session state
    })
