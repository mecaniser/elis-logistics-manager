# Accounting Integration Plan

## Overview
Integration of double-entry bookkeeping system into Elis Group Manager, supporting multiple business types (Logistics, Tech, Real Estate) with business-specific chart of accounts.

## Status: ✅ Core Features Complete

---

## Phase 1: Foundation & Models ✅ COMPLETE

### Backend Models
- [x] **ChartOfAccount Model** - Hierarchical account structure with tenant isolation
- [x] **JournalEntry Model** - Transaction records with tenant_id
- [x] **JournalEntryLine Model** - Debit/credit entries with tenant_id
- [x] **Tenant Model** - Multi-tenant support with business_type field
- [x] **Database Schema** - All models include tenant_id for data isolation

### Backend Schemas
- [x] **Pydantic Schemas** - Request/response validation for all accounting models
- [x] **Tenant Schemas** - Business details (EIN, addresses, bank accounts, etc.)

---

## Phase 2: Core Accounting Service ✅ COMPLETE

### Account Management
- [x] **get_or_create_account()** - Tenant-aware account creation
- [x] **ensure_standard_accounts_exist()** - Business-type-specific initialization
  - [x] Logistics accounts (Fuel, IFTA, Driver Pay, Vehicles, etc.)
  - [x] Tech accounts (Software subscriptions, Cloud services, Equipment, etc.)
  - [x] Real Estate accounts (Property maintenance, Property tax, HOA fees, etc.)
  - [x] Common accounts (Cash, AR, AP, Equity, Revenue) for all businesses

### Journal Entry Creation
- [x] **create_settlement_journal_entry()** - Auto-create entries from settlements
- [x] **create_repair_journal_entry()** - Auto-create entries from repairs
- [x] **validate_journal_entry_lines()** - Balance validation (debits = credits)

### Financial Statements
- [x] **generate_balance_sheet()** - Tenant-aware balance sheet generation
- [x] **generate_income_statement()** - Tenant-aware income statement generation
- [x] **calculate_account_balance()** - Account balance calculations

### Account Reset
- [x] **reset_chart_of_accounts()** - Delete all accounts and journal entries for re-initialization

---

## Phase 3: API Endpoints ✅ COMPLETE

### Chart of Accounts
- [x] `POST /api/accounting/chart-of-accounts/initialize` - Initialize business-type-specific accounts
- [x] `DELETE /api/accounting/chart-of-accounts/reset` - Reset all accounts for tenant
- [x] `GET /api/accounting/chart-of-accounts` - List accounts (tenant-filtered)
- [x] `POST /api/accounting/chart-of-accounts` - Create custom account
- [x] `GET /api/accounting/chart-of-accounts/{id}` - Get account details
- [x] `PUT /api/accounting/chart-of-accounts/{id}` - Update account
- [x] `DELETE /api/accounting/chart-of-accounts/{id}` - Delete account

### Journal Entries
- [x] `GET /api/accounting/journal-entries` - List entries (tenant-filtered)
- [x] `POST /api/accounting/journal-entries` - Create manual entry
- [x] `GET /api/accounting/journal-entries/{id}` - Get entry details
- [x] `PUT /api/accounting/journal-entries/{id}` - Update entry
- [x] `DELETE /api/accounting/journal-entries/{id}` - Delete entry

### Financial Statements
- [x] `GET /api/accounting/balance-sheet` - Generate balance sheet (tenant-filtered)
- [x] `GET /api/accounting/income-statement` - Generate income statement (tenant-filtered)
- [x] `GET /api/accounting/general-ledger` - Generate general ledger (tenant-filtered)

---

## Phase 4: Frontend Implementation ✅ COMPLETE

### Pages
- [x] **Accounting Overview Page** - Four-panel navigation (Chart of Accounts, Journal Entries, Balance Sheet, Income Statement)
- [x] **ChartOfAccounts Page** - List, create, edit, delete accounts with reset functionality
- [x] **JournalEntries Page** - List, create, edit, delete manual entries
- [x] **BalanceSheet Page** - Display balance sheet with date filter
- [x] **IncomeStatement Page** - Display income statement with date range filter

### Integration
- [x] **Tenant Context** - Business switching with automatic data refresh
- [x] **API Interceptor** - Automatic X-Tenant-ID header injection
- [x] **Data Isolation** - All pages re-fetch on tenant change

---

## Phase 5: Multi-Tenancy & Data Isolation ✅ COMPLETE

### Backend Isolation
- [x] **Tenant Dependency** - `get_tenant_id()` requires X-Tenant-ID header
- [x] **Analytics Filtering** - Dashboard, time-series, PM status filtered by tenant
- [x] **Financial Statement Filtering** - Balance sheet and income statement tenant-aware
- [x] **Account Filtering** - All account queries filtered by tenant_id
- [x] **Journal Entry Filtering** - All journal entry queries filtered by tenant_id

### Frontend Isolation
- [x] **Tenant Context Provider** - Manages current tenant and available tenants
- [x] **Business Switcher UI** - Dropdown in navigation bar
- [x] **Automatic Data Refresh** - All pages re-fetch when tenant changes
- [x] **Conditional Navigation** - Business-type-specific nav links (logistics vs others)

### Dashboard Isolation
- [x] **Logistics Dashboard** - Full dashboard with trucks, settlements, repairs
- [x] **Non-Logistics Placeholders** - Clean "Coming Soon" dashboards for Tech/Real Estate
- [x] **No API Calls** - Non-logistics businesses don't trigger logistics API calls

---

## Phase 6: Business-Type-Specific Features ✅ COMPLETE

### Account Initialization
- [x] **Logistics Accounts** - Fuel, IFTA, Driver Pay, Vehicles, Dispatch Fee, Prepass, Safety, Parking, Maintenance, Decals
- [x] **Tech Accounts** - Software & Subscriptions, Cloud Services, Professional Services, Equipment, Marketing, Salaries, Office Rent, Utilities, Travel & Entertainment
- [x] **Real Estate Accounts** - Property Maintenance, Property Management Fees, Property Insurance, Property Tax, Utilities, HOA Fees, Cleaning & Turnover, Legal & Professional, Repairs & Improvements, Supplies

### Navigation
- [x] **Logistics Navigation** - Dashboard, Trucks, Settlements, Repairs, Accounting
- [x] **Non-Logistics Navigation** - Dashboard, Accounting only

---

## Phase 7: Operational Integration ✅ COMPLETE

### Automatic Journal Entry Creation
- [x] **Settlement Integration** - Auto-create journal entries when settlements are created/updated
- [x] **Repair Integration** - Auto-create journal entries when repairs are created/updated
- [x] **Account Mapping** - Expense categories mapped to appropriate COA accounts

### Account Mapping Utilities
- [x] **get_account_code_for_expense_category()** - Map expense categories to account codes
- [x] **get_revenue_account_code()** - Revenue account mapping
- [x] **get_cash_account_code()** - Cash account mapping
- [x] **get_accounts_receivable_code()** - AR account mapping

---

## Phase 8: Migration & Backfill ✅ COMPLETE

### Migration Scripts
- [x] **migrate_add_tenant_support.py** - Add tenant_id columns to existing tables
- [x] **migrate_add_tenant_details.py** - Add business detail columns to tenants table
- [x] **migrate_recreate_chart_of_accounts_table.py** - Fix unique constraint (tenant_id, code)
- [x] **migrate_create_accounting_entries.py** - Backfill journal entries for existing data

### Production Migration
- [x] **PRODUCTION_MIGRATION_GUIDE.md** - Step-by-step migration instructions
- [x] **Database Backfill** - Existing data assigned to default tenant

---

## Phase 9: UI/UX Enhancements ✅ COMPLETE

### Navigation
- [x] **Breadcrumb Navigation** - Shows current page location
- [x] **Business Switcher** - Top bar dropdown for switching businesses
- [x] **Conditional Menu Items** - Show/hide based on business_type

### User Experience
- [x] **Reset Accounts Feature** - Delete and re-initialize accounts with confirmation modal
- [x] **Loading States** - Proper loading indicators on all pages
- [x] **Error Handling** - User-friendly error messages

---

## Future Enhancements (Not Yet Implemented)

### Advanced Features
- [ ] **Account Reconciliation** - Bank statement reconciliation
- [ ] **Budgeting & Forecasting** - Budget vs actual comparisons
- [ ] **Tax Reporting** - Generate tax-ready reports
- [ ] **Multi-Currency Support** - Handle foreign currency transactions
- [ ] **Audit Trail** - Track all changes to accounts and entries
- [ ] **Account Templates** - Save and reuse account structures
- [ ] **Recurring Entries** - Automate recurring journal entries
- [ ] **Account Hierarchies** - Parent-child account relationships with rollups

### Business-Specific Dashboards
- [ ] **Tech Dashboard** - Projects, clients, contracts, revenue tracking
- [ ] **Real Estate Dashboard** - Properties, rentals, occupancy rates, rental income

### Reporting
- [ ] **Custom Reports** - User-defined financial reports
- [ ] **Export to Excel/PDF** - Export financial statements
- [ ] **Email Reports** - Scheduled report delivery

### Integration
- [ ] **Bank Feeds** - Automatic transaction import from banks
- [ ] **Invoice Integration** - Link invoices to journal entries
- [ ] **Payment Processing** - Integrate payment gateways

---

## Notes

### Key Design Decisions
1. **Multi-Tenancy First** - All data models include tenant_id from the start
2. **Business-Type Awareness** - Chart of accounts initialized based on business_type
3. **Hybrid Approach** - Maintains operational profitability tracking alongside accounting
4. **Automatic Integration** - Settlements and repairs auto-create journal entries
5. **Strict Isolation** - No data leakage between tenants; X-Tenant-ID required for all requests

### Technical Debt
- Balance sheet still references "vehicles" in response schema (should be "fixed_assets" for non-logistics)
- Some hardcoded account codes in account mapping utilities
- Journal entry deletion doesn't cascade properly in some edge cases

---

## Last Updated
December 2024 - Core accounting integration complete with multi-tenancy and business-type-specific features.

