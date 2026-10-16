"""Own a NEW native MySQL instance; never connect to configured app databases.

Private stdout protocol is consumed by the E2E parent (contains test credentials).
STOP on stdin gracefully shuts down only this verified instance. Files are retained.
"""
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time

import pymysql
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[3]


def main():
    executable = shutil.which('mysqld')
    if executable is None:
        raise RuntimeError('Existing mysqld executable required; no installation attempted')
    base = (ROOT / '.local').resolve()
    token = secrets.token_hex(6)
    directory = base / ('mysql-e2e-' + token)
    assert directory.parent == base and not directory.exists()
    directory.mkdir(parents=True, exist_ok=False)
    data = directory / 'data'
    data.mkdir()
    schema = 'ayursage_e2e_' + token
    username = 'ayur_e2e_' + token
    assert re.fullmatch(r'ayursage_e2e_[0-9a-f]{12}', schema)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    process = None
    root = None
    schema_created = user_created = False
    schema_dropped = user_dropped = False
    with (directory / 'mysqld.log').open('ab') as log:
        try:
            subprocess.run([executable, '--no-defaults', '--initialize-insecure', '--datadir=' + str(data),
                '--console'], check=True, stdout=log, stderr=log, timeout=90,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            process = subprocess.Popen([executable, '--no-defaults', '--no-monitor', '--datadir=' + str(data),
                '--port=' + str(port), '--bind-address=127.0.0.1', '--mysqlx=0',
                '--pid-file=' + str(directory / 'mysqld.pid'), '--console'],
                stdout=log, stderr=log, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError('Owned test MySQL exited before readiness')
                try:
                    root = pymysql.connect(host='127.0.0.1', port=port, user='root', password='',
                        autocommit=True, connect_timeout=2, read_timeout=5, write_timeout=5)
                    break
                except pymysql.MySQLError:
                    time.sleep(0.2)
            if root is None:
                raise RuntimeError('Owned test MySQL readiness timed out')
            assert int((directory / 'mysqld.pid').read_text().strip()) == process.pid, 'OWNED_PID_MISMATCH'
            with root.cursor() as cursor:
                cursor.execute('SELECT @@datadir, @@port, @@server_uuid, VERSION()')
                actual_data, actual_port, server_uuid, version = cursor.fetchone()
                assert Path(actual_data).resolve() == data.resolve(), 'OWNED_DATADIR_MISMATCH'
                assert actual_port == port, 'OWNED_PORT_MISMATCH'
                # First SQL writes follow positive owned-instance identity checks.
                root_password = secrets.token_urlsafe(32)
                cursor.execute("ALTER USER 'root'@'localhost' IDENTIFIED BY %s", (root_password,))
                cursor.execute('CREATE DATABASE `' + schema + '` CHARACTER SET utf8mb4')
                schema_created = True
                password = secrets.token_urlsafe(32)
                cursor.execute("CREATE USER %s@'127.0.0.1' IDENTIFIED BY %s", (username, password))
                user_created = True
                cursor.execute('GRANT ALL PRIVILEGES ON `' + schema + "`.* TO %s@'127.0.0.1'", (username,))
            identity = {'schema': schema, 'port': port, 'server_uuid': server_uuid,
                'datadir': str(data.resolve()), 'version': version, 'username': username}
            (directory / 'identity.json').write_text(json.dumps(identity, indent=2), encoding='utf-8')
            url = URL.create('mysql+pymysql', username=username, password=password,
                host='127.0.0.1', port=port, database=schema).render_as_string(hide_password=False)
            print('MYSQL_READY ' + json.dumps({'url': url, 'identity': identity,
                'identity_file': str(directory / 'identity.json')}), flush=True)
            # EOF (parent failure) also initiates shutdown. No DB/schema drops.
            sys.stdin.readline()
        finally:
            if root is not None:
                try:
                    with root.cursor() as cursor:
                        cursor.execute('SELECT @@datadir, @@port')
                        observed_data, observed_port = cursor.fetchone()
                        assert Path(observed_data).resolve() == data.resolve() and observed_port == port
                        if '--drop-owned-schema' in sys.argv:
                            # Only this run's positively identified server/schema/user.
                            if schema_created:
                                cursor.execute('DROP DATABASE `' + schema + '`')
                                schema_dropped = True
                            if user_created:
                                cursor.execute("DROP USER %s@'127.0.0.1'", (username,))
                                user_dropped = True
                        cursor.execute('SHUTDOWN')
                except pymysql.MySQLError:
                    pass
                root.close()
            if process is not None and process.poll() is None:
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    # Own exact process handle; never stop a service or name-match.
                    process.terminate()
                    process.wait(timeout=10)
            if process is not None:
                (directory / 'stopped.json').write_text(json.dumps({'pid': process.pid,
                    'exit_code': process.returncode, 'running': process.poll() is None,
                    'schema_dropped': schema_dropped, 'user_dropped': user_dropped}), encoding='utf-8')
                if '--drop-owned-schema' in sys.argv and schema_created and not (schema_dropped and user_dropped):
                    raise RuntimeError('Owned schema/user cleanup incomplete')
                if process.returncode != 0:
                    raise RuntimeError('Owned test MySQL did not shut down normally')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Do not expose connection URLs, credentials or SQL parameters.
        code = error.args[0] if error.args and isinstance(error.args[0], int) else 'no-code'
        safe_reason = str(error) if isinstance(error, AssertionError) and str(error).startswith('OWNED_') else ''
        print('MYSQL_FIXTURE_FAILED ' + type(error).__name__ + ' ' + str(code) + ' ' + safe_reason, file=sys.stderr, flush=True)
        raise SystemExit(1)
