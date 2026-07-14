from fastapi import FastAPI
from app.services.receipt_processor import process_image

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "LifeSync Backend is running!"}

@app.post("/process-receipt")
def process_receipt_route():
    # Calling the internal service layer
    return process_image("dummy_path")
from fastapi import FastAPI
from app.services.receipt_processor import process_image

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "LifeSync Backend is running!"}

@app.post("/process-receipt")
def process_receipt_route():
    # Calling the internal service layer
    return process_image("dummy_path")
