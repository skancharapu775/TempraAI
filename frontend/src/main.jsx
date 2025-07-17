import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import App from './App.jsx'
import Chatbox from './components/Chatbox.jsx'
import Navbar from './components/Navbar.jsx'
import { GoogleOAuthProvider } from '@react-oauth/google';
import LoginPage from './pages/LoginPage.jsx';
import TodoPage from './pages/TodoPage.jsx';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <GoogleOAuthProvider clientId={import.meta.env.VITE_GOOGLE_CLIENT_ID}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<App />}>
            <Route index element={<Chatbox />} />
            <Route path="login" element={<LoginPage />} />
            <Route path="todo" element={<TodoPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </GoogleOAuthProvider>
  </StrictMode>
)
