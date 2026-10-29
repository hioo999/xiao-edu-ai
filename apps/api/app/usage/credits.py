"""Student-facing prepaid credits, rated from provider usage or fixed media tariffs.

The existing per-capability quotas remain independent guardrails. One credit pays
for 1,000 input tokens or 500 output tokens; media prices are per completed job.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import math
import uuid

from .service import UsageLedger


MEDIA_CREDITS = {"image": 8, "music": 12, "video": 30, "voice": 2}
MAX_TEXT_OUTPUT_TOKENS = 4096
_current_meter: ContextVar["StudentCreditMeter | None"] = ContextVar("student_credit_meter", default=None)


def text_credit_cost(input_tokens: int, output_tokens: int) -> int:
    return max(1, math.ceil((max(0, input_tokens) + 2 * max(0, output_tokens)) / 1000))


@dataclass
class StudentCreditMeter:
    ledger: UsageLedger
    student_id: str
    quotes: dict[str, int] = field(default_factory=dict)

    def reserve_text(self, prompt: str, max_output_tokens: int) -> str:
        # UTF-8 bytes bound typical tokenizer input; the extra 512 covers chat framing.
        quoted = text_credit_cost(len(prompt.encode("utf-8")) + 512, max_output_tokens)
        reservation_id = f"text-credit-{uuid.uuid4().hex}"
        self.ledger.reserve("student", self.student_id, "credits", quoted, reservation_id=reservation_id)
        self.quotes[reservation_id] = quoted
        return reservation_id

    def settle_text(self, reservation_id: str, prompt: str, content: str, usage: dict | None) -> tuple[int, int]:
        usage = usage if isinstance(usage, dict) else {}
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")
        if not isinstance(input_tokens, int) or input_tokens < 0:
            input_tokens = len(prompt.encode("utf-8"))
        if not isinstance(output_tokens, int) or output_tokens < 0:
            output_tokens = min(MAX_TEXT_OUTPUT_TOKENS, len(content.encode("utf-8")))
        self.ledger.finalize_amount(reservation_id, min(text_credit_cost(input_tokens, output_tokens), self.quotes.pop(reservation_id)))
        return input_tokens, output_tokens


def current_credit_meter() -> StudentCreditMeter | None:
    return _current_meter.get()


@contextmanager
def student_credit_context(ledger: UsageLedger | None, session):
    if ledger is None or session.role != "student" or not ledger.is_configured("student", session.user_id, "credits"):
        yield
        return
    token = _current_meter.set(StudentCreditMeter(ledger, session.user_id))
    try:
        yield
    finally:
        _current_meter.reset(token)


def reserve_media_credits(ledger: UsageLedger | None, student_id: str, kind: str, job_id: str, video_duration_seconds: int | None = None) -> bool:
    if ledger is None or not ledger.is_configured("student", student_id, "credits"):
        return False
    price = MEDIA_CREDITS[kind] * (2 if kind == "video" and video_duration_seconds == 10 else 1)
    ledger.reserve("student", student_id, "credits", price, reservation_id=f"{job_id}-credits")
    return True
