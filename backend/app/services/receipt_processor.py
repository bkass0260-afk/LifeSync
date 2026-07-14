from app.models.receipt import Receipt

def process_image(image_path: str) -> Receipt:
    # Logic returns a Receipt object that matches our model
    return Receipt(
        merchant_name="Sample Store",
        total_amount=99.99,
        date="2026-07-14",
        category="Testing"
    )
from app.models.receipt import Receipt

def process_image(image_path: str) -> Receipt:
    # Logic returns a Receipt object that matches our model
    return Receipt(
        merchant_name="Sample Store",
        total_amount=99.99,
        date="2026-07-14",
        category="Testing"
    )
