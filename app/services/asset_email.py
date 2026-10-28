
import os
import smtplib
from email.message import EmailMessage
from urllib.parse import urlencode


def send_assignment_email(
    recipient_email: str,
    employee_name: str,
    asset_name: str,
    asset_tag: str,
    token: str,
) -> None:
    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.environ["SMTP_USER"]
    smtp_password = os.environ["SMTP_PASSWORD"]
    sender_email = os.environ["SMTP_FROM_EMAIL"]
    frontend_url = os.environ["FRONTEND_URL"].rstrip("/")

    query = urlencode({"token": token})
    accept_url = f"{frontend_url}/assets/accept-assignment?{query}"

    message = EmailMessage()
    message["Subject"] = f"Asset assignment awaiting your acceptance: {asset_name}"
    message["From"] = sender_email
    message["To"] = recipient_email

    message.set_content(
        f"""Hello {employee_name},

An asset has been assigned to you and is awaiting your acceptance.

Asset: {asset_name}
Asset tag: {asset_tag}

Please sign in to your employee portal and review the assignment using this link:

{accept_url}

This link expires in 48 hours and can only be used by the intended employee.

If you were not expecting this assignment, contact your administrator.

Regards,
HR Operations
"""
    )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(message)
