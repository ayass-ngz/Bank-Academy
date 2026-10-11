"""Envoi d'e-mails.

Avec MAIL_SERVER configuré, les messages partent en SMTP. Sinon (développement, démo),
ils sont enregistrés au format .eml dans instance/outbox et consultables sur /dev/emails.
"""
import os
import smtplib
from datetime import datetime
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser

from flask import current_app

sent = []  # derniers messages envoyés (utile pour les tests)


def outbox_dir():
    path = os.path.join(current_app.instance_path, "outbox")
    os.makedirs(path, exist_ok=True)
    return path


def send_mail(to, subject, body):
    config = current_app.config
    message = EmailMessage()
    message["From"] = config["MAIL_DEFAULT_SENDER"]
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    sent.append(message)
    del sent[:-50]

    if config.get("MAIL_SUPPRESS_SEND"):
        return "suppressed"
    if config.get("MAIL_SERVER"):
        with smtplib.SMTP(config["MAIL_SERVER"], config["MAIL_PORT"], timeout=15) as smtp:
            if config.get("MAIL_USE_TLS"):
                smtp.starttls()
            if config.get("MAIL_USERNAME"):
                smtp.login(config["MAIL_USERNAME"], config["MAIL_PASSWORD"])
            smtp.send_message(message)
        return "smtp"

    filename = f"{datetime.now():%Y%m%d-%H%M%S-%f}.eml"
    with open(os.path.join(outbox_dir(), filename), "wb") as handle:
        handle.write(bytes(message))
    current_app.logger.info("E-mail (mode démo) pour %s enregistré dans instance/outbox/%s", to, filename)
    return "outbox"


def read_outbox(limit=30):
    """Messages enregistrés en mode démo, du plus récent au plus ancien."""
    messages = []
    for name in sorted(os.listdir(outbox_dir()), reverse=True)[:limit]:
        with open(os.path.join(outbox_dir(), name), "rb") as handle:
            msg = BytesParser(policy=policy.default).parse(handle)
        messages.append({"name": name, "to": msg["To"], "subject": msg["Subject"],
                         "body": msg.get_body(preferencelist=("plain",)).get_content()})
    return messages
