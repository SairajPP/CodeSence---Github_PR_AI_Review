import os
import random
from langchain_groq import ChatGroq

def get_llm(model_name="llama-3.1-8b-instant"):
    """Returns a configured instance of the Groq LLM, distributing load across multiple API keys."""
    # Gather all available GROQ_API_KEYs (e.g., GROQ_API_KEY, GROQ_API_KEY2, etc.)
    api_keys = [value for key, value in os.environ.items() if key.startswith("GROQ_API_KEY") and value.strip()]
    
    if not api_keys:
        raise ValueError("No GROQ_API_KEY environment variables are set")
    
    # Randomly select one key from the pool to avoid rate limiting
    selected_key = random.choice(api_keys)
    
    return ChatGroq(
        api_key=selected_key,
        model_name=model_name,
        temperature=0, # 0 for more deterministic and logical code reviews
        max_tokens=4000
    )
