from dotenv import load_dotenv
import os

load_dotenv()

def get_env(name):
    return os.environ.get(name)

def get_required_env(name):
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"{name} is required")
    return value

OPEN_AI_KEY_ENV = "OPEN_AI_KEY"
X_API_KEY_ENV = "X_API_KEY"