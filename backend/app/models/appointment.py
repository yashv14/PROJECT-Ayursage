"""Administrative bookings; never clinical access grants."""
from datetime import datetime
from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database import db

OPTIONS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}
class AppointmentLock(db.Model):
    __tablename__ = "appointment_lock"
    __table_args__ = (CheckConstraint("id = 1", name="ck_appointment_lock"), OPTIONS.copy())
    # Singleton is explicitly seeded as 1; MySQL CHECK cannot reference an
    # AUTO_INCREMENT column (error 3818).
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)

class Appointment(db.Model):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_appointment_duration"),
        CheckConstraint("status IN ('scheduled','checked_in','completed','cancelled','no_show')", name="ck_appointment_status"),
        OPTIONS.copy(),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="RESTRICT"), index=True)
    doctor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    starts_at: Mapped[datetime] = mapped_column(index=True)
    ends_at: Mapped[datetime] = mapped_column()
    status: Mapped[str] = mapped_column(String(16))
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column()
    updated_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    updated_at: Mapped[datetime] = mapped_column()

class AppointmentEvent(db.Model):
    __tablename__ = "appointment_events"
    __table_args__ = OPTIONS.copy()
    id: Mapped[int] = mapped_column(primary_key=True)
    appointment_id: Mapped[int] = mapped_column(ForeignKey("appointments.id", ondelete="RESTRICT"), index=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    action: Mapped[str] = mapped_column(String(16))
    from_status: Mapped[str | None] = mapped_column(String(16))
    to_status: Mapped[str] = mapped_column(String(16))
    starts_at: Mapped[datetime] = mapped_column()
    ends_at: Mapped[datetime] = mapped_column()
    occurred_at: Mapped[datetime] = mapped_column()
