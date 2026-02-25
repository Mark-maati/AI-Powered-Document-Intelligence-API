import logging
from openai import AsyncOpenAI, APIError

from app.config import settings
from app.models.schemas import DocumentAnalysis

logger = logging.getLogger(__name__)

_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

SYSTEM_PROMPT = """
You are an expert document analysis engine.
Given document text, you must return a structured JSON analysis that EXACTLY matches
the requested schema. Be precise, factual, and extract only what is present in the text.
""".strip()

MAX_TEXT_CHARS = 12_000  # stay well within context window


class LLMAnalysisError(Exception):
    pass


async def analyze_document(text: str) -> DocumentAnalysis:
    """
    Send document text to OpenAI and parse the response into a
    validated Pydantic DocumentAnalysis model. OpenAI's structured
    output (response_format) guarantees the JSON matches our schema.
    """
    # Truncate if needed — prefer the start of the document
    truncated_text = text[:MAX_TEXT_CHARS]
    if len(text) > MAX_TEXT_CHARS:
        logger.warning("Document truncated from %d to %d chars", len(text), MAX_TEXT_CHARS)

    user_prompt = f"""
Analyze the following document and return structured data as per the schema.

--- DOCUMENT START ---
{truncated_text}
--- DOCUMENT END ---
""".strip()

    try:
        completion = await _client.beta.chat.completions.parse(
            model=settings.OPENAI_MODEL,
            temperature=0.1,  # low temp = more deterministic structured output
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format=DocumentAnalysis,  # enforces Pydantic schema
        )
    except APIError as e:
        raise LLMAnalysisError(f"OpenAI API error: {e}") from e

    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise LLMAnalysisError("LLM returned a null or unparseable response.")

    return parsed  # already a validated DocumentAnalysis instance
