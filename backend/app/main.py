@app.post("/upload-receipt")
async def upload_receipt(file: UploadFile = File(...)):
    # Add this check to prevent non-image files from breaking the AI service
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are allowed.")
    
    file_path = UPLOAD_DIR / file.filename
    # ... rest of your code
@app.post("/upload-receipt")
async def upload_receipt(file: UploadFile = File(...)):
    # Add this check to prevent non-image files from breaking the AI service
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are allowed.")
    
    file_path = UPLOAD_DIR / file.filename
    # ... rest of your code
