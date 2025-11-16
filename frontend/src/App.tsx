import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Trucks from './pages/Trucks'
import Settlements from './pages/Settlements'
import Repairs from './pages/Repairs'
import Extractor from './pages/Extractor'

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/trucks" element={<Trucks />} />
          <Route path="/settlements" element={<Settlements />} />
          <Route path="/repairs" element={<Repairs />} />
          <Route path="/extractor" element={<Extractor />} />
        </Routes>
      </Layout>
    </Router>
  )
}

export default App

