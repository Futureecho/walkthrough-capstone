"""Email service using Resend API."""

from __future__ import annotations

import logging

from app.config import get_settings

logger = logging.getLogger(__name__)

_settings = get_settings()


def _send(to: str, subject: str, html: str) -> bool:
    """Send an email via Resend. Returns True on success."""
    if not _settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set — email to %s not sent: %s", to, subject)
        return False

    import resend
    resend.api_key = _settings.resend_api_key

    try:
        resend.Emails.send({
            "from": "Walkthru-X <noreply@verentyx.com>",
            "to": [to],
            "subject": subject,
            "html": html,
        })
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to)
        return False


def send_invite_email(email: str, token: str, company_name: str, invited_by: str) -> bool:
    """Send an invite email with accept link."""
    url = f"{_settings.app_url}/invite/{token}"
    html = f"""
    <h2>You've been invited to {company_name}</h2>
    <p>{invited_by} has invited you to join <strong>{company_name}</strong> on Walkthru-X.</p>
    <p><a href="{url}" style="display:inline-block;padding:12px 24px;background:#00d4ff;color:#0a0a0f;text-decoration:none;border-radius:6px;font-weight:600;">Accept Invite</a></p>
    <p>This invite expires in 7 days.</p>
    <p style="color:#888;font-size:12px;">If you didn't expect this, you can ignore this email.</p>
    """
    return _send(email, f"Join {company_name} on Walkthru-X", html)


def send_password_reset_email(email: str, token: str) -> bool:
    """Send a password reset email."""
    url = f"{_settings.app_url}/reset-password/{token}"
    html = f"""
    <h2>Reset your password</h2>
    <p>Click the button below to reset your Walkthru-X password.</p>
    <p><a href="{url}" style="display:inline-block;padding:12px 24px;background:#00d4ff;color:#0a0a0f;text-decoration:none;border-radius:6px;font-weight:600;">Reset Password</a></p>
    <p>This link expires in 1 hour. If you didn't request this, you can ignore this email.</p>
    """
    return _send(email, "Reset your Walkthru-X password", html)
