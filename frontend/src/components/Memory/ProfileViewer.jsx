import { useChat } from '../../context/ChatContext'

function formatKey(key) {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

function formatRelativeTime(dateStr) {
  if (!dateStr) return ''
  const normalized = dateStr.endsWith('Z') || dateStr.includes('+') ? dateStr : dateStr + 'Z'
  const date = new Date(normalized)
  if (isNaN(date.getTime())) return ''
  const now = new Date()
  const diffMs = now - date
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  return `${diffDays}d ago`
}

export default function ProfileViewer() {
  const { profile, deleteProfileEntry, clearProfile, setShowProfile } = useChat()

  return (
    <aside className="w-72 border-l border-gray-100 bg-gray-50 flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-gray-100 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-gray-800">Memory Profile</h2>
          <p className="text-xs text-gray-400 mt-0.5">What the agent knows about you</p>
        </div>
        <button
          onClick={() => setShowProfile(false)}
          className="text-gray-400 hover:text-gray-600 text-sm"
        >
          ✕
        </button>
      </div>

      {/* Profile entries */}
      <div className="flex-1 overflow-y-auto p-4">
        {profile.length === 0 ? (
          <p className="text-xs text-gray-400 text-center py-8">
            No profile data yet. Start chatting and the agent will learn about you.
          </p>
        ) : (
          <ul className="space-y-2">
            {profile.map((entry) => (
              <li
                key={entry.key}
                className="flex items-start justify-between gap-2 bg-white rounded-xl px-3 py-2.5 border border-gray-100"
              >
                <div className="min-w-0">
                  <p className="text-xs font-medium text-gray-500">
                    {formatKey(entry.key)}
                  </p>
                  <p className="text-sm text-gray-800 mt-0.5 break-words">
                    {entry.value}
                  </p>
                  {entry.updated_at && (
                    <p className="text-xs text-gray-300 mt-1">
                      {formatRelativeTime(entry.updated_at)}
                    </p>
                  )}
                </div>
                <button
                  onClick={() => deleteProfileEntry(entry.key)}
                  className="text-gray-300 hover:text-red-400 transition-colors text-xs flex-shrink-0 mt-0.5"
                  title="Delete"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Clear all */}
      {profile.length > 0 && (
        <div className="p-4 border-t border-gray-100">
          <button
            onClick={clearProfile}
            className="w-full text-xs text-red-400 hover:text-red-600 transition-colors py-1"
          >
            Clear all memory
          </button>
        </div>
      )}
    </aside>
  )
}