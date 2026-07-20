import { useState, useRef } from "react";
import { useChat } from "../../context/ChatContext";

export default function ChatInput({ disabled }) {
  const [input, setInput] = useState("");
  const { sendMessage, uploadDocuments } = useChat();
  const fileInputRef = useRef(null);

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || disabled) return;
    setInput("");
    await sendMessage(trimmed);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileChange = async (e) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    await uploadDocuments(files);
    // Reset input so same file can be re-selected (dedup handled by backend)
    e.target.value = "";
  };

  return (
    <div className="flex items-end gap-2 border border-gray-200 rounded-2xl px-4 py-3 bg-white shadow-sm focus-within:border-gray-300 transition-colors">
      {/* Hidden file input — PDF and TXT only, multi-select */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.txt"
        multiple
        className="hidden"
        onChange={handleFileChange}
      />

      {/* Paperclip button */}
      <button
        type="button"
        onClick={() => fileInputRef.current?.click()}
        disabled={disabled}
        title="Upload documents (PDF or TXT)"
        className="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-full text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors disabled:opacity-30"
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
        >
          <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
        </svg>
      </button>

      <textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Message NeuroGraph AI..."
        disabled={disabled}
        rows={1}
        className="flex-1 resize-none bg-transparent outline-none text-sm text-gray-800 placeholder-gray-400 max-h-32 overflow-y-auto disabled:opacity-50"
        style={{ lineHeight: "1.5" }}
        onInput={(e) => {
          e.target.style.height = "auto";
          e.target.style.height = Math.min(e.target.scrollHeight, 128) + "px";
        }}
      />

      <button
        onClick={handleSend}
        disabled={disabled || !input.trim()}
        className="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-full bg-gray-800 text-white disabled:opacity-30 hover:bg-gray-700 transition-colors"
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M12 19V5M5 12l7-7 7 7" />
        </svg>
      </button>
    </div>
  );
}
