import { useChat } from '../../context/ChatContext'

export default function DocumentList() {
  const { documents, deleteDocument } = useChat()

  if (documents.length === 0) {
    return (
      <div className="px-4 py-3 text-xs text-gray-400">
        No documents uploaded yet. Use the 📎 icon in the chat input to upload PDF or TXT files.
      </div>
    )
  }

  return (
    <div className="px-3 py-2 flex flex-col gap-1">
      <p className="text-xs font-medium text-gray-500 px-1 mb-1">Uploaded Documents</p>
      {documents.map((doc) => (
        <div
          key={doc.sha256}
          className="flex items-center justify-between gap-2 px-2 py-1.5 rounded-lg hover:bg-gray-100 group"
        >
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-xs flex-shrink-0">📄</span>
            <div className="min-w-0">
              <p className="text-xs text-gray-700 truncate" title={doc.filename}>
                {doc.filename}
              </p>
              <p className="text-xs text-gray-400">{doc.chunk_count} chunks</p>
            </div>
          </div>
          <button
            onClick={() => deleteDocument(doc.sha256)}
            title="Delete document"
            className="flex-shrink-0 opacity-0 group-hover:opacity-100 w-5 h-5 flex items-center justify-center rounded text-gray-400 hover:text-red-500 hover:bg-red-50 transition-all"
          >
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
      ))}
    </div>
  )
}