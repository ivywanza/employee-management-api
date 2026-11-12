
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

ORGANISATIONS = {
    "red_ant": {
        "name": "Red Ant International",
        "email_name": "Red Ant International",
        "colour": "#d32f2f",
        "header": "#0f1f3d",
    },
    "bella_organics": {
        "name": "Bella Organics",
        "email_name": "Bella Organics",
        "colour": "#2e7d32",
        "header": "#174d2b",
    },
    "juakali": {
        "name": "Juakali",
        "email_name": "Juakali",
        "colour": "#b45309",
        "header": "#292524",
    },
}


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


def send_welcome_email(
    to: str,
    full_name: str,
    temp_password: str,
    organisation: str = "red_ant",
) -> None:
    if not SITE_URL:
        raise RuntimeError("SITE_URL is not set in .env")

    brand = ORGANISATIONS.get(organisation, ORGANISATIONS["red_ant"])

    organisation_name = brand["name"]
    first = (full_name.split() or [""])[0]
    greeting = f"Hello {first}," if first else "Hello,"

    colour = brand["colour"]
    header_colour = brand["header"]

    text = (
        f"{greeting}\n\n"
        f"Welcome to {organisation_name}! Your account on the staff portal is ready.\n\n"
        "YOUR SIGN-IN DETAILS\n"
        f"  Website:             {SITE_URL}\n"
        f"  Registered email:    {to}\n"
        f"  Temporary password:  {temp_password}\n\n"
        "WHAT TO DO NEXT\n"
        "  1. Open the website above and sign in with your email and temporary password.\n"
        "  2. Choose your own password when prompted.\n"
        "  3. Upload your onboarding documents, or skip and complete them later.\n"
        "  4. If you forget your password, click Forgot Password on the sign-in page.\n\n"
        "Please do not share your temporary password with anyone.\n\n"
        f"Welcome aboard,\n{organisation_name}\n"
    )

    site = escape(SITE_URL, quote=True)
    safe_name = escape(first)
    safe_email = escape(to)
    safe_password = escape(temp_password)
    safe_organisation = escape(organisation_name)

    html = f"""\
<div style="font-family:Arial,Helvetica,sans-serif;background:#f1f3f7;padding:24px">
  <div style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:12px;overflow:hidden">
    <div style="background:{header_colour};padding:24px 28px">
      <p style="margin:0;color:#ffffff;font-size:12px;letter-spacing:2px;text-transform:uppercase">
        {safe_organisation}
      </p>
      <h1 style="margin:8px 0 0;color:#ffffff;font-size:24px">
        Welcome aboard{", " + safe_name if first else ""}
      </h1>
    </div>
    <div style="padding:28px;color:#1f2a44;font-size:15px;line-height:1.6">
      <p style="margin-top:0">
        Your account on the staff portal is ready. Here are your sign-in details.
      </p>
      <table style="width:100%;border-collapse:collapse;background:#f6f8fc">
        <tr>
          <td style="padding:10px 14px;color:#5b6472;width:42%">Website</td>
          <td style="padding:10px 14px"><a href="{site}">{site}</a></td>
        </tr>
        <tr>
          <td style="padding:10px 14px;color:#5b6472">Registered email</td>
          <td style="padding:10px 14px">{safe_email}</td>
        </tr>
        <tr>
          <td style="padding:10px 14px;color:#5b6472">Temporary password</td>
          <td style="padding:10px 14px"><strong>{safe_password}</strong></td>
        </tr>
      </table>
      <p style="margin:24px 0">
        <a href="{site}" style="background:{colour};color:#ffffff;text-decoration:none;padding:12px 22px;border-radius:8px;font-weight:bold;display:inline-block">
          Open the portal
        </a>
      </p>
      <p><strong>What to do next</strong></p>
      <ol style="padding-left:20px">
        <li>Sign in using your registered email and temporary password.</li>
        <li>Choose your own password when prompted.</li>
        <li>Upload your onboarding documents, or skip and complete them later.</li>
        <li>If you forget your password, use Forgot Password on the sign-in page.</li>
      </ol>
      <p style="color:#5b6472;font-size:13px">
        Please do not share your temporary password with anyone.
      </p>
      <p>Welcome aboard,<br><strong>{safe_organisation}</strong></p>
    </div>
  </div>
</div>
"""

    send_email(
        to,
        f"Welcome to {organisation_name}: your sign-in details",
        text,
        html,
    )
