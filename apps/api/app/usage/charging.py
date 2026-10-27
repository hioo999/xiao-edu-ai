from contextlib import contextmanager
import uuid

from .service import UsageLedger
from .credits import student_credit_context


@contextmanager
def generation_charge(auth, ledger: UsageLedger | None, session, metric: str = "text"):
    reservation_id = f"generation-{uuid.uuid4().hex}"
    selected = None
    if ledger is not None:
        user = auth.user_for_id(session.user_id)
        scopes = [("student", session.user_id)]
        if user and user.class_id:
            scopes.append(("class", user.class_id))
        scopes.append(("organization", session.organization_id))
        selected = ledger.reserve_with_fallback(scopes, metric, 1, reservation_id=reservation_id)
    try:
        with student_credit_context(ledger, session):
            yield
    except BaseException:
        if selected:
            ledger.release(reservation_id)
        raise
    else:
        if selected:
            ledger.finalize(reservation_id)
