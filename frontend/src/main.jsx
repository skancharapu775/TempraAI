import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import App from './App.jsx'
import Chatbox from './components/Chatbox.jsx'
import Navbar from './components/Navbar.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />}>
          <Route index element={<Chatbox />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
