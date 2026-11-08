"""Provider-neutral config. Blank values fall through; keys never leave config/UI."""
import os
from pathlib import Path
from dotenv import dotenv_values

_ROOT_ENV = Path(__file__).resolve().parent.parent / ".env"


def clear_session_key(state, name):
    """Callback runs before widgets render, clearing both secret copies."""
    state.pop(name, None)
    state.pop("session_api_key_input_" + name, None)



def get_secret(name: str, default: str = "") -> str:
    """Resolve a secret: session key > OS environment > root .env > Streamlit secrets > default."""
    try:
        import streamlit as st
        val = st.session_state.get(name) if name.endswith("_API_KEY") else None
        if val:
            return val
    except Exception:
        pass
    val = os.getenv(name)
    if val:
        return val
    value = dotenv_values(_ROOT_ENV, encoding="utf-8", interpolate=False).get(name)
    if value:
        return value
    try:
        import streamlit as st
        return st.secrets.get(name, default) or default
    except Exception:
        return default
