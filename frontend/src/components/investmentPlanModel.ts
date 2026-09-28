export type InvestmentDraft = Record<string, string | number | null>

// Changing funding in the editor must not destroy the financed draft. Only
// the submitted cash scenario drops loan fields, so switching back is safe.
export function investmentPayload(plan: InvestmentDraft): InvestmentDraft {
  return plan.funding === 'cash' ? {...plan, financed: 0, initial_cash: plan.acquisition_cost,
    annual_rate: 0, balance_at_sale: 0, financed_fees: 0, quoted_monthly_payment: null} : {...plan}
}

export function savedInvestmentDraft(saved: InvestmentDraft): InvestmentDraft {
  return {...saved}
}

export function formatInvestmentAmount(value: unknown): string {
  return value === '' || value == null ? '' : Number(value).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})
}
