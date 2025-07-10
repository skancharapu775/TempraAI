import Navbar from "./components/Navbar";
import { Outlet } from "react-router-dom";

function App() {

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <Navbar />
      <main className="flex-1 min-h-0 overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}

export default App
