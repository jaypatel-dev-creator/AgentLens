import ReactMarkdown from 'react-markdown'
import ToolCallBadge from '../ToolCall/ToolCallBadge'

function SourcesList({ sources }) {
  if (!sources || sources.length === 0) return null
  return (
    <div className="flex flex-col gap-1 pt-1">
      {sources.map((source, idx) => (
        <a key={idx} href={source.url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-500 hover:text-blue-700 hover:underline truncate max-w-sm">
          {source.title || source.url}
        </a>
      ))}
    </div>
  )
}

export default function StreamingMessage({ message }) {
  const allSources = message.toolCalls?.flatMap((tc) => tc.sources || []) || []

  return (
    <div className="flex flex-col gap-2">
      {/* Completed tool calls */}
      {message.toolCalls?.map((tc, idx) => (
        <ToolCallBadge key={idx} toolCall={tc} />
      ))}

      {/* Currently running tool */}
      {message.currentTool && (
        <ToolCallBadge toolCall={message.currentTool} />
      )}

      {/* Streaming text */}
      {message.content && (
        <div className="text-sm text-gray-800 leading-relaxed prose prose-sm max-w-none prose-p:my-1.5 prose-ul:my-1.5 prose-ol:my-1.5 prose-headings:my-2">
          <ReactMarkdown>{message.content}</ReactMarkdown>
          <span className="inline-block w-1.5 h-4 bg-gray-400 ml-0.5 animate-pulse rounded-sm align-middle" />
        </div>
      )}

      {/* Sources — after the response, shown only once streaming text exists */}
      {message.content && <SourcesList sources={allSources} />}

      {/* Thinking indicator when no content yet */}
      {!message.content && !message.currentTool && (
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
          <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
          <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
        </div>
      )}
    </div>
  )
} 