"""Validate quoted invoices and source payment observations without booking payments."""
import hashlib,json,re
from datetime import date,datetime
from decimal import Decimal
from app.services import finance as f

BREAKDOWN={'subtotal','shop_supplies_amount','service_fee_amount','tax_amount','discount_amount'}
SETTLEMENT={'settlement_id','revision','status','review_reasons','source_state','principal_total','max_card_fee','max_card_fee_tax','confirmed_principal','pending_principal','unapplied_credit','refund_pending','payments'}
PAYMENT={'attempt_id','revision','rail','state','principal_amount','received_amount','gross_received_amount','applied_principal_amount','applied_card_fee_amount','applied_card_fee_tax_amount','unapplied_amount','confirmed_at','actual_paid_date','paid_date_basis'}
MONEY=re.compile(r'(0|[1-9][0-9]{0,7})\.[0-9]{2}')


def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()
def invalid():f.fail('Invalid complete financial manifest. Existing financial records were preserved.','SOURCE_PROTOCOL_ERROR',502)
def money(v):
    if not isinstance(v,str) or not MONEY.fullmatch(v):invalid()
    return Decimal(v)
def identity(v):
    if not isinstance(v,str) or not v.strip() or len(v)>80:invalid()
def revision(v):
    if not isinstance(v.get('revision'),str) or v['revision']!=digest({k:x for k,x in v.items() if k!='revision'}):invalid()


def validate(invoice,settlement):
    if not isinstance(invoice.get('breakdown'),dict) or set(invoice['breakdown'])!=BREAKDOWN:invalid()
    values={k:money(v) for k,v in invoice['breakdown'].items()}
    if values['subtotal']+values['shop_supplies_amount']+values['service_fee_amount']+values['tax_amount']-values['discount_amount']!=money(invoice['total_amount']):invalid()
    if settlement is None:return
    if not isinstance(settlement,dict) or set(settlement)!=SETTLEMENT:invalid()
    identity(settlement['settlement_id']);revision(settlement)
    if settlement['status'] not in ('available','review_required'):invalid()
    if not isinstance(settlement['review_reasons'],list) or len(settlement['review_reasons'])>50 or any(not isinstance(v,str) or len(v)>100 for v in settlement['review_reasons']):invalid()
    if settlement['source_state'] not in ('unpaid','payment_pending','partially_paid','partially_paid_pending','paid','overpayment_resolution'):invalid()
    for k in ('principal_total','max_card_fee','max_card_fee_tax','confirmed_principal','pending_principal','unapplied_credit','refund_pending'):money(settlement[k])
    if not isinstance(settlement['payments'],list) or len(settlement['payments'])>1000:invalid()
    seen=set()
    for payment in settlement['payments']:
        if not isinstance(payment,dict) or set(payment)!=PAYMENT:invalid()
        identity(payment['attempt_id']);revision(payment)
        if payment['attempt_id'] in seen:invalid()
        seen.add(payment['attempt_id'])
        if payment['rail'] not in ('cash','card','zelle','check','ach','fleet_payment'):invalid()
        if payment['state'] not in ('pending','confirmed','failed','expired','refunded','reversed'):invalid()
        for k in ('principal_amount','applied_principal_amount','applied_card_fee_amount','applied_card_fee_tax_amount','unapplied_amount'):money(payment[k])
        if payment['received_amount'] is not None:money(payment['received_amount'])
        if payment['gross_received_amount'] is not None:money(payment['gross_received_amount'])
        if payment['confirmed_at'] is not None:
            if not isinstance(payment['confirmed_at'],str):invalid()
            parsed=datetime.fromisoformat(payment['confirmed_at'].replace('Z','+00:00'))
            if parsed.tzinfo is None:invalid()
        if payment['paid_date_basis'] not in ('unknown','explicit_verified_date'):invalid()
        if payment['actual_paid_date'] is not None:date.fromisoformat(payment['actual_paid_date'])
        if (payment['paid_date_basis']=='unknown')!=(payment['actual_paid_date'] is None):invalid()


def projection(row):
    """Expense is full obligation, while source receipts remain separate facts."""
    inv=row.get('invoice')
    if not inv:return {'amount':None,'reasons':['current_finalized_invoice_required'],'confirmed':None,'balance':None}
    breakdown=inv['breakdown'];s=row.get('settlement');reasons=[]
    if s is None:
        if money(breakdown['service_fee_amount'])>0:reasons.append('settlement_evidence_required')
        return {'amount':None if reasons else inv['total_amount'],'reasons':reasons,'confirmed':None,'balance':None}
    if s['status']!='available' or s['review_reasons']:reasons.append('source_settlement_review_required')
    principal=money(s['principal_total']);fee=money(s['max_card_fee']);fee_tax=money(s['max_card_fee_tax'])
    confirmed=money(s['confirmed_principal']);pending=money(s['pending_principal'])
    if principal+fee+fee_tax!=money(inv['total_amount']) or fee!=money(breakdown['service_fee_amount']) or fee_tax>money(breakdown['tax_amount']):reasons.append('source_settlement_totals_inconsistent')
    if confirmed+pending>principal or money(s['unapplied_credit']) or money(s['refund_pending']):reasons.append('source_payment_allocation_review_required')
    applied=Decimal('0');actual_fees=Decimal('0');actual_card_fee=Decimal('0');actual_fee_tax=Decimal('0');pending_sum=Decimal('0');cash=False
    for p in s['payments']:
        if p['state'] in ('reversed','refunded'):reasons.append('source_payment_reversal_review_required')
        if p['state']!='confirmed':
            if p['state']=='pending':pending_sum+=money(p['principal_amount'])
            if p['state'] in ('pending','failed','expired') and (p['received_amount'] is not None or p['gross_received_amount'] is not None or any(money(p[k]) for k in ('applied_principal_amount','applied_card_fee_amount','applied_card_fee_tax_amount','unapplied_amount'))):
                reasons.append('source_payment_totals_inconsistent')
            continue
        part=money(p['applied_principal_amount']);pf=money(p['applied_card_fee_amount'])+money(p['applied_card_fee_tax_amount'])
        applied+=part;actual_fees+=pf;actual_card_fee+=money(p['applied_card_fee_amount']);actual_fee_tax+=money(p['applied_card_fee_tax_amount']);cash|=p['rail']=='cash'
        if p['gross_received_amount'] is None or p['received_amount'] is None or part>money(p['principal_amount']) or part>money(p['received_amount']) or part+pf+money(p['unapplied_amount'])!=money(p['gross_received_amount']):reasons.append('source_payment_totals_inconsistent')
        if money(p['unapplied_amount']):reasons.append('source_payment_allocation_review_required')
        if p['rail']!='card' and pf:reasons.append('source_payment_fee_review_required')
    if applied!=confirmed or pending_sum!=pending or actual_card_fee>fee or actual_fee_tax>fee_tax:reasons.append('source_payment_totals_inconsistent')
    if s['source_state']=='paid' and confirmed!=principal:reasons.append('source_settlement_totals_inconsistent')
    if cash and money(breakdown['tax_amount'])-fee_tax>0:reasons.append('cash_tax_policy_conflict')
    amount=principal+actual_fees
    return {'amount':None if reasons else f.money(amount),'reasons':sorted(set(reasons)),
            'confirmed':f.money(confirmed+actual_fees),'balance':f.money(max(Decimal('0'),principal-confirmed))}


def receipt_amount(payment):
    total=money(payment['applied_principal_amount'])+money(payment['applied_card_fee_amount'])+money(payment['applied_card_fee_tax_amount'])
    if payment['state']!='confirmed' or payment['gross_received_amount'] is None or money(payment['unapplied_amount']) or total<=0 or total!=money(payment['gross_received_amount']):
        f.fail('Choose a whole confirmed source payment with no unapplied balance.','SOURCE_PAYMENT_REVIEW_REQUIRED')
    return total
