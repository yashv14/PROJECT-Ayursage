"""Backup first; optionally apply the reviewed migration on the approved local DB."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import sys,json,sqlite3,hashlib
sys.path.insert(0,str(Path.cwd()))
target=(Path.cwd()/'.local/auth/auth.sqlite3').resolve()
assert target.is_file()
def snapshot(connection):
    names=[row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    rows={name:connection.execute('SELECT * FROM "'+name+'" ORDER BY 1').fetchall() for name in names}
    return {name:{'count':len(values),'sha256':hashlib.sha256(repr(values).encode()).hexdigest()} for name,values in rows.items()}
if len(sys.argv)==1:
    stamp=datetime.now(timezone(timedelta(hours=5,minutes=30))).strftime('%Y%m%d-%H%M%S')
    backup=(Path('.local/backups')/f'auth-before-0006-{stamp}.sqlite3').resolve()
    assert not backup.exists()
    with sqlite3.connect(target.as_uri()+'?mode=ro',uri=True) as source:
        assert source.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='0005_patient_doctor_grants'
        before=snapshot(source)
        with sqlite3.connect(backup) as destination:source.backup(destination)
        assert snapshot(source)==before
    with sqlite3.connect(backup.as_uri()+'?mode=ro',uri=True) as copied:
        assert copied.execute('PRAGMA integrity_check').fetchall()==[('ok',)]
        assert snapshot(copied)==before
    proof={'target':str(target),'backup':str(backup),'integrity':'ok','before':before}
    Path('.local/reception/backup-evidence.json').write_text(json.dumps(proof,indent=2));print(json.dumps(proof,indent=2))
else:
    from sqlalchemy import create_engine
    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from backend.app.database import enable_sqlite_foreign_keys
    proof=json.loads(Path('.local/reception/backup-evidence.json').read_text())
    assert proof['target']==str(target)
    with sqlite3.connect(target.as_uri()+'?mode=ro',uri=True) as source:
        assert source.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='0005_patient_doctor_grants'
        assert snapshot(source)==proof['before']
    config=Config('backend/alembic.ini');script=ScriptDirectory.from_config(config)
    assert script.get_heads()==['0006_receptionist_appointments']
    engine=create_engine('sqlite:///'+target.as_posix());enable_sqlite_foreign_keys(engine)
    try:
        with engine.begin() as connection:
            config.attributes['connection']=connection;command.upgrade(config,'0006_receptionist_appointments')
        with engine.connect() as connection:assert connection.exec_driver_sql('PRAGMA foreign_keys').scalar()==1
    finally:engine.dispose()
    with sqlite3.connect(target.as_uri()+'?mode=ro',uri=True) as source,sqlite3.connect(Path(proof['backup']).as_uri()+'?mode=ro',uri=True) as backup:
        assert source.execute('PRAGMA integrity_check').fetchall()==[('ok',)]
        assert source.execute('PRAGMA foreign_key_check').fetchall()==[]
        assert source.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='0006_receptionist_appointments'
        for table in proof['before']:
            if table=='alembic_version':continue
            old=backup.execute('SELECT * FROM "'+table+'" ORDER BY 1').fetchall()
            actual=[source.execute('SELECT * FROM "'+table+'" WHERE id=?',(row[0],)).fetchone() if table!='grant_administrators' else source.execute('SELECT * FROM grant_administrators WHERE user_id=?',(row[0],)).fetchone() for row in old]
            assert actual==old,table+' original rows changed'
    print('PASS: local 0005 -> 0006; integrity/FKs ok; all original rows preserved')
