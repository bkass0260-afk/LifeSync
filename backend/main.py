from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "LifeSync Backend is running!"}

@app.get("/status")
def get_status():
    return {"status": "online"}
