import { GoogleLogin } from '@react-oauth/google';
import api from '../utils/api';
import {useNavigate} from 'react-router-dom';

const LoginPage = () => {
    const navigate = useNavigate();
    const handleLogin = () => {
        const redirectUri = encodeURIComponent("http://localhost:8000/auth/callback");
        const clientId = "1090386684531-io9ttj5vpiaj6td376v2vs8t3htknvnn.apps.googleusercontent.com";
        const scope = encodeURIComponent("https://www.googleapis.com/auth/calendar openid email");

        
        const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?client_id=${clientId}&redirect_uri=${redirectUri}&response_type=code&scope=${scope}&access_type=offline&prompt=consent&include_granted_scopes=false&state=tempra`;
        
        window.location.href = authUrl;
    };
  const handleSuccess = async (credentialResponse) => {
    const googleToken = credentialResponse.credential;

    try {
        const res = await api.post("/auth/google", {
          token: googleToken
        });
        const { access_token, email } = res.data;
        // Store your own backend-issued JWT
        localStorage.setItem("token", access_token);
        localStorage.setItem("email", email);
        navigate("/");
        console.log("Logged in with Google, token:", access_token);
        // Optionally redirect user or update app state here
      } catch (err) {
        console.error("Backend login with Google failed:", err);
      }

    window.location.href = "/"; // redirect to main app
  };

  const handleError = () => {
    console.log("Google login failed");
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-base-200">
      <h1 className="text-3xl font-bold mb-6">Welcome to TempraAI</h1>
      <div className="shadow-lg p-6 rounded-xl bg-white">
      <button onClick={handleLogin} className="btn btn-primary">
          Sign in with Google
        </button>
      </div>
    </div>
  );
}


export default LoginPage;