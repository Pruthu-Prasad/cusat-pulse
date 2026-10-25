"""Sign-in codes by SMTP. Without SMTP credentials in .env the code is printed to the console instead."""
import smtplib
import ssl
from email.message import EmailMessage

from core.config import SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER
from core.errors import AppError


def smtp_configured():
    # The "your-..." placeholders from .env.example count as unset.
    return all(v and not v.startswith("your-") for v in (SMTP_HOST, SMTP_USER, SMTP_PASSWORD))


def send_otp(email, code):
    if not smtp_configured():
        print(f"\n==== OTP for {email}: {code} ====\n", flush=True)
        return
    msg = EmailMessage()
    msg["Subject"] = f"{code} is your CUSAT Pulse sign-in code"
    msg["From"] = SMTP_FROM or SMTP_USER
    msg["To"] = email
    msg.set_content(
        f"Your CUSAT Pulse sign-in code is {code}\n\n"
        "It expires in 10 minutes. If you did not ask for it, you can ignore this email."
    )
    try:
        context = ssl.create_default_context()
        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=15) as s:
                s.login(SMTP_USER, SMTP_PASSWORD)
                s.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
                s.starttls(context=context)
                s.login(SMTP_USER, SMTP_PASSWORD)
                s.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        print(f"[smtp] could not send OTP to {email}: {exc!r}", flush=True)
        raise AppError(502, "We could not send the code email. Please try again in a minute.")
