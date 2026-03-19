import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


def get_llm(provider: str, model: str | None = None, temperature: float | None = None):
    """
    Return a LangChain chat model for the given provider.

    Args:
        provider: LLM provider, either "google" or "openrouter".
        model: Model ID to use; falls back to provider default if None.
        temperature: Sampling temperature; uses provider default if None.

    Returns:
        ChatGoogleGenerativeAI | ChatOpenAI: Configured LangChain chat model.

    Raises:
        ValueError: If provider is not "google" or "openrouter".
    """
    if provider == "google":
        return ChatGoogleGenerativeAI(
            model=model or "gemini-2.5-flash",
            google_api_key=GOOGLE_API_KEY,
            temperature=temperature if temperature is not None else 1.0,
        )
    elif provider == "openrouter":
        return ChatOpenAI(
            model=model or "openai/gpt-4o",
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
            temperature=temperature if temperature is not None else 0.7,
        )
    else:
        raise ValueError(f"Unsupported provider: {provider}")
