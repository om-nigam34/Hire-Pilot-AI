"""
llm_client.py
-------------
Wraps the two chained LLM calls that make this an *agent* rather than a
score-and-done tool:

  1. evaluate_resume()      -> finds skill gaps, keyword gaps, weak bullets
  2. generate_improvements() -> takes call 1's findings and produces
                                 rewritten bullets + likely interview
                                 questions, grounded in those specific gaps

Both calls ask the model for structured JSON so app.py can use the result
programmatically instead of scraping free text.

Uses Groq's OpenAI-compatible chat completions API. Swap GROQ_MODEL in .env
if you want a different model.
"""

import os
import json
from groq import Groq


class LLMClientError(Exception):
    """Raised for missing config or a call that fails after retrying."""
    pass


class LLMResponseError(Exception):
    """Raised when the model's response can't be parsed as the expected JSON."""
    pass


def _get_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key or api_key == "your_groq_api_key_here":
        raise LLMClientError(
            "No Groq API key configured. Copy .env.example to .env and set "
            "GROQ_API_KEY to a real key from https://console.groq.com/keys."
        )
    return Groq(api_key=api_key)


def _get_model() -> str:
    return os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")


def _call_json(client: Groq, system_prompt: str, user_prompt: str) -> dict:
    """Shared helper: call the model, ask for JSON, parse it, and raise a
    clear error if the model didn't return valid JSON."""
    try:
        response = client.chat.completions.create(
            model=_get_model(),
            temperature=0.3,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception as exc:
        raise LLMClientError(f"The LLM API call failed: {exc}") from exc

    raw_content = response.choices[0].message.content

    try:
        return json.loads(raw_content)
    except (json.JSONDecodeError, TypeError) as exc:
        raise LLMResponseError(
            "The model didn't return valid JSON. Raw response was:\n"
            f"{raw_content}"
        ) from exc


# ---------------------------------------------------------------------------
# Call 1: evaluate
# ---------------------------------------------------------------------------

_EVALUATE_SYSTEM_PROMPT = """\
You are a blunt, experienced technical recruiter. You evaluate a resume \
against a specific job description and report gaps honestly - you do not \
soften feedback or give generic advice. You only comment on what is \
actually present in the resume text and the job description text you are \
given; never invent experience or requirements that aren't there.

Respond with ONLY a JSON object matching this exact shape, no prose outside \
the JSON:

{
  "missing_skills": ["short phrase", ...],
  "keyword_gaps": ["exact keyword/phrase from the JD not found in the resume", ...],
  "weak_bullets": [
    {"original": "verbatim bullet text from the resume", "reason": "why it's weak - e.g. no metric, vague verb, buried impact"}
  ],
  "overall_summary": "2-3 sentence honest summary of how this candidate stacks up against this specific JD"
}

Guidelines:
- missing_skills: skills/requirements the JD asks for that the resume gives no evidence of.
- keyword_gaps: specific ATS-relevant terms from the JD that are absent from the resume, phrased exactly as they'd need to appear.
- weak_bullets: pick up to 5 of the resume's weakest bullets - prioritize ones relevant to this JD. A bullet is weak if it's unquantified, describes a duty instead of an outcome, or uses a vague verb ("helped with", "worked on").
- If the resume is genuinely strong for this JD, say so plainly in overall_summary and keep the gap lists short rather than inventing problems.
"""

_EVALUATE_USER_TEMPLATE = """\
JOB DESCRIPTION:
{jd_text}

RESUME:
{resume_text}
"""


def evaluate_resume(resume_text: str, jd_text: str) -> dict:
    """
    LLM call 1. Returns a dict with keys:
    missing_skills, keyword_gaps, weak_bullets, overall_summary.
    """
    client = _get_client()
    user_prompt = _EVALUATE_USER_TEMPLATE.format(jd_text=jd_text, resume_text=resume_text)
    result = _call_json(client, _EVALUATE_SYSTEM_PROMPT, user_prompt)

    # Normalize shape defensively so a slightly-off model response doesn't
    # crash the frontend - missing keys become empty defaults.
    return {
        "missing_skills": result.get("missing_skills", []),
        "keyword_gaps": result.get("keyword_gaps", []),
        "weak_bullets": result.get("weak_bullets", []),
        "overall_summary": result.get("overall_summary", ""),
    }


# ---------------------------------------------------------------------------
# Call 2: generate (chained on call 1's output)
# ---------------------------------------------------------------------------

_GENERATE_SYSTEM_PROMPT = """\
You are a career coach who writes sharp, specific resume bullets and asks \
realistic interview questions. You have already been given a gap analysis \
of a resume against a job description - your job now is to ACT on those \
specific findings, not give generic advice.

Respond with ONLY a JSON object matching this exact shape, no prose outside \
the JSON:

{
  "rewritten_bullets": [
    {"original": "verbatim weak bullet", "rewritten": "improved version", "why_better": "one sentence on what changed and why it matters for this JD"}
  ],
  "interview_questions": [
    {"question": "likely interview question", "why_they_might_ask": "one sentence tying it to a specific gap or requirement from the JD"}
  ]
}

Guidelines:
- rewritten_bullets: rewrite EVERY bullet listed in weak_bullets below. Keep them truthful to the original content - add structure (action, mechanism, measurable outcome) rather than inventing achievements or numbers that weren't implied.
- If a bullet has no implied metric at all, rewrite it to foreground scope/impact honestly instead of fabricating a number.
- interview_questions: produce 4-5 questions a real interviewer would plausibly ask for THIS role, weighted toward the missing_skills and keyword_gaps provided. Mix behavioral and technical questions.
"""

_GENERATE_USER_TEMPLATE = """\
JOB DESCRIPTION:
{jd_text}

RESUME:
{resume_text}

GAP ANALYSIS FROM PREVIOUS STEP:
{evaluation_json}
"""


def generate_improvements(evaluation: dict, resume_text: str, jd_text: str) -> dict:
    """
    LLM call 2, chained on call 1's output. Returns a dict with keys:
    rewritten_bullets, interview_questions.
    """
    client = _get_client()
    user_prompt = _GENERATE_USER_TEMPLATE.format(
        jd_text=jd_text,
        resume_text=resume_text,
        evaluation_json=json.dumps(evaluation, indent=2),
    )
    result = _call_json(client, _GENERATE_SYSTEM_PROMPT, user_prompt)

    return {
        "rewritten_bullets": result.get("rewritten_bullets", []),
        "interview_questions": result.get("interview_questions", []),
    }