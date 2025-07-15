import { GoogleLogin } from '@react-oauth/google';
import api from '../utils/api';
import {useNavigate} from 'react-router-dom';
import { auth, GoogleAuthProvider, signInWithPopup } from '../firebase';

const LoginPage = () => {
    const navigate = useNavigate();
  
    // Check login status
    // --- NEW FLOW: Firebase Auth ---
    const handleLogin = async () => {
        const provider = new GoogleAuthProvider();
        provider.addScope('https://www.googleapis.com/auth/gmail.modify');
        provider.addScope('https://www.googleapis.com/auth/calendar');
        try {
            const result = await signInWithPopup(auth, provider);
            const idToken = await result.user.getIdToken();
            const credential = GoogleAuthProvider.credentialFromResult(result);
            const accessToken = credential?.accessToken;
            const refreshToken = result.user.refreshToken; // Firebase does not expose Google refreshToken directly
            // Send all tokens to your backend for verification and Google API access
            const res = await api.post("/auth/firebase", {
                id_token: idToken,
                access_token: accessToken,
                refresh_token: refreshToken
            });
            const { access_token, email } = res.data;
            localStorage.setItem("token", access_token);
            localStorage.setItem("email", email);
            navigate("/");
            console.log("Logged in with Firebase, token:", access_token);
        } catch (err) {
            console.error("Firebase login failed:", err);
        }
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
          Sign in with Google (via Firebase)
        </button>
      </div>
    </div>
  );
}


export default LoginPage;