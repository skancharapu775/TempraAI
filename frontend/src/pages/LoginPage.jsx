import { GoogleLogin } from '@react-oauth/google';
import api from '../utils/api';
import {useNavigate} from 'react-router-dom';

const LoginPage = () => {
    const navigate = useNavigate();
  const handleSuccess = async (credentialResponse) => {
    const googleToken = credentialResponse.credential;

    try {
        const res = await api.post("/auth/google", {
          token: googleToken
        });
        const { access_token } = res.data;
        // Store your own backend-issued JWT
        localStorage.setItem("token", access_token);
        navigate("/");
        console.log("Logged in with Google, token:", access_token);
        // Optionally redirect user or update app state here
      } catch (err) {
        console.error("Backend login with Google failed:", err);
      }


    localStorage.setItem("token", token); // store token
    window.location.href = "/"; // redirect to main app
  };

  const handleError = () => {
    console.log("Google login failed");
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-base-200">
      <h1 className="text-3xl font-bold mb-6">Welcome to TempraAI</h1>
      <div className="shadow-lg p-6 rounded-xl bg-white">
        <GoogleLogin onSuccess={handleSuccess} onError={handleError} />
      </div>
    </div>
  );
}


export default LoginPage;