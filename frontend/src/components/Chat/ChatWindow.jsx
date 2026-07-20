import { useRef, useEffect } from "react";
import { useChat } from "../../context/ChatContext";
import MessageBubble from "./MessageBubble";
import StreamingMessage from "./StreamingMessage";
import ChatInput from "./ChatInput";

export default function ChatWindow() {
  const {
    messages,
    streamingMessage,
    activeThreadId,
    isStreaming,
    memoryNotification,
    uploadStatuses,
  } = useChat();
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingMessage?.content]);

  if (!activeThreadId) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <p className="text-2xl font-semibold text-gray-800 mb-2">
            NeuroGraph AI
          </p>
          <p className="text-sm text-gray-400">
            Start a new conversation or select an existing one
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-2xl mx-auto space-y-6">
          {messages.length === 0 && !streamingMessage && (
            <div className="text-center py-12">
              <p className="text-sm text-gray-400">
                Send a message to start the conversation
              </p>
            </div>
          )}

          {messages.map((msg, idx) => (
            <MessageBubble key={idx} message={msg} />
          ))}

          {streamingMessage && <StreamingMessage message={streamingMessage} />}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Memory update notification */}
      {memoryNotification && (
        <div className="px-4 pb-2">
          <div className="max-w-2xl mx-auto">
            <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-purple-50 border border-purple-100 text-xs text-purple-600">
              <span>🧠</span>
              <span>
                Memory updated:{" "}
                <span className="font-medium">
                  {memoryNotification.keys.join(", ")}
                </span>
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Upload status notifications — one pill per file */}
      {uploadStatuses.length > 0 && (
        <div className="px-4 pb-2">
          <div className="max-w-2xl mx-auto flex flex-col gap-1">
            {uploadStatuses.map((s, idx) => (
              <div
                key={idx}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs w-fit ${
                  s.status === "uploading"
                    ? "bg-blue-50 border border-blue-100 text-blue-600"
                    : s.status === "success"
                      ? "bg-green-50 border border-green-100 text-green-600"
                      : s.status === "duplicate"
                        ? "bg-yellow-50 border border-yellow-100 text-yellow-600"
                        : "bg-red-50 border border-red-100 text-red-600"
                }`}
              >
                <span>
                  {s.status === "uploading"
                    ? "📎"
                    : s.status === "success"
                      ? "✅"
                      : s.status === "duplicate"
                        ? "📋"
                        : "❌"}
                </span>
                <span>
                  {s.status === "uploading"
                    ? `Uploading ${s.filename}...`
                    : s.message}
                </span>
                {s.status === "uploading" && (
                  <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-pulse" />
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Input area */}
      <div className="border-t border-gray-100 px-4 py-4">
        <div className="max-w-2xl mx-auto">
          <ChatInput disabled={isStreaming} />
        </div>
      </div>
    </div>
  );
}
