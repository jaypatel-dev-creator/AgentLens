import { useState, useRef, useEffect } from "react";
import { useChat } from "../../context/ChatContext";

export default function ThreadItem({ thread }) {
  const { activeThreadId, selectThread, renameThread, deleteThread } =
    useChat();
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(thread.title);
  const [showActions, setShowActions] = useState(false);
  const inputRef = useRef(null);
  const isActive = activeThreadId === thread.id;

  useEffect(() => {
    if (isEditing) inputRef.current?.focus();
  }, [isEditing]);

  const handleClick = () => {
    if (!isEditing) selectThread(thread.id);
  };

  const handleDoubleClick = () => {
    setEditTitle(thread.title);
    setIsEditing(true);
  };

  const handleRename = async () => {
    const trimmed = editTitle.trim();
    if (trimmed && trimmed !== thread.title) {
      await renameThread(thread.id, trimmed);
    }
    setIsEditing(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") handleRename();
    if (e.key === "Escape") {
      setEditTitle(thread.title);
      setIsEditing(false);
    }
  };

  const handleDelete = async (e) => {
    e.stopPropagation();
    await deleteThread(thread.id);
  };

  return (
    <li
      onClick={handleClick}
      onDoubleClick={handleDoubleClick}
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
      className={`group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-colors text-sm ${
        isActive
          ? "bg-white shadow-sm text-gray-900"
          : "text-gray-600 hover:bg-gray-100"
      }`}
    >
      {isEditing ? (
        <input
          ref={inputRef}
          value={editTitle}
          onChange={(e) => setEditTitle(e.target.value)}
          onBlur={handleRename}
          onKeyDown={handleKeyDown}
          onClick={(e) => e.stopPropagation()}
          className="flex-1 bg-transparent outline-none text-sm text-gray-900 min-w-0"
        />
      ) : (
        <span className="flex-1 truncate">{thread.title}</span>
      )}

      {showActions && !isEditing && (
        <button
          onClick={handleDelete}
          className="text-gray-400 hover:text-red-500 transition-colors text-xs flex-shrink-0"
          title="Delete"
        >
          ✕
        </button>
      )}
    </li>
  );
}
