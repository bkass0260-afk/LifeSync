import os
import base64
import json
from openai import OpenAI
from app.models.receipt import Receipt

# Initialize the official client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def process_image(image_path: str) -> Receipt:
    # Encode image for the AI
    with open(image_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')
    
    # Send to AI
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract receipt data as JSON: merchant_name, total_amount, date, category."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }
        ],
        response_format={"type": "json_object"}
    )
    
    # Map to Pydantic model
    data = json.loads(response.choices[0].message.content)
    return Receipt(**data)
