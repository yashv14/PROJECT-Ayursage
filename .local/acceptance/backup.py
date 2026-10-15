from datetime import datetime, timezone, timedelta
from pathlib import Path
import sqlite3, json, hashlib

source=Path('.local/auth/auth.sqlite3').resolve()
assert source==Path.cwd()/'.local/auth/auth.sqlite3' and source.is_file()
directory=Path('.local/backups'); directory.mkdir(exist_ok=True)
stamp=datetime.now(timezone(timedelta(hours=5,minutes=30))).strftime('%Y%m%d-%H%M%S')
backup=(directory/f'auth-before-0005-{stamp}.sqlite3').resolve()
assert not backup.exists()
tables=('users','patients','clinical_assessments','assessment_reviews','roles')
def snapshot(con):
    return {'revision':con.execute('SELECT version_num FROM alembic_version').fetchone()[0],
            'counts':{t:con.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in tables},
            'rows_sha256':{t:hashlib.sha256(repr(con.execute('SELECT * FROM '+t+' ORDER BY id').fetchall()).encode()).hexdigest() for t in tables}}
with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as src:
    before=snapshot(src)
    assert before['revision']=='0004_assessment_reviews', before['revision']
    assert before['counts']['patients']==7 and before['counts']['clinical_assessments']==3, before['counts']
    with sqlite3.connect(backup) as dest: src.backup(dest)
    after=snapshot(src)
    assert after==before, 'Source changed during backup; re-evaluate'
with sqlite3.connect(backup.as_uri()+'?mode=ro',uri=True) as check:
    integrity=check.execute('PRAGMA integrity_check').fetchall()
    assert integrity==[('ok',)], integrity
    saved=snapshot(check)
    assert saved==before, 'Backup differs from source'
evidence={'source':str(source),'backup':str(backup),'integrity':'ok',**before}
Path('.local/acceptance/backup-evidence.json').write_text(json.dumps(evidence,indent=2))
print(json.dumps(evidence,indent=2))
