"""
Resend email service for SUNO Clips.

Uses the Resend HTTP API directly (httpx) — no extra SDK dependency.
Set RESEND_API_KEY and EMAIL_FROM in your .env to enable.

If RESEND_API_KEY is not set, all sends are no-ops (logged, not raised).
"""

import logging
import os
from datetime import datetime
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "SUNO Clips <no-reply@sunoclips.io>")
RESEND_API_URL = "https://api.resend.com/emails"


def _send(to: str, subject: str, html: str) -> bool:
    """Send a single email via Resend. Returns True on success."""
    if not RESEND_API_KEY:
        logger.warning("Email skipped (RESEND_API_KEY not set): subject=%s to=%s", subject, to)
        return False

    try:
        resp = httpx.post(
            RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"from": EMAIL_FROM, "to": [to], "subject": subject, "html": html},
            timeout=15.0,
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            logger.info("Email sent: id=%s to=%s subject=%s", data.get("id"), to, subject)
            return True
        logger.error(
            "Resend API error: HTTP %d to=%s subject=%s body=%s",
            resp.status_code, to, subject, resp.text[:500],
        )
        return False
    except Exception as exc:
        logger.error("Email send failed: to=%s subject=%s error=%s", to, subject, exc)
        return False


# ---------------------------------------------------------------------------
# Invoice email
# ---------------------------------------------------------------------------

def send_invoice_email(
    client_email: str,
    client_name: str,
    month: str,
    amount: float,
    clips_delivered: int,
    total_views: int,
    view_guarantee_met: bool,
    performance_bonus: float = 0.0,
    portal_url: Optional[str] = None,
) -> bool:
    """Email a generated invoice to the client."""
    guarantee_badge = (
        '<span style="color:#00ff87;font-weight:bold;">✓ View guarantee met</span>'
        if view_guarantee_met
        else '<span style="color:#ff6b6b;">✗ View guarantee missed</span>'
    )
    portal_link = (
        f'<p><a href="{portal_url}" style="color:#00ff87;">View your portal →</a></p>'
        if portal_url else ""
    )

    subject = f"Invoice for {month} — ${amount:,.0f}"
    html = f"""
<!DOCTYPE html>
<html>
<body style="background:#0a0a0a;color:#e8e8e8;font-family:sans-serif;padding:32px;">
  <div style="max-width:560px;margin:0 auto;background:#16161a;border-radius:12px;padding:32px;">
    <h1 style="color:#00ff87;margin:0 0 8px;">SUNO Clips</h1>
    <h2 style="color:#e8e8e8;margin:0 0 24px;font-size:18px;">Monthly Invoice — {month}</h2>

    <p>Hi {client_name},</p>
    <p>Here's your invoice summary for <strong>{month}</strong>.</p>

    <table style="width:100%;border-collapse:collapse;margin:24px 0;">
      <tr><td style="padding:10px 0;border-bottom:1px solid #2a2a2f;color:#888;">Base retainer</td>
          <td style="padding:10px 0;border-bottom:1px solid #2a2a2f;text-align:right;">${amount - performance_bonus:,.0f}</td></tr>
      {"<tr><td style='padding:10px 0;border-bottom:1px solid #2a2a2f;color:#888;'>Performance bonus</td><td style='padding:10px 0;border-bottom:1px solid #2a2a2f;text-align:right;color:#00ff87;'>+${performance_bonus:,.0f}</td></tr>" if performance_bonus else ""}
      <tr><td style="padding:10px 0;font-weight:bold;">Total</td>
          <td style="padding:10px 0;text-align:right;font-weight:bold;font-size:20px;color:#00ff87;">${amount:,.0f}</td></tr>
    </table>

    <div style="background:#0a0a0a;border-radius:8px;padding:16px;margin:24px 0;">
      <p style="margin:0 0 8px;"><strong>📊 Performance</strong></p>
      <p style="margin:4px 0;color:#888;">Clips delivered: <strong style="color:#e8e8e8;">{clips_delivered}</strong></p>
      <p style="margin:4px 0;color:#888;">Total views: <strong style="color:#e8e8e8;">{total_views:,}</strong></p>
      <p style="margin:4px 0;">{guarantee_badge}</p>
    </div>

    {portal_link}

    <p style="color:#555;font-size:12px;margin-top:32px;">
      SUNO Clips &mdash; The operating system for clip agencies
    </p>
  </div>
</body>
</html>
"""
    return _send(client_email, subject, html)


# ---------------------------------------------------------------------------
# Portal invite email (sent to the client, not the operator)
# ---------------------------------------------------------------------------

def send_portal_invite_email(
    client_email: str,
    client_name: str,
    invite_url: str,
    expires_days: int = 7,
    operator_name: Optional[str] = None,
) -> bool:
    """Send a magic-link portal invite to a client."""
    from_line = f"your team at {operator_name}" if operator_name else "your clip agency"

    subject = f"You're invited to your SUNO Clips portal"
    html = f"""
<!DOCTYPE html>
<html>
<body style="background:#0a0a0a;color:#e8e8e8;font-family:sans-serif;padding:32px;">
  <div style="max-width:560px;margin:0 auto;background:#16161a;border-radius:12px;padding:32px;">
    <h1 style="color:#00ff87;margin:0 0 24px;">SUNO Clips</h1>

    <p>Hi {client_name},</p>
    <p>{from_line.capitalize()} has set up your personal dashboard where you can track your clips,
       views, and monthly invoices in real time.</p>

    <div style="text-align:center;margin:32px 0;">
      <a href="{invite_url}"
         style="background:#00ff87;color:#0a0a0a;font-weight:700;padding:14px 32px;
                border-radius:8px;text-decoration:none;font-size:16px;display:inline-block;">
        Access Your Portal →
      </a>
    </div>

    <p style="color:#555;font-size:13px;">This link is valid for {expires_days} days and can only be used once.
       If you didn't expect this, you can ignore this email.</p>

    <p style="color:#555;font-size:12px;margin-top:32px;">
      SUNO Clips &mdash; The operating system for clip agencies
    </p>
  </div>
</body>
</html>
"""
    return _send(client_email, subject, html)


# ---------------------------------------------------------------------------
# Editor welcome email (sent when operator creates or resets editor password)
# ---------------------------------------------------------------------------

def send_editor_welcome_email(
    editor_email: str,
    editor_name: str,
    password: str,
    portal_url: Optional[str] = None,
) -> bool:
    """Send editor portal login credentials."""
    login_url = portal_url or f"{os.getenv('BASE_URL', 'http://localhost:8000')}/editor/login"
    subject = "Your SUNO Clips editor portal access"
    html = f"""
<!DOCTYPE html>
<html>
<body style="background:#0a0a0a;color:#e8e8e8;font-family:sans-serif;padding:32px;">
  <div style="max-width:560px;margin:0 auto;background:#16161a;border-radius:12px;padding:32px;">
    <h1 style="color:#00ff87;margin:0 0 24px;">SUNO Clips</h1>

    <p>Hi {editor_name},</p>
    <p>Your editor portal has been set up. Use the credentials below to log in and view your assigned clips.</p>

    <div style="background:#0a0a0a;border-radius:8px;padding:20px;margin:24px 0;">
      <p style="margin:0 0 8px;color:#888;">Login URL</p>
      <p style="margin:0 0 16px;"><a href="{login_url}" style="color:#00ff87;">{login_url}</a></p>
      <p style="margin:0 0 8px;color:#888;">Email</p>
      <p style="margin:0 0 16px;font-family:monospace;">{editor_email}</p>
      <p style="margin:0 0 8px;color:#888;">Password</p>
      <p style="margin:0;font-family:monospace;font-size:16px;color:#e8e8e8;">{password}</p>
    </div>

    <p style="color:#555;font-size:13px;">Change your password by contacting your agency manager.</p>
    <p style="color:#555;font-size:12px;margin-top:32px;">SUNO Clips &mdash; The operating system for clip agencies</p>
  </div>
</body>
</html>
"""
    return _send(editor_email, subject, html)


# ---------------------------------------------------------------------------
# Clip approved email
# ---------------------------------------------------------------------------

def send_clip_approved_email(
    operator_email: str,
    client_name: str,
    clip_title: str,
    clip_id: str,
    portal_url: Optional[str] = None,
) -> bool:
    """Notify the operator when a clip moves to APPROVED status."""
    review_link = (
        f'<p><a href="{portal_url}" style="color:#00ff87;">Review and post →</a></p>'
        if portal_url else ""
    )

    subject = f"Clip approved: {clip_title or clip_id[:8]}"
    html = f"""
<!DOCTYPE html>
<html>
<body style="background:#0a0a0a;color:#e8e8e8;font-family:sans-serif;padding:32px;">
  <div style="max-width:560px;margin:0 auto;background:#16161a;border-radius:12px;padding:32px;">
    <h1 style="color:#00ff87;margin:0 0 24px;">✓ Clip Approved</h1>

    <p>A clip for <strong>{client_name}</strong> has been approved and is ready to post.</p>

    <div style="background:#0a0a0a;border-radius:8px;padding:16px;margin:24px 0;">
      <p style="margin:4px 0;color:#888;">Client: <strong style="color:#e8e8e8;">{client_name}</strong></p>
      <p style="margin:4px 0;color:#888;">Clip: <strong style="color:#e8e8e8;">{clip_title or clip_id[:8]}</strong></p>
      <p style="margin:4px 0;color:#888;">Status: <strong style="color:#00ff87;">APPROVED → Ready to post</strong></p>
    </div>

    {review_link}

    <p style="color:#555;font-size:12px;margin-top:32px;">SUNO Clips</p>
  </div>
</body>
</html>
"""
    return _send(operator_email, subject, html)


# ---------------------------------------------------------------------------
# Weekly performance report email
# ---------------------------------------------------------------------------

def send_weekly_report_email(
    operator_email: str,
    client_name: str,
    period_start: datetime,
    period_end: datetime,
    total_clips: int,
    total_views: int,
    total_likes: int,
    top_clips: Optional[list] = None,
    portal_url: Optional[str] = None,
) -> bool:
    """Send a weekly performance summary to the operator."""
    start_str = period_start.strftime("%b %d")
    end_str = period_end.strftime("%b %d, %Y")

    top_clips_html = ""
    if top_clips:
        rows = "".join(
            f"<tr><td style='padding:8px 0;border-bottom:1px solid #2a2a2f;'>{c.get('title', 'Untitled')}</td>"
            f"<td style='padding:8px 0;border-bottom:1px solid #2a2a2f;text-align:right;color:#00ff87;'>{c.get('views', 0):,}</td></tr>"
            for c in top_clips[:5]
        )
        top_clips_html = f"""
        <h3 style="color:#888;font-size:14px;margin:24px 0 8px;">TOP CLIPS</h3>
        <table style="width:100%;border-collapse:collapse;">
          <tr><th style="text-align:left;color:#555;font-size:12px;padding-bottom:8px;">Title</th>
              <th style="text-align:right;color:#555;font-size:12px;padding-bottom:8px;">Views</th></tr>
          {rows}
        </table>
        """

    portal_link = (
        f'<p><a href="{portal_url}" style="color:#00ff87;">View full report →</a></p>'
        if portal_url else ""
    )

    subject = f"Weekly report: {client_name} ({start_str}–{end_str})"
    html = f"""
<!DOCTYPE html>
<html>
<body style="background:#0a0a0a;color:#e8e8e8;font-family:sans-serif;padding:32px;">
  <div style="max-width:560px;margin:0 auto;background:#16161a;border-radius:12px;padding:32px;">
    <h1 style="color:#00ff87;margin:0 0 8px;">SUNO Clips</h1>
    <h2 style="color:#e8e8e8;margin:0 0 4px;font-size:18px;">Weekly Report — {client_name}</h2>
    <p style="color:#555;margin:0 0 24px;">{start_str} – {end_str}</p>

    <div style="display:flex;gap:16px;margin:24px 0;">
      <div style="flex:1;background:#0a0a0a;border-radius:8px;padding:16px;text-align:center;">
        <div style="font-size:28px;font-weight:bold;color:#00ff87;">{total_clips}</div>
        <div style="color:#555;font-size:12px;margin-top:4px;">CLIPS</div>
      </div>
      <div style="flex:1;background:#0a0a0a;border-radius:8px;padding:16px;text-align:center;">
        <div style="font-size:28px;font-weight:bold;color:#00ff87;">{total_views:,}</div>
        <div style="color:#555;font-size:12px;margin-top:4px;">VIEWS</div>
      </div>
      <div style="flex:1;background:#0a0a0a;border-radius:8px;padding:16px;text-align:center;">
        <div style="font-size:28px;font-weight:bold;color:#00ff87;">{total_likes:,}</div>
        <div style="color:#555;font-size:12px;margin-top:4px;">LIKES</div>
      </div>
    </div>

    {top_clips_html}
    {portal_link}

    <p style="color:#555;font-size:12px;margin-top:32px;">SUNO Clips &mdash; The operating system for clip agencies</p>
  </div>
</body>
</html>
"""
    return _send(operator_email, subject, html)
