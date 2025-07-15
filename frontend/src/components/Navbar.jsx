import { Link } from "react-router-dom";
import { CircleUser, MessageCircleCode, LogOut } from 'lucide-react';
import { useState, useEffect } from "react";

function Navbar() {
    const [isLoggedIn, setIsLoggedIn] = useState(false);
    const [email, setEmail] = useState(null);
    const [loading, setLoading] = useState(true);
    const checkLogin = async () => {
      try {
        const res = await fetch("http://localhost:8000/auth/me", {
          credentials: "include",
        });
        if (!res.ok) throw new Error("Not logged in");
        const data = await res.json();
        setEmail(data.email);
      } catch (err) {
        setEmail(null);
      } finally {
        setLoading(false);
        setIsLoggedIn(true);
      }
    };

    useEffect(() => {
      checkLogin(); // immediately on mount
      const interval = setInterval(checkLogin, 30000);
      return () => clearInterval(interval);
    }, []);

    const handleLogout = () => {
      localStorage.removeItem("token");
      window.location.href = "/login";
    };


    return (
        <header
          className="border-b border-gray-700 w-full top-0 z-50  h-19
        backdrop-blur-lg bg-black"
        >
          <div className="container mx-auto px-4 h-18">
            <div className="flex items-center justify-between h-full">
              {/* Left Side: Logo and Navigation */}
              <div className="flex items-center gap-4">
                <Link to="/" className="flex items-center gap-2.5 hover:opacity-70 transition-all">
                  <div className="size-9 rounded-lg bg-primary/10 flex items-center justify-center">
                    <MessageCircleCode className="w-6 h-6 text-blue-700" />
                  </div>
                  <h1 className="text-lg font-bold text-white">TempraAI</h1>
                </Link>
              </div>

              {/* Right Side: Login Button */}
              <div className="flex items-center gap-3">
                {!isLoggedIn ? (
                    <Link
                    to="/login"
                    className="btn btn-md btn-primary normal-case"
                    >
                        Login
                    </Link>
                ) : (
                    <div className="flex items-center gap-2">
                        <Link
                        to="/seller-dashboard"
                        className=" normal-case text-white border-white"
                        >
                            <CircleUser className="w-6 h-6 text-blue-700" />
                        </Link>
                        {/* <button
                            onClick={handleLogout}
                            className="btn btn-sm btn-outline normal-case text-white border-white hover:bg-white hover:text-slate-900"
                        >
                            <LogOut className="w-4 h-4" />
                            Logout
                        </button> */}
                    </div>
                )}
              </div>
            </div>
          </div>
        </header>
  );
}
export default Navbar;
