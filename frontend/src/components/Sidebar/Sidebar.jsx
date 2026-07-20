import { useState } from "react";
import { useChat } from "../../context/ChatContext";
import { useAuth } from "../../context/AuthContext";
import ThreadList from "./ThreadList";
import DocumentList from "../Documents/DocumentList";

export default function Sidebar() {
  const {
    createThread,
    setShowProfile,
    showProfile,
    loadProfile,
    showDocuments,
    handleToggleDocuments,
  } = useChat();
  const { logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);

  const handleNewChat = async () => {
    await createThread();
  };

  const handleToggleProfile = async () => {
    if (!showProfile) await loadProfile();
    setShowProfile(!showProfile);
  };

  return (
    <aside
      className={`flex flex-col border-r border-gray-100 bg-gray-50 h-full transition-all duration-200 ${
        collapsed ? "w-14" : "w-64"
      }`}
    >
      {/* Header */}
      <div
        className={`flex items-center border-b border-gray-100 ${collapsed ? "p-3 justify-center" : "p-4 justify-between"}`}
      >
        {!collapsed && (
          <div className="flex items-center gap-2">
            <img src="/favicon.svg" alt="logo" className="w-5 h-5 flex-shrink-0" />
            <h1 className="text-base font-semibold text-gray-800 tracking-tight truncate">
              NeuroGraph AI
            </h1>
          </div>
        )}
        <button
          onClick={() => setCollapsed((prev) => !prev)}
          className="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-lg text-gray-400 hover:bg-gray-200 hover:text-gray-600 transition-colors"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            {collapsed ? (
              <path d="M9 18l6-6-6-6" />
            ) : (
              <path d="M15 18l-6-6 6-6" />
            )}
          </svg>
        </button>
      </div>

      {/* New Chat Button */}
      <div className="p-3">
        <button
          onClick={handleNewChat}
          title="New Chat"
          className={`w-full flex items-center gap-2 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-200 transition-colors ${
            collapsed ? "justify-center px-0 py-2" : "px-3 py-2"
          }`}
        >
          <span className="text-lg leading-none flex-shrink-0">+</span>
          {!collapsed && "New Chat"}
        </button>
      </div>

      {/* Thread List */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden">
        {!collapsed && <ThreadList />}
      </div>

      {/* Documents panel — shown inline in sidebar when toggled */}
      {!collapsed && showDocuments && (
        <div className="border-t border-gray-100 max-h-64 overflow-y-auto">
          <DocumentList />
        </div>
      )}

      {/* Documents Toggle */}
      <div className="p-3 border-t border-gray-100">
        <button
          onClick={handleToggleDocuments}
          title="Documents"
          className={`w-full flex items-center gap-2 rounded-lg text-sm font-medium transition-colors ${
            collapsed ? "justify-center px-0 py-2" : "px-3 py-2"
          } ${
            showDocuments
              ? "bg-gray-200 text-gray-800"
              : "text-gray-600 hover:bg-gray-200"
          }`}
        >
          <span className="flex-shrink-0">📎</span>
          {!collapsed && "Documents"}
        </button>
      </div>

      {/* Profile Toggle */}
      <div className="p-3 border-t border-gray-100">
        <button
          onClick={handleToggleProfile}
          title="Memory Profile"
          className={`w-full flex items-center gap-2 rounded-lg text-sm font-medium transition-colors ${
            collapsed ? "justify-center px-0 py-2" : "px-3 py-2"
          } ${
            showProfile
              ? "bg-gray-200 text-gray-800"
              : "text-gray-600 hover:bg-gray-200"
          }`}
        >
          <span className="flex-shrink-0">🧠</span>
          {!collapsed && "Memory Profile"}
        </button>
      </div>

      {/* Logout */}
      <div className="p-3 border-t border-gray-100">
        <button
          onClick={logout}
          title="Sign out"
          className={`w-full flex items-center gap-2 rounded-lg text-sm font-medium text-gray-500 hover:bg-gray-200 hover:text-red-500 transition-colors ${
            collapsed ? "justify-center px-0 py-2" : "px-3 py-2"
          }`}
        >
          <svg
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="flex-shrink-0"
          >
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
          {!collapsed && "Sign out"}
        </button>
      </div>
    </aside>
  );
}