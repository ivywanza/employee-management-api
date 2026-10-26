import os
import smtplib
from email.message import EmailMessage
from html import escape
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USER)
SITE_URL = (os.getenv("SITE_URL") or "").rstrip("/")


def send_email(to: str, subject: str, body: str, html: str | None = None) -> None:
    missing = [
        name
        for name, value in [
            ("SMTP_HOST", SMTP_HOST),
            ("SMTP_USER", SMTP_USER),
            ("SMTP_PASSWORD", SMTP_PASSWORD),
        ]
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"Email is not configured. Missing: {', '.join(missing)}. "
            f"Looked in {ENV_PATH} (file exists: {ENV_PATH.exists()})"
        )

    message = EmailMessage()
    message["From"] = EMAIL_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    if html:
        message.add_alternative(html, subtype="html")

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(message)


def send_welcome_email(to: str, full_name: str, temp_password: str) -> None:
    if not SITE_URL:
        raise RuntimeError("SITE_URL is not set in .env")

    first = (full_name.split() or [""])[0]
    greeting = f"Hello {first}," if first else "Hello,"

    text = (
        f"{greeting}\n\n"
        "Welcome to Redant International! Your account on the staff portal is ready.\n\n"
        "YOUR SIGN-IN DETAILS\n"
        f"  Website:             {SITE_URL}\n"
        f"  Registered email:    {to}\n"
        f"  Temporary password:  {temp_password}\n\n"
        "WHAT TO DO NEXT\n"
        "  1. Open the website above and sign in with your email and the temporary password.\n"
        "  2. You will be asked to choose your own password straight away. After that you can\n"
        "     upload your onboarding documents, or skip and do it later.\n"
        "  3. If you ever forget your password: on the sign-in page click \"Forgot Password?\",\n"
        f"     enter {to}, type the 6-digit code we email you, and choose a new password.\n\n"
        "Please do not share the temporary password with anyone. It stops working as soon as\n"
        "you choose your own.\n\n"
        "Welcome aboard,\n"
        "Redant International\n"
    )

    site = escape(SITE_URL, quote=True)
    html = f"""\
<div style="font-family:Arial,Helvetica,sans-serif;background:#f1f3f7;padding:24px">
  <div style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:12px;overflow:hidden">
    <div style="background:#0f1f3d;padding:24px 28px">
      <p style="margin:0;color:#ff6b6b;font-size:12px;letter-spacing:2px;text-transform:uppercase">Redant International</p>
      <h1 style="margin:8px 0 0;color:#ffffff;font-size:24px">Welcome aboard{", " + escape(first) if first else ""}</h1>
    </div>
    <div style="padding:28px;color:#1f2a44;font-size:15px;line-height:1.6">
      <p style="margin-top:0">Your account on the staff portal is ready. Here are your sign-in details.</p>
      <table style="width:100%;border-collapse:collapse;background:#f6f8fc;border-radius:8px">
        <tr><td style="padding:10px 14px;color:#5b6472;width:42%">Website</td><td style="padding:10px 14px"><a href="{site}" style="color:#0f1f3d">{escape(SITE_URL)}</a></td></tr>
        <tr><td style="padding:10px 14px;color:#5b6472">Registered email</td><td style="padding:10px 14px">{escape(to)}</td></tr>
        <tr><td style="padding:10px 14px;color:#5b6472">Temporary password</td><td style="padding:10px 14px"><code style="font-size:16px;font-weight:bold;letter-spacing:1px">{escape(temp_password)}</code></td></tr>
      </table>
      <p style="margin:24px 0"><a href="{site}" style="background:#d32f2f;color:#ffffff;text-decoration:none;padding:12px 22px;border-radius:8px;font-weight:bold;display:inline-block">Open the portal</a></p>
      <p style="margin-bottom:6px"><strong>What to do next</strong></p>
      <ol style="margin-top:0;padding-left:20px">
        <li>Open the portal and sign in with your email and the temporary password.</li>
        <li>You will be asked to choose your own password straight away. After that, upload your onboarding documents, or skip and do it later.</li>
        <li>Forgot your password later? On the sign-in page click <strong>Forgot Password?</strong>, enter <strong>{escape(to)}</strong>, type the 6-digit code we email you, and choose a new password.</li>
      </ol>
      <p style="color:#5b6472;font-size:13px">Please do not share the temporary password with anyone. It stops working as soon as you choose your own.</p>
    </div>
  </div>
</div>
"""
    send_email(to, "Welcome to Redant International: your sign-in details", text, html)