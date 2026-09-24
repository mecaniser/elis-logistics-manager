"""Recover referenced repair attachments from a read-only local review snapshot.

Only existing HTTPS Cloudinary references are fetched; redirects are not followed.
No application startup, database mutation, accounting entry or payment inference.
"""
import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit
import httpx

MAX_BYTES = 20 * 1024 * 1024


def media_type(content):
    if content.startswith(b'%PDF'): return 'application/pdf', '.pdf'
    if content.startswith(b'\xff\xd8\xff'): return 'image/jpeg', '.jpg'
    if content.startswith(b'\x89PNG\r\n\x1a\n'): return 'image/png', '.png'
    if content.startswith(b'RIFF') and content[8:12] == b'WEBP': return 'image/webp', '.webp'
    return None, None


async def recover(database, output, tenant):
    with sqlite3.connect(database.resolve(strict=True).as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        records = [dict(r) for r in db.execute('SELECT r.* FROM repairs r JOIN trucks t ON r.truck_id=t.id WHERE t.tenant_id=? ORDER BY r.id', (tenant,))]
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    originals = output / 'originals'; originals.mkdir(exist_ok=True, mode=0o700)
    sources = {}
    for row in records:
        refs = ([('receipt', row['receipt_path'])] if row['receipt_path'] else [])
        refs += [('image', p) for p in (json.loads(row['image_paths'] or 'null') or [])]
        row['attachments'] = [{'role': role, 'source': p} for role, p in refs]
        for _, p in refs: sources[p] = None
    semaphore = asyncio.Semaphore(4)
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
        async def fetch(source):
            parsed = urlsplit(source)
            if parsed.scheme != 'https' or parsed.hostname != 'res.cloudinary.com' or parsed.port or parsed.username:
                return {'status': 'unsupported_source'}
            async with semaphore:
                try:
                    async with client.stream('GET', source) as response:
                        if response.status_code != 200: return {'status': 'unavailable', 'http_status': response.status_code}
                        content = bytearray()
                        async for chunk in response.aiter_bytes():
                            content.extend(chunk)
                            if len(content) > MAX_BYTES: return {'status': 'too_large'}
                    content = bytes(content)
                    mime, suffix = media_type(content)
                    if not mime: return {'status': 'unsupported_content'}
                    digest = hashlib.sha256(content).hexdigest()
                    path = originals / (digest + suffix)
                    if path.exists():
                        if hashlib.sha256(path.read_bytes()).hexdigest() != digest: raise ValueError('Saved original hash mismatch')
                    else:
                        with path.open('xb') as file: file.write(content)
                        path.chmod(0o600)
                    return {'status': 'preserved', 'sha256': digest, 'media_type': mime, 'bytes': len(content), 'file': str(path.resolve())}
                except httpx.HTTPError as exc:
                    return {'status': 'unavailable', 'error_type': type(exc).__name__}
        results = await asyncio.gather(*(fetch(source) for source in sources))
    sources = dict(zip(sources, results))
    for row in records:
        for item in row['attachments']: item.update(sources[item['source']])
        row['payment_status'] = 'unverified'
        row['payer'] = None
        row['posting_status'] = 'review_required'
        row['review_reasons'] = ['Confirm incurred amount, payer, funding and any settlement deduction before posting.']
        if not any(a['status'] == 'preserved' for a in row['attachments']): row['review_reasons'].append('No original attachment recovered.')
    counts = dict(Counter(x['status'] for x in results))
    result = {'version': 'repair-recovery-v1', 'tenant_id': tenant, 'captured_at': datetime.now(timezone.utc).isoformat(), 'records': records, 'attachment_counts': counts, 'posted': 0}
    manifest = output / ('manifest-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    with manifest.open('x') as file: json.dump(result, file, indent=2)
    manifest.chmod(0o600)
    print(json.dumps({'records': len(records), 'attachments': counts, 'records_with_preserved_attachment': sum(any(a['status']=='preserved' for a in r['attachments']) for r in records), 'manifest': str(manifest)}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database-path', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--tenant', type=int, required=True)
    args = parser.parse_args()
    asyncio.run(recover(args.database_path, args.output_dir, args.tenant))


if __name__ == '__main__': main()
