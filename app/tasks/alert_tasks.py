# app/tasks/alert_tasks.py
import logging
from datetime import date, timedelta
from sqlalchemy.orm import joinedload
from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.alert import Alert
from app.models.opportunity import Opportunity
from app.models.user import User
from app.services.alerts import send_alert

logger = logging.getLogger(__name__)

def get_db():
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise

@celery_app.task(name="app.tasks.alert_tasks.send_deadline_alerts")
def send_deadline_alerts():
    db = get_db()
    today = date.today()
    total_sent = 0
    total_failed = 0
    try:
        for days in [7, 1]:
            target_date = today + timedelta(days=days)
            alert_type = f"j{days}"
            pending_alerts = (
                db.query(Alert)
                .join(Alert.opportunity)
                .join(Alert.user)
                .filter(
                    Alert.is_sent == False,
                    Alert.type == alert_type,
                    Opportunity.deadline == target_date,
                    Opportunity.is_active == True,
                )
                .options(joinedload(Alert.user), joinedload(Alert.opportunity))
                .all()
            )
            logger.info(f"Found {len(pending_alerts)} pending {alert_type} alerts for {target_date}")
            for alert in pending_alerts:
                success = send_alert(db, alert)
                if success:
                    total_sent += 1
                else:
                    total_failed += 1
    except Exception as e:
        logger.error(f"send_deadline_alerts failed: {e}", exc_info=True)
    finally:
        db.close()
    logger.info(f"Alerts done — sent: {total_sent}, failed: {total_failed}")
    return {"sent": total_sent, "failed": total_failed}

@celery_app.task(name="app.tasks.alert_tasks.create_alerts_for_opportunity")
def create_alerts_for_opportunity(opportunity_id: str):
    db = get_db()
    try:
        opportunity = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
        if not opportunity or not opportunity.deadline:
            logger.warning(f"Opportunity {opportunity_id} not found or has no deadline")
            return
        query = db.query(User)
        if opportunity.required_level:
            query = query.filter(User.level.in_(opportunity.required_level))
        if opportunity.required_fields:
            query = query.filter(User.field.in_(opportunity.required_fields))
        eligible_users = query.all()
        logger.info(f"Creating alerts for {len(eligible_users)} users on opportunity {opportunity_id}")
        created = 0
        for user in eligible_users:
            for alert_type in ["j7", "j1"]:
                exists = db.query(Alert).filter(
                    Alert.user_id == user.id,
                    Alert.opportunity_id == opportunity.id,
                    Alert.type == alert_type,
                ).first()
                if not exists:
                    if user.phone:
                        db.add(Alert(user_id=user.id, opportunity_id=opportunity.id, type=alert_type, channel="sms"))
                        created += 1
                    db.add(Alert(user_id=user.id, opportunity_id=opportunity.id, type=alert_type, channel="email"))
                    created += 1
        db.commit()
        logger.info(f"Created {created} alert rows for opportunity {opportunity_id}")
        return {"created": created}
    except Exception as e:
        logger.error(f"create_alerts_for_opportunity failed: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()
