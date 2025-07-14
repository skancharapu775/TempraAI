import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

const AuthSuccess = () => {
  const navigate = useNavigate();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const accessToken = params.get("access_token");
    const refreshToken = params.get("refresh_token");

    if (accessToken && refreshToken) {
      localStorage.setItem("access_token", accessToken);
      localStorage.setItem("refresh_token", refreshToken);
      console.log("✅ Tokens saved to localStorage!");
      navigate("/"); // or wherever
    } else {
      console.error("❌ Missing tokens in callback URL");
    }
  }, []);

  return <div>Logging you in...</div>;
};

export default AuthSuccess;
