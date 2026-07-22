import { useChat } from '../../context/ChatContext'

function MetricRow({ label, value, sub }) {
  return (
    <div className="flex items-start justify-between py-2 border-b border-gray-50 last:border-0">
      <span className="text-xs text-gray-400 leading-tight">{label}</span>
      <div className="text-right">
        <span className="text-xs font-medium text-gray-800">{value}</span>
        {sub && <p className="text-xs text-gray-400">{sub}</p>}
      </div>
    </div>
  )
}

function SectionHeader({ icon, title }) {
  return (
    <div className="flex items-center gap-1.5 mb-2 mt-4 first:mt-0">
      <span className="text-sm">{icon}</span>
      <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{title}</span>
    </div>
  )
}

function ToolCallRow({ call, idx }) {
  return (
    <div className="flex items-center gap-2 py-1.5 border-b border-gray-50 last:border-0">
      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${call.success ? 'bg-green-400' : 'bg-red-400'}`} />
      <span className="text-xs text-gray-700 flex-1 truncate">{call.name}</span>
      <span className="text-xs text-gray-400 flex-shrink-0">{call.latency_ms}ms</span>
    </div>
  )
}

export default function ObservabilityPanel() {
  const { sessionMetrics, activeThreadId, isStreaming } = useChat()

  if (!activeThreadId) return null

  return (
    <aside className="w-72 flex-shrink-0 border-l border-gray-100 bg-white flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm">🔭</span>
          <span className="text-sm font-semibold text-gray-700">Observability</span>
        </div>
        {isStreaming && (
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
            <span className="text-xs text-green-600">Live</span>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {!sessionMetrics ? (
          <div className="flex flex-col items-center justify-center h-full text-center py-12">
            <span className="text-2xl mb-2">📡</span>
            <p className="text-xs text-gray-400 leading-relaxed">
              Send a message to start<br />collecting metrics
            </p>
          </div>
        ) : (
          <>
            {/* LLM */}
            <SectionHeader icon="🧠" title="LLM" />
            <div className="bg-gray-50 rounded-lg px-3 py-1 mb-1">
              <MetricRow
                label="Tokens in"
                value={sessionMetrics.tokens.input.toLocaleString()}
              />
              <MetricRow
                label="Tokens out"
                value={sessionMetrics.tokens.output.toLocaleString()}
              />
              <MetricRow
                label="Total tokens"
                value={sessionMetrics.tokens.total.toLocaleString()}
              />
              <MetricRow
                label="LLM calls"
                value={sessionMetrics.llm.calls}
              />
              <MetricRow
                label="Last latency"
                value={`${sessionMetrics.llm.last_latency_ms}ms`}
              />
            </div>

            {/* Tools */}
            <SectionHeader icon="🔧" title="Tools" />
            <div className="bg-gray-50 rounded-lg px-3 py-1 mb-1">
              <MetricRow
                label="Total calls"
                value={sessionMetrics.tools.total_calls}
              />
              <MetricRow
                label="Successful"
                value={sessionMetrics.tools.successful}
              />
              {sessionMetrics.tools.failed > 0 && (
                <MetricRow
                  label="Failed"
                  value={sessionMetrics.tools.failed}
                />
              )}
            </div>
            {sessionMetrics.tools.calls.length > 0 && (
              <div className="bg-gray-50 rounded-lg px-3 py-1 mb-1">
                {sessionMetrics.tools.calls.map((call, idx) => (
                  <ToolCallRow key={idx} call={call} idx={idx} />
                ))}
              </div>
            )}

            {/* Retrieval */}
            <SectionHeader icon="📚" title="RAG Retrieval" />
            <div className="bg-gray-50 rounded-lg px-3 py-1 mb-1">
              {sessionMetrics.retrieval.total_queries === 0 ? (
                <p className="text-xs text-gray-400 py-2">No retrieval queries this session</p>
              ) : (
                <>
                  <MetricRow
                    label="Queries"
                    value={sessionMetrics.retrieval.total_queries}
                  />
                  <MetricRow
                    label="Avg latency"
                    value={sessionMetrics.retrieval.avg_latency_ms != null
                      ? `${sessionMetrics.retrieval.avg_latency_ms}ms`
                      : '—'}
                  />
                  <MetricRow
                    label="Max latency"
                    value={sessionMetrics.retrieval.max_latency_ms != null
                      ? `${sessionMetrics.retrieval.max_latency_ms}ms`
                      : '—'}
                  />
                </>
              )}
            </div>

            {/* LTM */}
            <SectionHeader icon="💾" title="Memory (LTM)" />
            <div className="bg-gray-50 rounded-lg px-3 py-1 mb-1">
              <MetricRow label="Reads" value={sessionMetrics.ltm.reads} />
              <MetricRow label="Writes" value={sessionMetrics.ltm.writes} />
              <MetricRow label="Total ops" value={sessionMetrics.ltm.total} />
            </div>

            {/* Session */}
            <SectionHeader icon="⏱" title="Session" />
            <div className="bg-gray-50 rounded-lg px-3 py-1 mb-4">
              <MetricRow
                label="Duration"
                value={`${sessionMetrics.session.duration_seconds}s`}
              />
              <MetricRow
                label="Session ID"
                value={activeThreadId.slice(0, 8) + '…'}
                sub="matches SigNoz trace"
              />
            </div>
          </>
        )}
      </div>

      {/* Footer — SigNoz link */}
      <div className="px-4 py-3 border-t border-gray-100">
        <a
          href="https://pro-grouper.us2.signoz.cloud"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-600 transition-colors"
        >
          <span>📊</span>
          <span>View full traces in SigNoz</span>
        </a>
      </div>
    </aside>
  )
}