import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import LegalDocumentPage from './components/LegalDocumentPage.jsx'
import MobileApp from './mobile/MobileApp.jsx'

const publicLegalPath = window.location.pathname.replace(/\/+$/, '') || '/'
const isPublicLegalRoute = publicLegalPath === '/terms' || publicLegalPath === '/privacy'
const isMobileRoute = publicLegalPath === '/m' || publicLegalPath.startsWith('/m/')

if (isPublicLegalRoute) {
  document.documentElement.classList.add('public-legal-route')
  document.body.classList.add('public-legal-route')
}

const rootContent = publicLegalPath === '/terms'
  ? <LegalDocumentPage documentType="terms" />
  : publicLegalPath === '/privacy'
    ? <LegalDocumentPage documentType="privacy" />
    : isMobileRoute
      ? <MobileApp />
      : <App />

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      {rootContent}
    </ErrorBoundary>
  </StrictMode>,
)
