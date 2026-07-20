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

export default function MessageBubble({ message }) {
  const isHuman = message.role === 'human'

  if (isHuman) {
    return (
      <div className="flex justify-end">
        <div className="max-w-lg bg-gray-100 rounded-2xl px-4 py-3 text-sm text-gray-800">
          {message.content}
        </div>
      </div>
    )
  }

  // collect all sources from all tool calls in this message
  const allSources = message.toolCalls?.flatMap((tc) => tc.sources || []) || []

  return (
    <div className="flex flex-col gap-2">
      {/* Tool calls */}
      {message.toolCalls?.map((tc, idx) => (
        <ToolCallBadge key={idx} toolCall={tc} />
      ))}

      {/* AI response */}
      {message.content && (
        <div className="text-sm text-gray-800 leading-relaxed prose prose-sm max-w-none prose-p:my-1.5 prose-ul:my-1.5 prose-ol:my-1.5 prose-headings:my-2">
          <ReactMarkdown>{message.content}</ReactMarkdown>
        </div>
      )}

      {/* Sources — after the response, like Claude/Perplexity */}
      <SourcesList sources={allSources} />
    </div>
  )
}