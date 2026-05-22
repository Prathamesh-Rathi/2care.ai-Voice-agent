from groq import Groq
import os

_client = None

def get_groq_client():
    global _client
    if _client is None:
        _client = Groq(api_key=os.environ.get("Ypur key"))
    return _client