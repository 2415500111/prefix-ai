"""The only place the assistant talks to an LLM (safety rules a and c).

Every patient text is de-identified here, inside the client, so no caller can forget it.
The model is told the protocol steps are its only source and returns structured JSON;
the pipeline then checks that output before anything reaches the patient. Any failure
(API error, refusal, truncation, malformed output) raises ``AssistantLLMError`` and the
pipeline escalates to a person.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import anthropic
from anthropic.types import MessageParam, OutputConfigParam

from prefix_api.core.config import Settings
from prefix_api.core.logging import get_logger
from prefix_api.domain.deidentify import deidentify
from prefix_api.prompts import load_prompt
from prefix_api.services.translation import LANGUAGE_NAMES

logger = get_logger(__name__)

PROMPT_VERSION = "assistant-v1"
_TRIAGE_PROMPT = "assistant_triage_v1"
_ANSWER_PROMPT = "assistant_answer_v1"
MAX_QUESTION_CHARS = 1000
Effort = Literal["low", "medium", "high"]

_TRIAGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "red_flag": {"type": "boolean"},
        "about_prep": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["red_flag", "about_prep", "reason"],
    "additionalProperties": False,
}
_ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "covered": {"type": "boolean"},
        "answer": {"type": "string"},
        "cited_steps": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["covered", "answer", "cited_steps"],
    "additionalProperties": False,
}


class AssistantLLMError(Exception):
    """The LLM could not give a usable result; the question goes to a person."""


@dataclass(frozen=True, slots=True)
class StepContext:
    """One approved step as the LLM sees it: a short reference, never a database id."""

    ref: str
    title: str
    instruction: str
    timing: str


@dataclass(frozen=True, slots=True)
class Triage:
    red_flag: bool
    about_prep: bool
    reason: str


@dataclass(frozen=True, slots=True)
class Answer:
    covered: bool
    text: str
    cited_refs: tuple[str, ...]


class AssistantLLM(Protocol):
    @property
    def model(self) -> str: ...

    def triage(self, question: str, *, names: Sequence[str]) -> Triage: ...

    def answer(
        self,
        question: str,
        *,
        names: Sequence[str],
        steps: Sequence[StepContext],
        procedure: str,
        time_to_procedure: str,
        language: str,
    ) -> Answer: ...


def triage_message(question: str, names: Sequence[str]) -> str:
    redacted = deidentify(question[:MAX_QUESTION_CHARS], names=names).text
    return f"<message>\n{redacted}\n</message>"


def answer_message(
    question: str,
    *,
    names: Sequence[str],
    steps: Sequence[StepContext],
    procedure: str,
    time_to_procedure: str,
    language: str,
) -> str:
    redacted = deidentify(question[:MAX_QUESTION_CHARS], names=names).text
    reply_in = LANGUAGE_NAMES.get(language.split("-")[0], "English")
    lines = "\n".join(f"[{s.ref}] ({s.timing}) {s.title}: {s.instruction}" for s in steps)
    return (
        f"Procedure: {procedure}, {time_to_procedure}.\n"
        f"Reply in: {reply_in}\n"
        f"<steps>\n{lines}\n</steps>\n"
        f"<question>\n{redacted}\n</question>"
    )


class ClaudeAssistantLLM:
    def __init__(self, client: anthropic.Anthropic, model: str) -> None:
        self._client = client
        self._model = model
        self._triage_prompt = load_prompt(_TRIAGE_PROMPT)
        self._answer_prompt = load_prompt(_ANSWER_PROMPT)

    @property
    def model(self) -> str:
        return self._model

    def triage(self, question: str, *, names: Sequence[str]) -> Triage:
        data = self._call(
            system=self._triage_prompt,
            content=triage_message(question, names),
            schema=_TRIAGE_SCHEMA,
            effort="low",
            max_tokens=4000,
        )
        return Triage(
            red_flag=bool(data["red_flag"]),
            about_prep=bool(data["about_prep"]),
            reason=str(data["reason"])[:200],
        )

    def answer(
        self,
        question: str,
        *,
        names: Sequence[str],
        steps: Sequence[StepContext],
        procedure: str,
        time_to_procedure: str,
        language: str,
    ) -> Answer:
        data = self._call(
            system=self._answer_prompt,
            content=answer_message(
                question,
                names=names,
                steps=steps,
                procedure=procedure,
                time_to_procedure=time_to_procedure,
                language=language,
            ),
            schema=_ANSWER_SCHEMA,
            effort="medium",
            max_tokens=8000,
        )
        return Answer(
            covered=bool(data["covered"]),
            text=str(data["answer"]).strip(),
            cited_refs=tuple(str(ref) for ref in data["cited_steps"]),
        )

    def _call(
        self,
        *,
        system: str,
        content: str,
        schema: dict[str, Any],
        effort: Effort,
        max_tokens: int,
    ) -> dict[str, Any]:
        output_config: OutputConfigParam = {
            "effort": effort,
            "format": {"type": "json_schema", "schema": schema},
        }
        messages: list[MessageParam] = [{"role": "user", "content": content}]
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                output_config=output_config,
                messages=messages,
            )
        except anthropic.APIError as exc:
            logger.warning("assistant.llm_failed", error=type(exc).__name__)
            raise AssistantLLMError(f"LLM unavailable ({type(exc).__name__})") from exc

        if response.stop_reason != "end_turn":
            logger.warning("assistant.llm_incomplete", stop_reason=response.stop_reason)
            raise AssistantLLMError(f"LLM stopped early ({response.stop_reason})")
        text = "".join(block.text for block in response.content if block.type == "text")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AssistantLLMError("LLM returned invalid JSON") from exc
        if not isinstance(data, dict) or not set(schema["required"]) <= data.keys():
            raise AssistantLLMError("LLM output did not match the schema")
        return data


def build_assistant_llm(settings: Settings) -> AssistantLLM | None:
    """None when no LLM is configured: every question then goes to a nurse."""
    if settings.anthropic_api_key is None:
        return None
    client = anthropic.Anthropic(
        api_key=settings.anthropic_api_key.get_secret_value(),
        timeout=settings.assistant_timeout_seconds,
        max_retries=1,
    )
    return ClaudeAssistantLLM(client, settings.llm_model)
