import { useState } from 'react'

const TOOL_ICONS = {
  calculator: '🧮',
  weather: '🌤️',
  finance: '📈',
  get_datetime: '🕐',
  tavily_search: '🔍',
  document_search: '📄',
}

const TOOL_LABELS = {
  calculator: 'Calculator',
  weather: 'Weather',
  finance: 'Finance',
  get_datetime: 'Date & Time',
  tavily_search: 'Web Search',
  document_search: 'Document Search',
}

export default function ToolCallBadge({ toolCall }) {
  const [expanded, setExpanded] = useState(false)
  const icon = TOOL_ICONS[toolCall.tool_name] || '🔧'
  const label = TOOL_LABELS[toolCall.tool_name] || toolCall.tool_name
  const isRunning = toolCall.status === 'running'
  const hasOutput = toolCall.tool_output && !isRunning

  return (
    <div className="inline-flex flex-col gap-1.5 max-w-lg">
      <button
        type="button"
        onClick={() => hasOutput && setExpanded((prev) => !prev)}
        disabled={!hasOutput}
        className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors w-fit ${
          isRunning
            ? 'bg-blue-50 border-blue-100 text-blue-600'
            : 'bg-gray-50 border-gray-100 text-gray-600 hover:bg-gray-100'
        } ${hasOutput ? 'cursor-pointer' : 'cursor-default'}`}
      >
        <span>{icon}</span>
        <span>{isRunning ? `Using ${label}...` : `Used ${label}`}</span>
        {isRunning && <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-pulse" />}
        {hasOutput && (
          <svg
            width="10"
            height="10"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
            className={`transition-transform ${expanded ? 'rotate-180' : ''}`}
          >
            <path d="M6 9l6 6 6-6" />
          </svg>
        )}
      </button>

      {hasOutput && expanded && (
        <div className="text-xs text-gray-500 px-3 py-2 bg-gray-50 rounded-xl border border-gray-100 max-w-lg">
          {toolCall.tool_output.length > 200
            ? toolCall.tool_output.slice(0, 200) + '...'
            : toolCall.tool_output}
        </div>
      )}
    </div>
  )
}