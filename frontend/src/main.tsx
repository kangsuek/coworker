import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// 저장된 테마를 즉시 적용해 초기 로드 시 깜빡임 방지
try {
  if (localStorage.getItem('coworker_theme') === 'dark') {
    document.documentElement.classList.add('dark')
  }
} catch {
  /* ignore */
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
