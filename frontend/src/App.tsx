import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { TenantProvider } from './contexts/TenantContext'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Trucks from './pages/Trucks'
import Settlements from './pages/Settlements'
import Repairs from './pages/Repairs'
import VehicleDetail from './pages/VehicleDetail'
import Accounting from './pages/Accounting'
import ChartOfAccounts from './pages/ChartOfAccounts'
import JournalEntries from './pages/JournalEntries'
import BalanceSheet from './pages/BalanceSheet'
import IncomeStatement from './pages/IncomeStatement'
import Businesses from './pages/Businesses'

function App() {
  return (
    <TenantProvider>
      <Router>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/businesses" element={<Businesses />} />
            <Route path="/trucks" element={<Trucks />} />
            <Route path="/settlements" element={<Settlements />} />
            <Route path="/repairs" element={<Repairs />} />
            <Route path="/vehicles/:id" element={<VehicleDetail />} />
            <Route path="/accounting" element={<Accounting />} />
            <Route path="/accounting/chart-of-accounts" element={<ChartOfAccounts />} />
            <Route path="/accounting/journal-entries" element={<JournalEntries />} />
            <Route path="/accounting/balance-sheet" element={<BalanceSheet />} />
            <Route path="/accounting/income-statement" element={<IncomeStatement />} />
          </Routes>
        </Layout>
      </Router>
    </TenantProvider>
  )
}

export default App

