import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import LegalDocumentPage from './components/LegalDocumentPage.jsx'

const publicLegalPath = window.location.pathname.replace(/\/+$/, '') || '/'
const rootContent = publicLegalPath === '/terms'
  ? <LegalDocumentPage documentType="terms" />
  : publicLegalPath === '/privacy'
    ? <LegalDocumentPage documentType="privacy" />
    : <App />

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      {rootContent}
    </ErrorBoundary>
  </StrictMode>,
)
