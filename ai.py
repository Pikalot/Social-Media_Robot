"""Claude-powered helpers: summarize a review for the log, and decide whether
an edited review is still the same complaint.

Needs ANTHROPIC_API_KEY in .env. Without it, both functions fall back to
simple rules so the robot still runs (see each function)."""
import json
import os

import anthropic

MODEL = "claude-opus-5-5"

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _ask_json(prompt: str, schema: dict) -> dict | None:
    """One Claude call returning JSON matching `schema`, or None if Claude is
    unavailable (no key, network/API error, or refusal)."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    try:
        response = _get_client().beta.messages.create(
            model=MODEL,
            max_tokens=1024,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": schema},
            },
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIConnectionError as e:
        print(f"[AI] Network error, using fallback: {e}")
        return None
    except anthropic.APIStatusError as e:
        print(f"[AI] API error {e.status_code}, using fallback: {e.message}")
        return None
    if response.stop_reason == "refusal":
        print("[AI] Request declined, using fallback")
        return None
    text = next((b.text for b in response.content if b.type == "text"), "")
    return json.loads(text)


SUMMARY_PROMPT = """You write the Description column of a bank's social-media monitoring log.
Summarize the customer review below in one short phrase, the way staff write it.
No star rating, no reviewer name, no platform name, no quotes. Under 15 words.

Examples of the log's style:
- Customer's complaint about the loan process
- Non customer complaints the Calendar giving out policy
- Complain - Security guard
- Customer asks for foreign currency exchange

Review:
{text}"""


def summarize(text: str) -> str:
    """Short staff-style summary of a review. Fallback: the review text itself,
    trimmed (or a note if the reviewer left only a rating)."""
    text = (text or "").strip()
    if not text:
        return "Low rating, no written comment"
    result = _ask_json(
        SUMMARY_PROMPT.format(text=text),
        {
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
            "additionalProperties": False,
        },
    )
    if result and result.get("summary", "").strip():
        return result["summary"].strip()
    return text if len(text) <= 120 else text[:117] + "..."


SAME_PROMPT = """A customer edited their review of a bank branch.
Decide whether the edited version is still the SAME complaint, or whether the
meaning changed (a different issue, the issue now resolved, a different
situation). Wording fixes, grammar, rephrasing, adding or removing small
details about the same issue all count as the same complaint.

Original review:
{old}

Edited review:
{new}"""


def is_same_complaint(old_text: str, new_text: str) -> bool:
    """True if an edit keeps the same meaning. Fallback without Claude: treat it
    as the same (never closes a report or adds a row on a guess)."""
    old_text, new_text = (old_text or "").strip(), (new_text or "").strip()
    if old_text == new_text:
        return True
    if not old_text or not new_text:
        return False  # a comment was added to a rating-only review, or removed
    result = _ask_json(
        SAME_PROMPT.format(old=old_text, new=new_text),
        {
            "type": "object",
            "properties": {"same_complaint": {"type": "boolean"}},
            "required": ["same_complaint"],
            "additionalProperties": False,
        },
    )
    if result is None:
        return True
    return bool(result["same_complaint"])
