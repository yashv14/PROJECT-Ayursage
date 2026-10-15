"""Reception-only administrative data; no clinical serializer or grant bypass."""
from datetime import datetime, timedelta, timezone
from flask import Blueprint, g, request
from sqlalchemy import select, update, or_
from werkzeug.exceptions import BadRequest, Conflict, NotFound, ServiceUnavailable
from backend.app.auth.security import roles_required, validate_email
from backend.app.auth.routes import find_accounts
from backend.app.auth.grants import utc_now
from backend.app.database import db
from backend.app.models import Patient, User, Role, Appointment, AppointmentEvent, AppointmentLock
from .assessment_validation import json_object

reception=Blueprint("reception",__name__,url_prefix="/reception")
TRANSITIONS={"scheduled":{"checked_in","cancelled","no_show"},"checked_in":{"completed"}}
ACTIVE=("scheduled","checked_in")

@reception.after_request
def private(response):
    response.headers["Cache-Control"]="no-store"
    return response

def identifier(value):
    if type(value) is not int or not 1 <= value <= 2147483647: raise BadRequest()
    return value

def timestamp(value):
    if not isinstance(value,str) or len(value)>64: raise BadRequest()
    try:
        result=datetime.fromisoformat(value.replace('Z','+00:00'))
        if result.tzinfo is None or result.utcoffset() is None or result.microsecond: raise ValueError()
        return result.astimezone(timezone.utc).replace(tzinfo=None)
    except (ValueError,OverflowError): raise BadRequest() from None

def interval(payload):
    start=timestamp(payload.get("starts_at"))
    try: end=timestamp(payload["ends_at"]) if "ends_at" in payload else start+timedelta(minutes=30)
    except OverflowError: raise BadRequest() from None
    if end<=start: raise BadRequest()
    return start,end

def lock_bookings():
    # Every booking mutation obtains this shared write lock BEFORE overlap/state
    # reads. SQLite UPDATE serializes writers; InnoDB holds the row lock to commit.
    result=db.session.execute(update(AppointmentLock).where(AppointmentLock.id==1).values(id=1))
    if result.rowcount!=1: raise ServiceUnavailable()

def valid_participants(patient_id,doctor_id):
    patient=db.session.scalar(select(Patient).join(User,User.id==Patient.owner_user_id).join(Role).where(
        Patient.id==patient_id,Role.code=="patient"))
    doctor=db.session.scalar(select(User.id).join(Role).where(User.id==doctor_id,Role.code=="doctor",User.password_hash.is_not(None)))
    if patient is None or doctor is None: raise BadRequest()

def no_overlap(patient_id,doctor_id,start,end,exclude=None):
    query=select(Appointment.id).where(Appointment.status.in_(ACTIVE),Appointment.starts_at<end,
        Appointment.ends_at>start,or_(Appointment.patient_id==patient_id,Appointment.doctor_user_id==doctor_id))
    if exclude is not None: query=query.where(Appointment.id!=exclude)
    if db.session.scalar(query.limit(1).with_for_update()) is not None: raise Conflict()

def data(row):
    return {"id":row.id,"patient_id":row.patient_id,"doctor_user_id":row.doctor_user_id,
        "starts_at":row.starts_at.isoformat()+"Z","ends_at":row.ends_at.isoformat()+"Z","status":row.status,
        "created_by_user_id":row.created_by_user_id,"updated_by_user_id":row.updated_by_user_id,
        "created_at":row.created_at.isoformat()+"Z","updated_at":row.updated_at.isoformat()+"Z"}

def event(row,action,old=None):
    row.updated_at=utc_now(); row.updated_by_user_id=g.current_user.id
    db.session.add(AppointmentEvent(appointment_id=row.id,actor_user_id=g.current_user.id,action=action,
        from_status=old,to_status=row.status,starts_at=row.starts_at,ends_at=row.ends_at,occurred_at=row.updated_at))

@reception.get("/patients")
@roles_required("receptionist")
def lookup():
    if set(request.args)!={"email"} or len(request.args.getlist("email"))!=1: raise BadRequest()
    accounts=find_accounts(validate_email(request.args["email"]))
    if len(accounts)!=1 or accounts[0].role.code!="patient": raise NotFound()
    user=accounts[0]
    patient=db.session.scalar(select(Patient).where(Patient.owner_user_id==user.id))
    if patient is None: raise NotFound()
    return {"patient":{"id":patient.id,"email":user.email,
        "administrative_status":"registered" if user.password_hash else "credential_setup_required"}}

@reception.get("/doctors")
@roles_required("receptionist")
def doctors():
    after=page_after()
    rows=db.session.execute(select(User.id,User.email).join(Role).where(Role.code=="doctor",User.password_hash.is_not(None),User.id>after).order_by(User.id).limit(51)).all()
    return {"doctors":[{"id":row.id,"email":row.email} for row in rows[:50]],"next_after_id":rows[49].id if len(rows)>50 else None}

def page_after():
    if set(request.args)-{"after_id"} or len(request.args.getlist("after_id"))>1: raise BadRequest()
    try: after=int(request.args.get("after_id","0"))
    except ValueError: raise BadRequest() from None
    if not 0<=after<=2147483647: raise BadRequest()
    return after

@reception.get("/appointments")
@roles_required("receptionist")
def appointments():
    after=page_after()
    rows=db.session.scalars(select(Appointment).where(Appointment.id>after).order_by(Appointment.id).limit(51)).all()
    return {"appointments":[data(row) for row in rows[:50]],"next_after_id":rows[49].id if len(rows)>50 else None}

@reception.post("/appointments")
@roles_required("receptionist")
def create():
    payload=json_object()
    if set(payload)-{"patient_id","doctor_user_id","starts_at","ends_at"} or not {"patient_id","doctor_user_id","starts_at"}<=set(payload): raise BadRequest()
    patient_id=identifier(payload["patient_id"]);doctor_id=identifier(payload["doctor_user_id"])
    start,end=interval(payload)
    lock_bookings();valid_participants(patient_id,doctor_id);no_overlap(patient_id,doctor_id,start,end)
    now=utc_now()
    row=Appointment(patient_id=patient_id,doctor_user_id=doctor_id,starts_at=start,ends_at=end,status="scheduled",
        created_by_user_id=g.current_user.id,updated_by_user_id=g.current_user.id,created_at=now,updated_at=now)
    db.session.add(row);db.session.flush();event(row,"created");db.session.commit()
    return {"appointment":data(row)},201

def locked_appointment(appointment_id):
    identifier(appointment_id);lock_bookings()
    row=db.session.scalar(select(Appointment).where(Appointment.id==appointment_id).with_for_update().execution_options(populate_existing=True))
    if row is None: raise NotFound()
    return row

@reception.post("/appointments/<int:appointment_id>/reschedule")
@roles_required("receptionist")
def reschedule(appointment_id):
    payload=json_object()
    if set(payload)-{"starts_at","ends_at"} or "starts_at" not in payload: raise BadRequest()
    start,end=interval(payload);row=locked_appointment(appointment_id)
    if row.status!="scheduled": raise Conflict()
    valid_participants(row.patient_id,row.doctor_user_id)
    no_overlap(row.patient_id,row.doctor_user_id,start,end,row.id)
    row.starts_at=start;row.ends_at=end;event(row,"rescheduled",row.status);db.session.commit()
    return {"appointment":data(row)}

@reception.post("/appointments/<int:appointment_id>/status")
@roles_required("receptionist")
def status(appointment_id):
    payload=json_object()
    if set(payload)!={"status"} or not isinstance(payload["status"],str): raise BadRequest()
    row=locked_appointment(appointment_id)
    if payload["status"] not in TRANSITIONS.get(row.status,set()): raise Conflict()
    old=row.status;row.status=payload["status"];event(row,"status_changed",old);db.session.commit()
    return {"appointment":data(row)}
