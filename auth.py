from fastapi import Header, HTTPException
from config import REQUIRED_API_KEY

def verify_api_key(x_api_key: str = Header(None, alias="X-API-KEY")):
    if REQUIRED_API_KEY and x_api_key != REQUIRED_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return x_api_key
