import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '../index.css'
import App from './App'
import { FlowOverviewExport, bakedOverview } from './flowbuilder/FlowOverviewPage'

// An exported Flow Overview is this same bundle with the flows baked in: it
// shows that one page and never calls the server.
const baked = bakedOverview()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {baked ? <FlowOverviewExport model={baked} /> : <App />}
  </StrictMode>,
)
