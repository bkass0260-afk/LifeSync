from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path
import shutil
import uuid
import os
import logging

# Import the processing service (Phase 2 will implement this)
from services.receipt_processor import process_image  # should be async

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# App and CORS (development: allow all origins)
app = FastAPI(title="Receipt Processing API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Upload directory: backend/app/uploads/
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "app" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Pydantic models for response (ensure service returns this shape)
class Item(BaseModel):
    description: str
    quantity: Optional[int] = None
    price: Optional[float] = None

class Receipt(BaseModel):
    vendor: Optional[str] = None
    date: Optional[str] = None  # ISO date string preferred
    total: Optional[float] = None
    currency: Optional[str] = None
    items: List[Item] = []

@app.post("/upload-receipt", response_model=Receipt)
async def upload_receipt(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    """
    Accept an image file, save to backend/app/uploads/, call process_image,
    and ensure the temporary file is deleted after the response is returned.
    """
    # Basic validation: accept only images
    content_type = (file.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are allowed.")

    # Generate a safe unique filename
    suffix = Path(file.filename).suffix or ""
    unique_name = f"{uuid.uuid4().hex}{suffix}"
    saved_path = UPLOAD_DIR / unique_name

    # Save uploaded file to disk
    try:
        # file.file is a SpooledTemporaryFile; using shutil to write to destination
        with saved_path.open("wb") as out_file:
            file.file.seek(0)
            shutil.copyfileobj(file.file, out_file)
        logger.info("Saved upload to %s", saved_path)
    except Exception as exc:
        logger.exception("Failed to save uploaded file: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to save uploaded file.") from exc
    finally:
        # Close the uploaded file object
        try:
            file.file.close()
        except Exception:
            pass

    # Call the processing service. Expect an object/dict that matches Receipt model.
    try:
        # process_image should be implemented as an async function in services/receipt_processor.py
        result = await process_image(str(saved_path))
    except Exception as exc:
        logger.exception("Error while processing image: %s", exc)
        # Schedule cleanup even on processing failure
        if background_tasks is not None:
            background_tasks.add_task(_safe_remove, str(saved_path))
        raise HTTPException(status_code=500, detail="Failed to process image.") from exc

    # Schedule deletion of the file after response is returned
    if background_tasks is not None:
        background_tasks.add_task(_safe_remove, str(saved_path))
    else:
        # Fallback: try removing now (best-effort); background tasks are recommended.
        _safe_remove(str(saved_path))

    # Validate/convert result into Receipt model (FastAPI does this automatically for response_model)
    return result

def _safe_remove(path: str):
    """Remove path if exists; swallow exceptions to avoid crashing background task."""
    try:
        os.remove(path)
        logger.info("Deleted temporary upload: %s", path)
    except FileNotFoundError:
        logger.debug("File already removed: %s", path)
    except Exception:
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path
import shutil
import uuid
import os
import logging

# Import the processing service (Phase 2 will implement this)
from services.receipt_processor import process_image  # should be async

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# App and CORS (development: allow all origins)
app = FastAPI(title="Receipt Processing API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Upload directory: backend/app/uploads/
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "app" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Pydantic models for response (ensure service returns this shape)
class Item(BaseModel):
    description: str
    quantity: Optional[int] = None
    price: Optional[float] = None

class Receipt(BaseModel):
    vendor: Optional[str] = None
    date: Optional[str] = None  # ISO date string preferred
    total: Optional[float] = None
    currency: Optional[str] = None
    items: List[Item] = []

@app.post("/upload-receipt", response_model=Receipt)
async def upload_receipt(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    """
    Accept an image file, save to backend/app/uploads/, call process_image,
    and ensure the temporary file is deleted after the response is returned.
    """
    # Basic validation: accept only images
    content_type = (file.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are allowed.")

    # Generate a safe unique filename
    suffix = Path(file.filename).suffix or ""
    unique_name = f"{uuid.uuid4().hex}{suffix}"
    saved_path = UPLOAD_DIR / unique_name

    # Save uploaded file to disk
    try:
        # file.file is a SpooledTemporaryFile; using shutil to write to destination
        with saved_path.open("wb") as out_file:
            file.file.seek(0)
            shutil.copyfileobj(file.file, out_file)
        logger.info("Saved upload to %s", saved_path)
    except Exception as exc:
        logger.exception("Failed to save uploaded file: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to save uploaded file.") from exc
    finally:
        # Close the uploaded file object
        try:
            file.file.close()
        except Exception:
            pass

    # Call the processing service. Expect an object/dict that matches Receipt model.
    try:
        # process_image should be implemented as an async function in services/receipt_processor.py
        result = await process_image(str(saved_path))
    except Exception as exc:
        logger.exception("Error while processing image: %s", exc)
        # Schedule cleanup even on processing failure
        if background_tasks is not None:
            background_tasks.add_task(_safe_remove, str(saved_path))
        raise HTTPException(status_code=500, detail="Failed to process image.") from exc

    # Schedule deletion of the file after response is returned
    if background_tasks is not None:
        background_tasks.add_task(_safe_remove, str(saved_path))
    else:
        # Fallback: try removing now (best-effort); background tasks are recommended.
        _safe_remove(str(saved_path))

    # Validate/convert result into Receipt model (FastAPI does this automatically for response_model)
    return result

def _safe_remove(path: str):
    """Remove path if exists; swallow exceptions to avoid crashing background task."""
    try:
        os.remove(path)
        logger.info("Deleted temporary upload: %s", path)
    except FileNotFoundError:
        logger.debug("File already removed: %s", path)
    except Exception:
        logger.exception("Failed to delete temporary upload: %s", path)