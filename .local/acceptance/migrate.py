from pathlib import Path
import sys, sqlite3, json, hashlib
sys.path.insert(0,str(Path.cwd()))
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from backend.app.database import enable_sqlite_foreign_keys

proof=json.loads(Path('.local/acceptance/backup-evidence.json').read_text())
target=Path(proof['source']).resolve()
assert target==Path.cwd()/'.local/auth/auth.sqlite3' and target.is_file()
def check(con):
    counts={t:con.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in proof['counts']}
    hashes={t:hashlib.sha256(repr(con.execute('SELECT * FROM '+t+' ORDER BY id').fetchall()).encode()).hexdigest() for t in proof['counts']}
    assert counts==proof['counts'] and hashes==proof['rows_sha256'], 'Existing records changed'
    assert con.execute('PRAGMA integrity_check').fetchall()==[('ok',)]
with sqlite3.connect(Path(proof['backup']).as_uri()+'?mode=ro',uri=True) as backup:
    check(backup)
with sqlite3.connect(target.as_uri()+'?mode=ro',uri=True) as source:
    assert source.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='0004_assessment_reviews'
    check(source)
config=Config(str(Path('backend/alembic.ini').resolve()))
script=ScriptDirectory.from_config(config)
assert script.get_heads()==['0005_patient_doctor_grants']
assert script.get_revision('0005_patient_doctor_grants').down_revision=='0004_assessment_reviews'
engine=create_engine(URL.create('sqlite',database=str(target)),hide_parameters=True)
enable_sqlite_foreign_keys(engine)
try:
    with engine.begin() as connection:
        config.attributes['connection']=connection
        command.upgrade(config,'0005_patient_doctor_grants')
finally: engine.dispose()
with sqlite3.connect(target.as_uri()+'?mode=ro',uri=True) as source:
    revision=source.execute('SELECT version_num FROM alembic_version').fetchone()[0]
    assert revision=='0005_patient_doctor_grants'
    check(source)
    assert source.execute('PRAGMA foreign_key_check').fetchall()==[]
evidence={'target':str(target),'before':'0004_assessment_reviews','after':revision,
          'integrity':'ok','foreign_key_check':'ok','existing_counts':proof['counts'],'existing_rows_unchanged':True}
Path('.local/acceptance/migration-evidence.json').write_text(json.dumps(evidence,indent=2))
print(json.dumps(evidence,indent=2))
