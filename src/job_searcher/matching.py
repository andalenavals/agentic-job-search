from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class MatchResult:
    semantic_score: float
    llm_score: int | None = None
    llm_reason: str = ""
    llm_error: str = ""

    @property
    def sort_score(self) -> float:
        if self.llm_score is None:
            return self.semantic_score
        return (self.semantic_score + self.llm_score) / 2


class ProfileMatcher:
    def __init__(
        self,
        profile: str,
        ollama_model: str | None = "deepseek-r1:latest",
        ollama_url: str = "http://localhost:11434/api/generate",
        timeout: int = 30,
    ) -> None:
        self.profile = profile
        self.ollama_model = ollama_model
        self.ollama_url = ollama_url
        self.timeout = timeout
        self._llm_unavailable: str | None = None

    def score(self, job_title: str, company: str, description: str) -> MatchResult:
        semantic = semantic_match_score(self.profile, " ".join([job_title, company, description]))
        if not self.ollama_model:
            return MatchResult(semantic_score=semantic)
        llm_score, reason, error = self._score_with_ollama(job_title, company, description)
        return MatchResult(
            semantic_score=semantic,
            llm_score=llm_score,
            llm_reason=reason,
            llm_error=error,
        )

    def _score_with_ollama(self, job_title: str, company: str, description: str) -> tuple[int | None, str, str]:
        if self._llm_unavailable:
            return None, "", self._llm_unavailable
        prompt = build_match_prompt(self.profile, job_title, company, description)
        payload = json.dumps(
            {
                "model": self.ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0},
            }
        ).encode("utf-8")
        request = Request(
            self.ollama_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8", "replace")
        except (OSError, TimeoutError, URLError) as exc:
            self._llm_unavailable = f"Ollama unavailable: {exc}"
            return None, "", self._llm_unavailable

        try:
            data = json.loads(body)
            parsed = parse_llm_match_response(str(data.get("response", "")))
            return parsed
        except (ValueError, TypeError) as exc:
            return None, "", f"Could not parse Ollama response: {exc}"


def semantic_match_score(profile: str, description: str) -> float:
    profile_terms = weighted_terms(profile)
    description_terms = weighted_terms(description)
    if not profile_terms or not description_terms:
        return 0.0
    dot = sum(weight * description_terms.get(term, 0) for term, weight in profile_terms.items())
    profile_norm = math.sqrt(sum(weight * weight for weight in profile_terms.values()))
    description_norm = math.sqrt(sum(weight * weight for weight in description_terms.values()))
    if not profile_norm or not description_norm:
        return 0.0
    return round((dot / (profile_norm * description_norm)) * 100, 1)


def weighted_terms(value: str) -> Counter[str]:
    return Counter(term for term in tokenize(value) if term not in STOP_WORDS)


def tokenize(value: str) -> list[str]:
    return [term for term in re.findall(r"[a-zA-Z0-9+#.]+", value.lower()) if len(term) > 1]


def build_match_prompt(profile: str, job_title: str, company: str, description: str) -> str:
    return (
        "You compare a candidate profile with a job description.\n"
        "Return only compact JSON with this schema: "
        '{"score": 0-100, "reason": "one short reason"}.\n'
        "Score 100 means excellent match; 0 means no match.\n\n"
        f"Candidate profile:\n{profile[:4000]}\n\n"
        f"Job title: {job_title}\n"
        f"Company: {company}\n"
        f"Job description:\n{description[:8000]}\n"
    )


def parse_llm_match_response(value: str) -> tuple[int | None, str, str]:
    without_thinking = re.sub(r"<think>.*?</think>", "", value, flags=re.DOTALL | re.IGNORECASE)
    match = re.search(r"\{.*\}", without_thinking, flags=re.DOTALL)
    if not match:
        raise ValueError("missing JSON object")
    data = json.loads(match.group(0))
    score = int(data["score"])
    score = max(0, min(100, score))
    reason = str(data.get("reason", "")).strip()
    return score, reason, ""


STOP_WORDS = {
    "about",
    "and",
    "are",
    "auf",
    "bei",
    "das",
    "der",
    "die",
    "ein",
    "eine",
    "for",
    "from",
    "im",
    "in",
    "mit",
    "of",
    "or",
    "our",
    "the",
    "to",
    "und",
    "we",
    "with",
    "you",
    "your",
}
