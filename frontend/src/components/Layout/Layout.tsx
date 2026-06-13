import { Outlet, NavLink, useNavigate } from "react-router-dom";
import {
  Bot, MessageSquare, BookOpen, LayoutDashboard, LogOut,
} from "lucide-react";
import clsx from "clsx";
import { useWebSocket } from "../../hooks/useWebSocket";
import { useState } from "react";

const NAV = [
  { to: "/dashboard",      label: "Dashboard",      Icon: LayoutDashboard },
  { to: "/chat",           label: "Chat",            Icon: MessageSquare },
  { to: "/knowledge-base", label: "Knowledge Base",  Icon: BookOpen },
];

export default function Layout() {
  const navigate = useNavigate();
  const [eventCount, setEventCount] = useState(0);
  const { connected } = useWebSocket("/ws/events", () =>
    setEventCount((c) => c + 1)
  );

  const logout = () => {
    localStorage.removeItem("token");
    navigate("/login");
  };

  return (
    <div className="flex h-screen overflow-hidden bg-gray-950">
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col">
        {/* Logo */}
        <div className="px-5 py-4 border-b border-gray-800">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-indigo-600 rounded flex items-center justify-center">
              <Bot size={14} className="text-white" />
            </div>
            <div>
              <p className="text-xs font-semibold text-white leading-tight">Local AI</p>
              <p className="text-xs text-gray-400 leading-tight">Chat Platform</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto">
          {NAV.map(({ to, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                clsx(
                  "flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors",
                  isActive
                    ? "bg-indigo-600 text-white"
                    : "text-gray-400 hover:bg-gray-800 hover:text-white"
                )
              }
            >
              <Icon size={15} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-gray-800">
          <div className="flex items-center gap-2 mb-2">
            <span
              className={clsx(
                "w-2 h-2 rounded-full",
                connected ? "bg-green-400" : "bg-red-400"
              )}
            />
            <span className="text-xs text-gray-400">
              {connected ? "Live" : "Reconnecting"}
            </span>
            {eventCount > 0 && (
              <span className="ml-auto text-xs text-indigo-400">
                {eventCount}
              </span>
            )}
          </div>
          <button
            onClick={logout}
            className="flex items-center gap-2 text-xs text-gray-500 hover:text-gray-300 w-full"
          >
            <LogOut size={13} />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
