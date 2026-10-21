import os
from fastapi import FastAPI, Request, Response
from dotenv import load_dotenv
import uvicorn

# Load variables from .env file
load_dotenv()

app = FastAPI()

# Retrieve credentials securely from environment variables
LEMINA_API_KEY = os.getenv("LEMINA_API_KEY")

@app.post("/webhook")
async def receive_message(request: Request):
    """Triggers whenever anyone messages via LeminaAI."""
    try:
        body = await request.json()
        print("Received webhook payload:", body)
        
        # Extract sender and message body from payload structure
        sender_phone = body.get("from") or body.get("sender") or body.get("phone")
        message_body = body.get("message") or body.get("text") or body.get("body")
        
        if message_body:
            print(f"Triggered! Message from {sender_phone}: {message_body}")
            
        return Response(status_code=200)
    except Exception as e:
        print(f"Error processing webhook: {e}")
        return Response(status_code=500)

if __name__ == "__main__":
    uvicorn.run("input", host="0.0.0.0", port=8000, reload=True)