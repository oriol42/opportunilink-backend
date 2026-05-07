# app/services/alerts.py
# Handles actual sending of SMS (AfricasTalking) and email (Resend)

import logging
import africastalking
import resend
from datetime import date, timedelta
from sqlalchemy.orm import Session
from app.config import settings
from app.models.alert import Alert
from app.models.opportunity import Opportunity
from app.models.user import User

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# AFRICAS TALKING — SMS
# ---------------------------------------------------------------------------

def _init_africastalking():
    """Initialize AfricasTalking SDK (called once before sending)."""
    africastalking.initialize(
        username=settings.africas_talking_user or "sandbox",
        api_key=settings.africas_talking_key or "dummy",
    )
    return africastalking.SMS()


def send_sms(phone: str, message: str) -> bool:
    """
    Send a single SMS via AfricasTalking.
    Returns True if sent successfully, False otherwise.
    Phone must include country code: +237XXXXXXXXX
    """
    if not settings.africas_talking_key:
        logger.warning("AfricasTalking key not configured — SMS skipped")
        return False

    try:
        sms = _init_africastalking()
        response = sms.send(message, [phone])
        logger.info(f"SMS sent to {phone}: {response}")
        return True
    except Exception as e:
        logger.error(f"SMS failed for {phone}: {e}")
        return False


# ---------------------------------------------------------------------------
# RESEND — EMAIL
# ---------------------------------------------------------------------------

def send_email(to: str, subject: str, html: str) -> bool:
    """
    Send a single email via Resend.
    Returns True if sent successfully, False otherwise.
    """
    if not settings.resend_api_key:
        logger.warning("Resend API key not configured — email skipped")
        return False

    try:
        resend.api_key = settings.resend_api_key
        params = {
            "from": "OpportuLink <alerts@opportunilink.cm>",
            "to": [to],
            "subject": subject,
            "html": html,
        }
        response = resend.Emails.send(params)
        logger.info(f"Email sent to {to}: {response}")
        return True
    except Exception as e:
        logger.error(f"Email failed for {to}: {e}")
        return False


# ---------------------------------------------------------------------------
# ALERT BUILDERS — build the message content per alert type
# ---------------------------------------------------------------------------

def build_deadline_message(user: User, opportunity: Opportunity, days_left: int) -> dict:
    """
    Build SMS + email content for a deadline alert (J-7 or J-1).
    Returns {"sms": str, "subject": str, "html": str}
    """
    urgency = "URGENT — " if days_left == 1 else ""
    deadline_str = opportunity.deadline.strftime("%d/%m/%Y")

    sms = (
        f"{urgency}OpportuLink: La deadline pour '{opportunity.title}' "
        f"est dans {days_left} jour(s) ({deadline_str}). "
        f"Candidate maintenant : opportunilink.cm"
    )

    subject = f"{urgency}Deadline dans {days_left} jour(s) — {opportunity.title}"

    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto;">
        <h2 style="color: #10b981;">⏰ {urgency}Deadline approche !</h2>
        <p>Bonjour <strong>{user.full_name}</strong>,</p>
        <p>
            La date limite de candidature pour l'opportunité
            <strong>"{opportunity.title}"</strong>
            est dans <strong>{days_left} jour(s)</strong> ({deadline_str}).
        </p>
        <a href="https://opportunilink.cm/opportunity/{opportunity.id}"
           style="background:#10b981;color:white;padding:12px 24px;
                  border-radius:6px;text-decoration:none;display:inline-block;margin-top:16px;">
            Voir l'opportunité →
        </a>
        <p style="color:#6b7280;font-size:12px;margin-top:32px;">
            OpportuLink — La plateforme des étudiants camerounais
        </p>
    </div>
    """

    return {"sms": sms, "subject": subject, "html": html}


# ---------------------------------------------------------------------------
# CORE ALERT SENDER — used by Celery tasks
# ---------------------------------------------------------------------------

def send_alert(db: Session, alert: Alert) -> bool:
    """
    Send one alert (SMS or email) and mark it as sent in the DB.
    Called by Celery tasks — receives an Alert ORM object.
    """
    user = alert.user
    opportunity = alert.opportunity
    days_left = (opportunity.deadline - date.today()).days

    # Build message content
    content = build_deadline_message(user, opportunity, days_left)

    # Dispatch based on channel
    success = False
    if alert.channel == "sms" and user.phone:
        success = send_sms(user.phone, content["sms"])
    elif alert.channel == "email" and user.email:
        success = send_email(user.email, content["subject"], content["html"])
    else:
        logger.warning(f"Alert {alert.id}: unknown channel '{alert.channel}' or missing contact")
        return False

    # Update DB
    if success:
        from datetime import datetime
        alert.is_sent = True
        alert.sent_at = datetime.utcnow()
        db.commit()
        logger.info(f"Alert {alert.id} marked as sent")

    return success
