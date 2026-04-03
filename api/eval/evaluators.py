"""
Custom LLM-as-judge evaluators for RAG quality scoring.

Three evaluators:
    relevance            — Does the answer address the question?
    groundedness         — Is the answer supported by retrieved context?
    retrieval_relevance  — Did the retriever fetch useful chunks?

Each function follows the LangSmith evaluator signature:
    (inputs: dict, outputs: dict) -> dict with {"key": str, "score": float}
"""

import os
from typing_extensions import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# ---------------------------------------------------------------------------
# Judge LLM — non-streaming, temperature=0 for deterministic grading
# ---------------------------------------------------------------------------

_judge_llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0,
    streaming=False,
)


# ---------------------------------------------------------------------------
# Structured output schemas
# ---------------------------------------------------------------------------

class RelevanceGrade(TypedDict):
    """Structured output for the relevance judge."""

    reasoning: Annotated[str, ..., "Step-by-step reasoning for the grade"]
    relevant: Annotated[bool, ..., "True if the answer addresses the question"]


class GroundednessGrade(TypedDict):
    """Structured output for the groundedness judge."""

    reasoning: Annotated[str, ..., "Step-by-step reasoning for the grade"]
    grounded: Annotated[bool, ..., "True if every claim is supported by context"]


class RetrievalRelevanceGrade(TypedDict):
    """Structured output for the retrieval relevance judge."""

    reasoning: Annotated[str, ..., "Step-by-step reasoning for the grade"]
    relevant: Annotated[bool, ..., "True if retrieved docs are relevant to the question"]


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_RELEVANCE_INSTRUCTIONS = (
    "You are grading whether an AI assistant's answer addresses the question asked.\n"
    "Grade True if the answer is on-topic and attempts to answer the question.\n"
    "Grade False if the answer is off-topic, refuses to answer, or ignores the question.\n"
    "Explain your reasoning step by step before giving a final verdict."
)

_GROUNDEDNESS_INSTRUCTIONS = (
    "You are checking whether an AI assistant's answer is supported by the provided context.\n"
    "Grade True if every factual claim in the answer can be found in or inferred from the context.\n"
    "Grade False if the answer contains claims not present in the context (hallucination).\n"
    "Explain your reasoning step by step before giving a final verdict."
)

_RETRIEVAL_RELEVANCE_INSTRUCTIONS = (
    "You are checking whether retrieved documents are relevant to a question.\n"
    "Grade True if the documents contain information that could help answer the question.\n"
    "Grade False if the documents are mostly unrelated to the question.\n"
    "Explain your reasoning step by step before giving a final verdict."
)


# ---------------------------------------------------------------------------
# Judge instances with structured output
# ---------------------------------------------------------------------------

_relevance_judge = _judge_llm.with_structured_output(RelevanceGrade)
_groundedness_judge = _judge_llm.with_structured_output(GroundednessGrade)
_retrieval_relevance_judge = _judge_llm.with_structured_output(RetrievalRelevanceGrade)


# ---------------------------------------------------------------------------
# Evaluator functions (LangSmith-compatible signatures)
# ---------------------------------------------------------------------------


def relevance(inputs: dict, outputs: dict) -> dict:
    """
    Judge whether the answer addresses the question.

    Args:
        inputs: Must contain "question" (str).
        outputs: Must contain "answer" (str).

    Returns:
        dict: {"key": "relevance", "score": 1.0 or 0.0}
    """
    prompt = f"QUESTION: {inputs['question']}\nANSWER: {outputs['answer']}"
    grade = _relevance_judge.invoke([
        {"role": "system", "content": _RELEVANCE_INSTRUCTIONS},
        {"role": "user", "content": prompt},
    ])
    return {"key": "relevance", "score": 1.0 if grade["relevant"] else 0.0}


def groundedness(inputs: dict, outputs: dict) -> dict:
    """
    Judge whether the answer is supported by the retrieved documents.

    Args:
        inputs: Not used directly (question available but not needed).
        outputs: Must contain "answer" (str) and "documents" (list of dicts
            with "page_content" key).

    Returns:
        dict: {"key": "groundedness", "score": 1.0 or 0.0}
    """
    docs_text = "\n\n".join(d["page_content"] for d in outputs.get("documents", []))
    prompt = f"CONTEXT:\n{docs_text}\n\nANSWER: {outputs['answer']}"
    grade = _groundedness_judge.invoke([
        {"role": "system", "content": _GROUNDEDNESS_INSTRUCTIONS},
        {"role": "user", "content": prompt},
    ])
    return {"key": "groundedness", "score": 1.0 if grade["grounded"] else 0.0}


def retrieval_relevance(inputs: dict, outputs: dict) -> dict:
    """
    Judge whether the retrieved documents are relevant to the question.

    Args:
        inputs: Must contain "question" (str).
        outputs: Must contain "documents" (list of dicts with "page_content" key).

    Returns:
        dict: {"key": "retrieval_relevance", "score": 1.0 or 0.0}
    """
    docs_text = "\n\n".join(d["page_content"] for d in outputs.get("documents", []))
    prompt = f"QUESTION: {inputs['question']}\n\nRETRIEVED DOCUMENTS:\n{docs_text}"
    grade = _retrieval_relevance_judge.invoke([
        {"role": "system", "content": _RETRIEVAL_RELEVANCE_INSTRUCTIONS},
        {"role": "user", "content": prompt},
    ])
    return {"key": "retrieval_relevance", "score": 1.0 if grade["relevant"] else 0.0}
