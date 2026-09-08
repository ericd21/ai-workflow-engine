import os
import time
from typing import Optional
from langchain_anthropic import ChatAnthropic
from langsmith import traceable  
from app.logging_config import get_logger


logger = get_logger(__name__)

# Create a reusable client instance
anthropic_client = ChatAnthropic(
    model="claude-3-haiku-20240307",
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    temperature=0.2,
    max_tokens=1000,
)


def call_llm(prompt: str) -> str:
    """
    Call llm with model and provider specified above via LangChain with:
    - API-level retry (max_attempts)
    - latency measurement
    - structured logging

    Returns the raw text content from the model.
    """

    max_attempts = 2
    last_error: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        start_time = time.time()

        try:
            response = anthropic_client.invoke(prompt)
            latency_ms = (time.time() - start_time) * 1000

            # LangChain's ChatAnthropic returns an AIMessage
            output_text = response.content

            # Basic structured logging
            logger.info(
                "LLM call succeeded",
                extra={
                    "model": "claude-3-haiku-20240307",
                    "attempt": attempt,
                    "latency_ms": round(latency_ms, 2),
                    # Token usage is not directly exposed by ChatAnthropic;
                    # if you later switch to the raw Anthropic client,
                    # you can add prompt/completion/total tokens here.
                },
            )

            return output_text

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            last_error = e

            logger.warning(
                "LLM call failed",
                extra={
                    "model": "claude-3-haiku-20240307",
                    "attempt": attempt,
                    "latency_ms": round(latency_ms, 2),
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )

            if attempt < max_attempts:
                continue
            else:
                logger.error(
                    "LLM call failed after max attempts",
                    extra={
                        "model": "claude-3-haiku-20240307",
                        "max_attempts": max_attempts,
                        "final_error_type": type(last_error).__name__,
                        "final_error_message": str(last_error),
                    },
                )
                raise RuntimeError(
                    f"LLM API failed after {max_attempts} attempts: {last_error}"
                )