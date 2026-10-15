"""DDL regression for the real MySQL 8.0 migration error 3818."""
import unittest
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable
from backend.app.models import AppointmentLock


class MySQLCompatibilityTests(unittest.TestCase):
    def test_singleton_lock_check_does_not_reference_an_auto_increment_key(self):
        ddl = str(CreateTable(AppointmentLock.__table__).compile(dialect=mysql.dialect()))
        self.assertIn('CHECK (id = 1)', ddl)
        self.assertNotIn('AUTO_INCREMENT', ddl)
