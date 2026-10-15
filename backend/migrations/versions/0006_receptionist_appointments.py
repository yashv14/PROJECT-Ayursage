"""Receptionist role and administrative appointments; no clinical permissions."""
from alembic import op
import sqlalchemy as sa
revision = "0006_receptionist_appointments"
down_revision = "0005_patient_doctor_grants"
branch_labels = None
depends_on = None

def prepare_roles_rebuild():
    connection=op.get_bind()
    if connection.dialect.name == "sqlite":
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        if connection.exec_driver_sql("PRAGMA foreign_keys").scalar() and connection.exec_driver_sql("SELECT COUNT(*) FROM users").scalar():
            raise RuntimeError("Role migration requires a fresh dedicated SQLite connection before any data writes")
        raw=connection.connection.driver_connection
        if not raw.in_transaction:
            connection.exec_driver_sql("BEGIN")
    return connection

def verify_references():
    connection=op.get_bind()
    if connection.dialect.name == "sqlite" and connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall():
        raise RuntimeError("Foreign key verification failed")

def upgrade():
    connection = prepare_roles_rebuild()
    with op.batch_alter_table("roles") as batch:
        batch.drop_constraint("ck_roles_code", type_="check")
        batch.create_check_constraint("ck_roles_code", "code IN ('patient','doctor','admin','receptionist')")
    op.bulk_insert(sa.table("roles", sa.column("id", sa.Integer()), sa.column("code", sa.String())), [{"id":4,"code":"receptionist"}])
    options = {"mysql_engine":"InnoDB", "mysql_charset":"utf8mb4"}
    op.create_table("appointment_lock", sa.Column("id",sa.Integer(),primary_key=True,autoincrement=False),
                    sa.CheckConstraint("id = 1", name="ck_appointment_lock"), **options)
    op.bulk_insert(sa.table("appointment_lock",sa.column("id",sa.Integer())),[{"id":1}])
    op.create_table("appointments",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("patient_id",sa.Integer(),sa.ForeignKey("patients.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("doctor_user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("starts_at",sa.DateTime(),nullable=False), sa.Column("ends_at",sa.DateTime(),nullable=False),
        sa.Column("status",sa.String(16),nullable=False),
        sa.Column("created_by_user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("created_at",sa.DateTime(),nullable=False),
        sa.Column("updated_by_user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("updated_at",sa.DateTime(),nullable=False),
        sa.CheckConstraint("ends_at > starts_at",name="ck_appointment_duration"),
        sa.CheckConstraint("status IN ('scheduled','checked_in','completed','cancelled','no_show')",name="ck_appointment_status"), **options)
    for name in ("patient_id","doctor_user_id","starts_at"):
        op.create_index("ix_appointments_"+name,"appointments",[name])
    op.create_table("appointment_events",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("appointment_id",sa.Integer(),sa.ForeignKey("appointments.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("actor_user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("action",sa.String(16),nullable=False),
        sa.Column("from_status",sa.String(16),nullable=True), sa.Column("to_status",sa.String(16),nullable=False),
        sa.Column("starts_at",sa.DateTime(),nullable=False),sa.Column("ends_at",sa.DateTime(),nullable=False),
        sa.Column("occurred_at",sa.DateTime(),nullable=False), **options)
    op.create_index("ix_appointment_events_appointment_id","appointment_events",["appointment_id"])
    verify_references()

def downgrade():
    # Never silently delete provisioned staff during a role downgrade.
    connection=prepare_roles_rebuild()
    if connection.execute(sa.text("SELECT COUNT(*) FROM users WHERE role_id=4")).scalar():
        raise RuntimeError("Receptionist accounts must be handled before downgrade")
    op.drop_table("appointment_events"); op.drop_table("appointments"); op.drop_table("appointment_lock")
    connection.execute(sa.text("DELETE FROM roles WHERE id=4"))
    with op.batch_alter_table("roles") as batch:
        batch.drop_constraint("ck_roles_code",type_="check")
        batch.create_check_constraint("ck_roles_code","code IN ('patient','doctor','admin')")
    verify_references()
