import os
import json
import re
from typing import List, Dict, Any, Optional
import httpx
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present (optional - install python-dotenv and add to requirements if you want this)
load_dotenv()

# Placeholder / env var for OpenAI API key
# Set this in your environment before running the server:
# export OPENAI_API_KEY="sk-..."
# or create a .env with OPENAI_API_KEY=sk-...
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # <- PLACEHOLDER

# Recommended model name (verify current model name with OpenAI docs)
# Examples: "gpt-4o-mini-vision", "gpt-4o-vision-preview", etc.
# Update this to the exact vision-capable model name you have access to.
OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini-vision")

# Example schema we must return (matching backend/main.py Receipt model)
# Receipt: { vendor: Optional[str], date: Optional[str], total: Optional[float],
#            currency: Optional[str], items: List[{description, quantity?, price?}] }

async def process_image(image_path: str) -> Dict[str, Any]:
    """
    Process the image at image_path using an AI Vision model (OpenAI GPT-4o Vision).
    Returns a dict that matches the Receipt pydantic model:
      {
        "vendor": "Vendor Name" | None,
        "date": "YYYY-MM-DD" | None,
        "total": 12.34 | None,
        "currency": "USD" | None,
        "items": [
            {"description": "Item A", "quantity": 1, "price": 3.50},
            ...
        ]
      }

    Notes:
    - You must set OPENAI_API_KEY in the environment before running.
    - The exact request shape for OpenAI Vision APIs changes; the implementation below
      uses an HTTP POST to the /v1/responses endpoint with the image attached as a file.
      You should verify and adapt to the current OpenAI SDK / REST API contract.
    """

    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY not set. Configure it as an environment variable (export OPENAI_API_KEY=...) "
            "or add it to a .env file and install python-dotenv."
        )

    p = Path(image_path)
    if not p.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    # Read image bytes
    image_bytes = p.read_bytes()

    # Instruction for the model: be precise, return JSON only following schema
    # We instruct the model to output JSON matching the schema exactly, so we can parse it.
    prompt = (
        "You are an assistant that extracts structured data from a photo of a receipt. "
        "Return ONLY a JSON object with the following fields: "
        '{"vendor": string or null, "date": string in ISO format (YYYY-MM-DD) or null, '
        '"total": number or null, "currency": string or null, '
        '"items": [ {"description": string, "quantity": integer or null, "price": number or null} ] } '
        "If a field cannot be determined, set it to null. Do not include any extra keys or commentary."
        "\n\nParse the receipt in the attached image and return the JSON."
    )

    url = "https://api.openai.com/v1/responses"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        # Do not set Content-Type; httpx will set the multipart boundary automatically
    }

    # Build multipart/form-data: model + input text + file
    # NOTE: The exact field names expected by OpenAI's vision-capable responses endpoint may vary.
    # If OpenAI's API expects a different shape (e.g., 'messages' or JSON body with base64 image),
    # adapt this request accordingly (consult current OpenAI docs).
    data = {
        "model": OPENAI_VISION_MODEL,
        # Provide textual instructions as a single "input" or similar field.
        # Some OpenAI variants accept "input" as string; others accept "messages".
        # If your account's model expects "input" structured as an array or "messages", change this.
        "input": prompt,
    }

    files = {
        # Attach the image bytes as a multipart file. Field name 'file' is commonly accepted for file uploads.
        # If OpenAI expects 'image' or another name, update accordingly.
        "file": (p.name, image_bytes, "application/octet-stream"),
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(url, headers=headers, data=data, files=files)
        except Exception as exc:
            raise RuntimeError(f"Failed to call OpenAI API: {exc}") from exc

    if resp.status_code >= 400:
        # Bubble up a helpful error
        try:
            err = resp.json()
        except Exception:
            err = resp.text
        raise RuntimeError(f"OpenAI API error: {resp.status_code} - {err}")

    # Parse the model response. The exact response shape depends on the API.
    # Try to extract text content where the model returned JSON.
    try:
        body = resp.json()
    except Exception:
        raise RuntimeError("Failed to parse JSON response from OpenAI API.")

    # Heuristics to find model output text:
    # 1) Some Responses API implementations put a top-level "output[0].content[0].text" or similar.
    # 2) Others include "choices" with "message" or "output_text".
    text_output = None

    # Try several common shapes safely:
    # - New Responses API: body["output"][0]["content"][0]["text"]
    if not text_output:
        try:
            output = body.get("output") or body.get("outputs") or body.get("choices")
            if isinstance(output, list) and len(output) > 0:
                # Search deeply for any "text" or "content" fields
                def extract_text_from_node(node) -> Optional[str]:
                    if not node:
                        return None
                    if isinstance(node, str):
                        return node
                    if isinstance(node, dict):
                        # common keys
                        for k in ("text", "content", "message", "output_text"):
                            v = node.get(k)
                            if isinstance(v, str) and v.strip():
                                return v
                            if isinstance(v, list):
                                # join strings in list
                                strings = [i for i in v if isinstance(i, str)]
                                if strings:
                                    return " ".join(strings)
                        # explore nested
                        for v in node.values():
                            if isinstance(v, (dict, list)):
                                res = extract_text_from_node(v)
                                if res:
                                    return res
                    if isinstance(node, list):
                        for item in node:
                            res = extract_text_from_node(item)
                            if res:
                                return res
                    return None

                text_output = extract_text_from_node(output[0])
        except Exception:
            text_output = None

    # Final fallback: if response has top-level 'text'
    if not text_output:
        text_output = body.get("text") or body.get("output_text") or None

    if not text_output:
        # If we couldn't find textual output, dump the body for debugging.
        # Return an empty Receipt-compatible structure instead of failing.
        return {
            "vendor": None,
            "date": None,
            "total": None,
            "currency": None,
            "items": [],
        }

    # The model should have returned a JSON object. Attempt to locate and parse JSON from the text.
    json_candidate = None
    # Try direct parse first
    try:
        parsed = json.loads(text_output)
        json_candidate = parsed
    except Exception:
        # Try to extract a JSON substring using regex (first { ... } block)
        m = re.search(r"(\{(?:.|\s)*\})", text_output)
        if m:
            try:
                json_candidate = json.loads(m.group(1))
            except Exception:
                json_candidate = None

    # If we have parsed JSON, validate keys and coerce types
    if isinstance(json_candidate, dict):
        receipt = _coerce_to_receipt(json_candidate)
        return receipt

    # If parsing failed, return an empty receipt (or consider raising)
    return {
        "vendor": None,
        "date": None,
        "total": None,
        "currency": None,
        "items": [],
    }


def _coerce_to_receipt(obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Take a loosely-structured dict and coerce into the Receipt schema,
    performing some basic normalization and type conversions.
    """
    vendor = _safe_str(obj.get("vendor"))
    date = _safe_str(obj.get("date"))
    total = _safe_number(obj.get("total"))
    currency = _safe_str(obj.get("currency"))

    items_raw = obj.get("items") or []
    items: List[Dict[str, Any]] = []
    if isinstance(items_raw, list):
        for it in items_raw:
            if not isinstance(it, dict):
                continue
            desc = _safe_str(it.get("description") or it.get("name") or it.get("item"))
            qty = _safe_int(it.get("quantity") or it.get("qty"))
            price = _safe_number(it.get("price") or it.get("amount"))
            if desc is None:
                # Skip items with no description
                continue
            items.append({"description": desc, "quantity": qty, "price": price})

    return {
        "vendor": vendor,
        "date": date,
        "total": total,
        "currency": currency,
        "items": items,
    }


def _safe_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        return s if s else None
    try:
        return str(v)
    except Exception:
        return None


def _safe_number(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            # remove common currency symbols and commas
            cleaned = re.sub(r"[^\d\.\-]", "", v)
            if cleaned == "":
                return None
            return float(cleaned)
        except Exception:
            return None
    return None


def _safe_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    if isinstance(v, str):
        try:
            cleaned = re.sub(r"[^\d\-]", "", v)
            if cleaned == "":
                return None
            return int(cleaned)
        except Exception:
            return None
import os
import json
import re
from typing import List, Dict, Any, Optional
import httpx
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present (optional - install python-dotenv and add to requirements if you want this)
load_dotenv()

# Placeholder / env var for OpenAI API key
# Set this in your environment before running the server:
# export OPENAI_API_KEY="sk-..."
# or create a .env with OPENAI_API_KEY=sk-...
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # <- PLACEHOLDER

# Recommended model name (verify current model name with OpenAI docs)
# Examples: "gpt-4o-mini-vision", "gpt-4o-vision-preview", etc.
# Update this to the exact vision-capable model name you have access to.
OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini-vision")

# Example schema we must return (matching backend/main.py Receipt model)
# Receipt: { vendor: Optional[str], date: Optional[str], total: Optional[float],
#            currency: Optional[str], items: List[{description, quantity?, price?}] }

async def process_image(image_path: str) -> Dict[str, Any]:
    """
    Process the image at image_path using an AI Vision model (OpenAI GPT-4o Vision).
    Returns a dict that matches the Receipt pydantic model:
      {
        "vendor": "Vendor Name" | None,
        "date": "YYYY-MM-DD" | None,
        "total": 12.34 | None,
        "currency": "USD" | None,
        "items": [
            {"description": "Item A", "quantity": 1, "price": 3.50},
            ...
        ]
      }

    Notes:
    - You must set OPENAI_API_KEY in the environment before running.
    - The exact request shape for OpenAI Vision APIs changes; the implementation below
      uses an HTTP POST to the /v1/responses endpoint with the image attached as a file.
      You should verify and adapt to the current OpenAI SDK / REST API contract.
    """

    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY not set. Configure it as an environment variable (export OPENAI_API_KEY=...) "
            "or add it to a .env file and install python-dotenv."
        )

    p = Path(image_path)
    if not p.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    # Read image bytes
    image_bytes = p.read_bytes()

    # Instruction for the model: be precise, return JSON only following schema
    # We instruct the model to output JSON matching the schema exactly, so we can parse it.
    prompt = (
        "You are an assistant that extracts structured data from a photo of a receipt. "
        "Return ONLY a JSON object with the following fields: "
        '{"vendor": string or null, "date": string in ISO format (YYYY-MM-DD) or null, '
        '"total": number or null, "currency": string or null, '
        '"items": [ {"description": string, "quantity": integer or null, "price": number or null} ] } '
        "If a field cannot be determined, set it to null. Do not include any extra keys or commentary."
        "\n\nParse the receipt in the attached image and return the JSON."
    )

    url = "https://api.openai.com/v1/responses"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        # Do not set Content-Type; httpx will set the multipart boundary automatically
    }

    # Build multipart/form-data: model + input text + file
    # NOTE: The exact field names expected by OpenAI's vision-capable responses endpoint may vary.
    # If OpenAI's API expects a different shape (e.g., 'messages' or JSON body with base64 image),
    # adapt this request accordingly (consult current OpenAI docs).
    data = {
        "model": OPENAI_VISION_MODEL,
        # Provide textual instructions as a single "input" or similar field.
        # Some OpenAI variants accept "input" as string; others accept "messages".
        # If your account's model expects "input" structured as an array or "messages", change this.
        "input": prompt,
    }

    files = {
        # Attach the image bytes as a multipart file. Field name 'file' is commonly accepted for file uploads.
        # If OpenAI expects 'image' or another name, update accordingly.
        "file": (p.name, image_bytes, "application/octet-stream"),
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(url, headers=headers, data=data, files=files)
        except Exception as exc:
            raise RuntimeError(f"Failed to call OpenAI API: {exc}") from exc

    if resp.status_code >= 400:
        # Bubble up a helpful error
        try:
            err = resp.json()
        except Exception:
            err = resp.text
        raise RuntimeError(f"OpenAI API error: {resp.status_code} - {err}")

    # Parse the model response. The exact response shape depends on the API.
    # Try to extract text content where the model returned JSON.
    try:
        body = resp.json()
    except Exception:
        raise RuntimeError("Failed to parse JSON response from OpenAI API.")

    # Heuristics to find model output text:
    # 1) Some Responses API implementations put a top-level "output[0].content[0].text" or similar.
    # 2) Others include "choices" with "message" or "output_text".
    text_output = None

    # Try several common shapes safely:
    # - New Responses API: body["output"][0]["content"][0]["text"]
    if not text_output:
        try:
            output = body.get("output") or body.get("outputs") or body.get("choices")
            if isinstance(output, list) and len(output) > 0:
                # Search deeply for any "text" or "content" fields
                def extract_text_from_node(node) -> Optional[str]:
                    if not node:
                        return None
                    if isinstance(node, str):
                        return node
                    if isinstance(node, dict):
                        # common keys
                        for k in ("text", "content", "message", "output_text"):
                            v = node.get(k)
                            if isinstance(v, str) and v.strip():
                                return v
                            if isinstance(v, list):
                                # join strings in list
                                strings = [i for i in v if isinstance(i, str)]
                                if strings:
                                    return " ".join(strings)
                        # explore nested
                        for v in node.values():
                            if isinstance(v, (dict, list)):
                                res = extract_text_from_node(v)
                                if res:
                                    return res
                    if isinstance(node, list):
                        for item in node:
                            res = extract_text_from_node(item)
                            if res:
                                return res
                    return None

                text_output = extract_text_from_node(output[0])
        except Exception:
            text_output = None

    # Final fallback: if response has top-level 'text'
    if not text_output:
        text_output = body.get("text") or body.get("output_text") or None

    if not text_output:
        # If we couldn't find textual output, dump the body for debugging.
        # Return an empty Receipt-compatible structure instead of failing.
        return {
            "vendor": None,
            "date": None,
            "total": None,
            "currency": None,
            "items": [],
        }

    # The model should have returned a JSON object. Attempt to locate and parse JSON from the text.
    json_candidate = None
    # Try direct parse first
    try:
        parsed = json.loads(text_output)
        json_candidate = parsed
    except Exception:
        # Try to extract a JSON substring using regex (first { ... } block)
        m = re.search(r"(\{(?:.|\s)*\})", text_output)
        if m:
            try:
                json_candidate = json.loads(m.group(1))
            except Exception:
                json_candidate = None

    # If we have parsed JSON, validate keys and coerce types
    if isinstance(json_candidate, dict):
        receipt = _coerce_to_receipt(json_candidate)
        return receipt

    # If parsing failed, return an empty receipt (or consider raising)
    return {
        "vendor": None,
        "date": None,
        "total": None,
        "currency": None,
        "items": [],
    }


def _coerce_to_receipt(obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Take a loosely-structured dict and coerce into the Receipt schema,
    performing some basic normalization and type conversions.
    """
    vendor = _safe_str(obj.get("vendor"))
    date = _safe_str(obj.get("date"))
    total = _safe_number(obj.get("total"))
    currency = _safe_str(obj.get("currency"))

    items_raw = obj.get("items") or []
    items: List[Dict[str, Any]] = []
    if isinstance(items_raw, list):
        for it in items_raw:
            if not isinstance(it, dict):
                continue
            desc = _safe_str(it.get("description") or it.get("name") or it.get("item"))
            qty = _safe_int(it.get("quantity") or it.get("qty"))
            price = _safe_number(it.get("price") or it.get("amount"))
            if desc is None:
                # Skip items with no description
                continue
            items.append({"description": desc, "quantity": qty, "price": price})

    return {
        "vendor": vendor,
        "date": date,
        "total": total,
        "currency": currency,
        "items": items,
    }


def _safe_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        return s if s else None
    try:
        return str(v)
    except Exception:
        return None


def _safe_number(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            # remove common currency symbols and commas
            cleaned = re.sub(r"[^\d\.\-]", "", v)
            if cleaned == "":
                return None
            return float(cleaned)
        except Exception:
            return None
    return None


def _safe_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    if isinstance(v, str):
        try:
            cleaned = re.sub(r"[^\d\-]", "", v)
            if cleaned == "":
                return None
            return int(cleaned)
        except Exception:
            return None
    return None