"""Preserve recovered originals in a local SQLite review database; never post bills.

The manifest must come from recover_repair_evidence.py. A timestamped SQLite
backup is created before writes. Original hashes and tenant ownership are checked.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.models.repair import Repair
from app.models.truck import Truck
from app.models.finance import FinanceEvidence, FinanceEvent, FinancePosting


def run(database, manifest_path, tenant):
    database = database.resolve(strict=True)
    manifest_path = manifest_path.resolve(strict=True)
    manifest = json.loads(manifest_path.read_text())
    if manifest['tenant_id'] != tenant: raise ValueError('Manifest business mismatch')
    root = manifest_path.parent
    review_path, text_path = root/'invoice-total-review.json', root/'invoice-text.json'
    reviews = {r['sha256']: r for r in json.loads(review_path.read_text())} if review_path.exists() else {}
    texts = {r['sha256']: r['pages'] for r in json.loads(text_path.read_text())} if text_path.exists() else {}
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = database.with_name(database.stem + '-before-repair-evidence-' + stamp + '.db')
    with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as src, sqlite3.connect(backup) as dst: src.backup(dst)
    backup.chmod(0o600)
    engine = create_engine('sqlite:///' + str(database))
    added = reused = 0
    grouped = {}
    for row in manifest['records']:
        for a in row['attachments']:
            if a['status'] != 'preserved': continue
            grouped.setdefault(a['sha256'], {'attachment': a, 'repair_ids': []})['repair_ids'].append(row['id'])
    with Session(engine) as db:
        before = (db.query(FinanceEvent).count(), db.query(FinancePosting).count())
        for digest, item in grouped.items():
            ids = sorted(set(item['repair_ids']))
            count = db.query(Repair).join(Truck,Repair.truck_id==Truck.id).filter(Truck.tenant_id==tenant,Repair.id.in_(ids)).count()
            if count != len(ids): raise ValueError('Manifest references an inaccessible repair')
            attachment = item['attachment']; path = Path(attachment['file']).resolve(strict=True)
            path.relative_to((root/'originals').resolve())
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != digest: raise ValueError('Original hash mismatch')
            existing = db.query(FinanceEvidence).filter_by(tenant_id=tenant,sha256=digest).first()
            if existing:
                if not set(ids) <= set(existing.extracted.get('legacy_repair_ids', [])): raise ValueError('Existing evidence needs explicit repair association review')
                reused += 1; continue
            review = reviews.get(digest, {})
            extracted = {'status':'review_required','legacy_repair_ids':ids,'pages':texts.get(digest,[]),
                         'invoice_review':{k:review[k] for k in ('source_total','delta','status','verification') if k in review},
                         'payment_status':'unverified','payer':None}
            db.add(FinanceEvidence(tenant_id=tenant,sha256=digest,filename=path.name,media_type=attachment['media_type'],content_base64=base64.b64encode(raw).decode(),source_key='recovered-repair:'+digest,extraction_version='repair-recovery-v1',extracted=extracted));added += 1
        db.flush()
        assert before == (db.query(FinanceEvent).count(), db.query(FinancePosting).count())
        db.commit()
    engine.dispose()
    print(json.dumps({'added_evidence':added,'reused_evidence':reused,'posted':0,'backup':str(backup)},indent=2))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database-path',type=Path,required=True)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--tenant',type=int,required=True)
    a=p.parse_args();run(a.database_path,a.manifest,a.tenant)
