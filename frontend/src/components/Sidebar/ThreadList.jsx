import { useChat } from "../../context/ChatContext";
import ThreadItem from "./ThreadItem";

export default function ThreadList() {
  const { threads } = useChat();

  if (threads.length === 0) {
    return (
      <div className="px-4 py-6 text-xs text-gray-400 text-center">
        No conversations yet
      </div>
    );
  }

  return (
    <ul className="py-1 px-2 space-y-0.5">
      {threads.map((thread) => (
        <ThreadItem key={thread.id} thread={thread} />
      ))}
    </ul>
  );
}
