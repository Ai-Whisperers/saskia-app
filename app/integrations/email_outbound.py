"""app/integrations/email_outbound.py — SMTP outbound email with retry.

Tier 8.x (S2 robustness PR7): a small, focused wrapper around stdlib
``smtplib`` for sending transactional email from Sazon. Lives in
``app/integrations/`` because it talks to a third-party service
(SMTP server) and the call site wants the retry behavior the
``app/integrations/scrapers`` + ``app/services/backup_crypto`` already
use (S2 robustness PR6).

Why a separate module from :mod:`app.observability.email`?
- ``app.observability.email`` is the **Resend HTTP API** path (operator
  alerts). It is a no-op when ``RESEND_API_KEY`` is unset, designed
  for low-volume operator notifications.
- ``app.integrations.email_outbound`` is the **SMTP** path (transactional
  email, e.g. password resets / customer receipts). It is wired for
  any operator who provisions ``AIW_SMTP_HOST``/``AIW_SMTP_USER``/etc.
  (same env vars as :mod:`app.rms.notifications`).

What this module does:
1. Open an SMTP connection to ``smtp_host:smtp_port`` (STARTTLS by default).
2. Authenticate with ``smtp_user`` / ``smtp_password``.
3. Send the message via ``SMTP.send_message``.
4. Wrap the send in :func:`app.rms.retry.retry_transient` with
   ``attempts=3`` and a custom ``_email_is_transient`` classifier.

What it deliberately does NOT do:
- HTML templating — caller composes the body (keeps the surface small).
- Retry on auth errors (``smtplib.SMTPAuthenticationError``) — bad
  creds are operator-actionable, never transient.
- Async / aiohttp — sync mode per AGENTS.md rule 32.

Classifier notes:
- ``smtplib.SMTPConnectError`` / ``SMTPServerDisconnected`` / ``socket.timeout``
  / ``ConnectionRefusedError`` → transient (retry).
- ``smtplib.SMTPTimeoutError`` → transient.
- ``smtplib.SMTPResponseException`` with status >= 500 (rare — most
  smtplib exceptions don't carry a status; ``send_message`` typically
  raises ``SMTPServerDisconnected`` on 4xx) → transient.
- ``smtplib.SMTPAuthenticationError`` → terminal (bad creds, retrying
  with the same creds is pointless and locks the account further).
- Any other exception → default ``default_is_transient`` decides.
"""

from __future__ import annotations

import logging
import smtplib
import socket
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Callable

from app.retry import default_is_transient, retry_transient

logger = logging.getLogger(__name__)


class EmailConfigError(ValueError):
    """Raised when the email configuration is incomplete or invalid.

    Distinct from :class:`smtplib.SMTPException` so callers can tell
    "you didn't set AIW_SMTP_*" (config) from "the SMTP server
    rejected the message" (transport).
    """


@dataclass(frozen=True)
class EmailOutboundConfig:
    """SMTP connection settings for outbound email.

    All fields are required. The factory :meth:`from_env` reads
    ``AIW_SMTP_HOST`` / ``AIW_SMTP_PORT`` / ``AIW_SMTP_USER`` /
    ``AIW_SMTP_PASSWORD`` / ``AIW_SMTP_USE_TLS`` (same env vars as
    :mod:`app.rms.notifications`).
    """

    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    use_tls: bool = True

    @classmethod
    def from_env(cls) -> "EmailOutboundConfig":
        import os

        host = os.environ.get("AIW_SMTP_HOST", "")
        port_raw = os.environ.get("AIW_SMTP_PORT", "587")
        user = os.environ.get("AIW_SMTP_USER", "")
        password = os.environ.get("AIW_SMTP_PASS", "")
        use_tls_raw = os.environ.get("AIW_SMTP_USE_TLS", "1")

        try:
            port = int(port_raw)
        except ValueError as exc:
            raise EmailConfigError(
                f"AIW_SMTP_PORT must be an integer, got {port_raw!r}"
            ) from exc

        return cls(
            smtp_host=host,
            smtp_port=port,
            smtp_user=user,
            smtp_password=password,
            use_tls=use_tls_raw not in {"0", "false", "False", "no"},
        )

    def validate(self) -> None:
        """Raise :class:`EmailConfigError` if any required field is empty.

        Called by :func:`send_email_outbound` before opening the SMTP
        connection so a missing env var surfaces as a config error,
        not a transport-time auth failure.
        """
        missing: list[str] = []
        if not self.smtp_host:
            missing.append("smtp_host (AIW_SMTP_HOST)")
        if not self.smtp_user:
            missing.append("smtp_user (AIW_SMTP_USER)")
        if not self.smtp_password:
            missing.append("smtp_password (AIW_SMTP_PASS)")
        if missing:
            raise EmailConfigError(
                f"email_outbound config incomplete; missing: {', '.join(missing)}"
            )


# ─── Retry classifier for SMTP (S2 robustness PR7) ────────────────
#
# Mirrors the HTTP classifier added in PR6: transport-level / network
# errors are transient (retry), auth errors are terminal (operator
# has to fix creds). We piggyback on ``default_is_transient`` for
# the stdlib socket/timeout branches so the policy stays uniform
# across modules.

# Auth errors are NEVER transient (terminal). The remaining smtplib
# exception family is treated as transient — it almost always
# indicates a flaky connection or a 5xx SMTP response, both worth
# retrying.
_TERMINAL_EMAIL_EXCEPTIONS: tuple[type[BaseException], ...] = (
    smtplib.SMTPAuthenticationError,
    smtplib.SMTPNotSupportedError,  # server doesn't support STARTTLS — config issue
    EmailConfigError,
)


def _email_is_transient(exc: BaseException) -> bool:
    """Classify an SMTP error as transient (retry) or terminal (raise).

    Terminal:
    - ``smtplib.SMTPAuthenticationError`` — bad creds.
    - ``smtplib.SMTPNotSupportedError`` — server refused STARTTLS, won't
      change on retry.
    - :class:`EmailConfigError` — bad config surfaced late.

    Transient (everything else that ``default_is_transient`` says is
    transient, plus SMTP-specific transport errors):
    - ``smtplib.SMTPConnectError`` — couldn't reach the server.
    - ``smtplib.SMTPServerDisconnected`` — connection dropped mid-send.
    - ``smtplib.SMTPTimeoutError`` — socket read/write timeout.
    - ``smtplib.SMTPResponseException`` — server returned a non-2xx code.
    - Any socket/timeout from stdlib.
    """
    # Terminal checks first (don't retry on bad creds or misconfig).
    for terminal in _TERMINAL_EMAIL_EXCEPTIONS:
        if isinstance(exc, terminal):
            return False

    name = type(exc).__name__
    # SMTP-specific transport errors.
    if name in {
        "SMTPConnectError",
        "SMTPServerDisconnected",
        "SMTPTimeoutError",
        "SMTPResponseException",
        "SMTPHeloError",
        "SMTPSenderRefused",
        "SMTPRecipientRefused",
        "SMTPDataError",
    }:
        return True

    # Fall back to the default classifier for the rest (socket / timeout /
    # DNS). If it doesn't know, return False so we never accidentally
    # retry a logic bug.
    return default_is_transient(exc)


# ─── Public API ───────────────────────────────────────────────────


def _open_and_send(
    cfg: EmailOutboundConfig,
    msg: EmailMessage,
) -> None:
    """Open SMTP, authenticate, send ``msg``. One attempt — no retry.

    The retry wrapping lives in :func:`send_email_outbound` so the
    classifier can be swapped in tests via monkeypatch.
    """
    with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=10.0) as server:
        if cfg.use_tls:
            server.starttls()
        server.login(cfg.smtp_user, cfg.smtp_password)
        server.send_message(msg)


def send_email_outbound(
    to: str,
    subject: str,
    body: str,
    *,
    cfg: EmailOutboundConfig | None = None,
    from_addr: str | None = None,
    is_transient: Callable[[BaseException], bool] = _email_is_transient,
    sleep: Callable[[float], None] | None = None,
    attempts: int = 3,
    op_name: str = "email_outbound_send",
) -> bool:
    """Send a single outbound email via SMTP with retry.

    Returns True on successful send, False on permanent (terminal)
    failure (bad creds, config error, etc.). Raises on transient
    failure after ``attempts`` exhausted.

    Parameters
    ----------
    to:
        Recipient email address.
    subject:
        Email subject line.
    body:
        Plain-text body. HTML templating is the caller's job.
    cfg:
        SMTP configuration. If None, reads from env vars via
        :meth:`EmailOutboundConfig.from_env`.
    from_addr:
        Optional ``From:`` override; defaults to ``cfg.smtp_user``.
    is_transient:
        Classifier for retry decisions. Tests can pass a fake to
        control which errors are retried.
    sleep:
        Sleep function. Default = ``time.sleep`` from the helper.
    attempts:
        Maximum total calls (1 try + N-1 retries). Default 3.
    op_name:
        Label included in every log line for grep-ability.
    """
    if cfg is None:
        cfg = EmailOutboundConfig.from_env()
    cfg.validate()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr or cfg.smtp_user
    msg["To"] = to
    msg.set_content(body)

    try:
        retry_transient(
            lambda: _open_and_send(cfg, msg),
            attempts=attempts,
            is_transient=is_transient,
            sleep=sleep if sleep is not None else __import__("time").sleep,
            op_name=op_name,
        )
        logger.info("email_outbound sent to=%r subject=%r", to, subject)
        return True
    except BaseException as exc:
        # Terminal errors (bad creds, config) → return False so the
        # caller can decide what to do (no point retrying). Transient
        # errors after attempts are exhausted → re-raise so the caller
        # can page on-call / log to Sentry.
        is_terminal = not is_transient(exc)
        if is_terminal:
            logger.warning(
                "email_outbound terminal_error to=%r subject=%r error=%r",
                to,
                subject,
                exc,
            )
            return False
        raise


__all__ = [
    "EmailConfigError",
    "EmailOutboundConfig",
    "send_email_outbound",
    "_email_is_transient",
]
