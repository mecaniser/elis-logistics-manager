"""Identify known invoice issuers, never infer how the invoice was paid."""
import re


def invoice_payee(text):
    # Issuer header only: a payee mentioned in repair notes is not the issuer.
    header = '\n'.join(text.splitlines()[:12])
    names = []
    for pattern, name in (
        (r'caro\s*me[ck]+(?:\s+diesel)?', 'CaroMeck Diesel PM LLC'),
        (r'truck\s+pit\s+stop', 'Truck Pit Stop'),
        (r'tarp\s*stop', 'Tarpstop'),
    ):
        if re.search(pattern, header, re.I): names.append(name)
    return names


def payee_details(evidence):
    found = {}
    for doc in evidence:
        text = '\n'.join(str(p.get('text', '')) for p in doc.extracted.get('pages', []))
        names = invoice_payee(text)
        parsed = doc.extracted.get('parsed') or {}
        if parsed.get('vendor'): names.extend(invoice_payee(str(parsed['vendor'])))
        for name in names: found.setdefault(name, []).append(doc.id)
    return {'name': next(iter(found)) if len(found) == 1 else None,
            'basis': 'invoice_header' if len(found) == 1 else 'conflicting_headers' if found else 'unknown',
            'candidates': sorted(found), 'evidence_ids': sorted({i for ids in found.values() for i in ids})}
