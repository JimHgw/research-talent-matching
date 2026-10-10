"""SMTP delivery. Never return or log verification codes or SMTP credentials."""

from email.message import EmailMessage
import smtplib
import ssl

from flask import current_app


class EmailDeliveryError(Exception):
    pass


def send_registration_code(email, code):
    send_email_code(email, code, "registration", current_app.config["REGISTER_CODE_TTL"])


def send_password_reset_code(email, code):
    send_email_code(email, code, "password reset", current_app.config["RESET_CODE_TTL"])


def send_email_code(email, code, purpose, ttl):
    config = current_app.config
    host, sender = config["SMTP_HOST"], config["SMTP_FROM"]
    security = config["SMTP_SECURITY"]
    if (not host or not sender or security not in {"starttls", "ssl", "plain"}
            or (config["SMTP_USERNAME"] and not config["SMTP_PASSWORD"])):
        raise EmailDeliveryError("Email delivery is not configured.")
    try:
        message = EmailMessage()
        message["From"] = sender
        message["To"] = email
        message["Subject"] = f"Banana account {purpose} code"
        minutes = ttl // 60
        message.set_content(
            f"Your Banana {purpose} code is: {code}\n\n"
            f"This code expires in {minutes} minutes and can be used once.\n"
            "If you did not request this email, you can ignore it.\n"
        )
        port = int(config["SMTP_PORT"])
        timeout = float(config["SMTP_TIMEOUT"])
        context = ssl.create_default_context()
        connection = (smtplib.SMTP_SSL(host, port, timeout=timeout, context=context)
                      if security == "ssl" else smtplib.SMTP(host, port, timeout=timeout))
        with connection as smtp:
            if security == "starttls":
                smtp.starttls(context=context)
            if config["SMTP_USERNAME"]:
                smtp.login(config["SMTP_USERNAME"], config["SMTP_PASSWORD"])
            if smtp.send_message(message):
                raise EmailDeliveryError("Registration email was refused.")
    except (OSError, smtplib.SMTPException, ValueError) as error:
        raise EmailDeliveryError("Registration email could not be delivered.") from error
