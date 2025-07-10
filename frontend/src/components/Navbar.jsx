import { Link } from "react-router-dom";
import { Store, CircleUser, LogOut } from 'lucide-react';
import { useState, useEffect } from "react";

function Navbar() {
    const [isLoggedIn, setIsLoggedIn] = useState(false);


    return (
        <header
          className="border-b border-base-300 fixed w-full top-0 z-50  h-19
        backdrop-blur-lg bg-slate-900"
        >
          <div className="container mx-auto px-4 h-18">
            <div className="flex items-center justify-between h-full">
              {/* Left Side: Logo and Navigation */}
              <div className="flex items-center gap-4">
                <Link to="/" className="flex items-center gap-2.5 hover:opacity-70 transition-all">
                  <div className="size-9 rounded-lg bg-primary/10 flex items-center justify-center">
                    <Store className="w-6 h-6 text-blue-700" />
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
                        className="btn btn-md btn-outline normal-case text-white border-white hover:bg-white hover:text-slate-900"
                        >
                            <CircleUser className="w-6 h-6 text-blue-700" />
                            Your Dashboard
                        </Link>
                        <button
                            onClick={handleLogout}
                            className="btn btn-sm btn-outline normal-case text-white border-white hover:bg-white hover:text-slate-900"
                        >
                            <LogOut className="w-4 h-4" />
                            Logout
                        </button>
                    </div>
                )}
              </div>
            </div>
          </div>
        </header>
  );
}
export default Navbar;
