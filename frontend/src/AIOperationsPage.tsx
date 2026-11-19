import { useCallback, useEffect, useMemo, useState } from 'react'
import { Activity, AlertTriangle, RefreshCw, Workflow } from 'lucide-react'
import './OperationsPages.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

type WorkflowRow = Record<string, any>
type RunRow = Record<string, any>
type AuditRow = Record<string, any>

function token() {
  return sessionStorage.getItem('cargopilot-token')
}

function headers(): HeadersInit {
  const value = token()
  return value ? { Authorization: `Bearer ${value}` } : {}
}

function label(value: any) {
  if (value === null || value === undefined || value === '') return '—'
  return String(value).replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, c => c.toUpperCase())
}

function date(value: any) {
  if (!value) return '—'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString()
}

function Status({ value }: { value: any }) {
  const normalized = String(value || 'UNKNOWN').toLowerCase()
  const tone = /completed|succeeded/.test(normalized) ? 'success'
    : /failed|cancelled/.test(normalized) ? 'danger'
      : /running|processing|waiting|pending/.test(normalized) ? 'warning' : 'neutral'
  return <span className={`op-status op-status-${tone}`}>{label(value || 'UNKNOWN')}</span>
}

function JsonDetails({ value }: { value: any }) {
  if (value === null || value === undefined || value === '') {
    return <p className="ai-ops-muted">No output was recorded for this run.</p>
  }
  return <pre className="ai-ops-json">{typeof value === 'string' ? value : JSON.stringify(value, null, 2)}</pre>
}

export default function AIOperationsPage() {
  const [workflows, setWorkflows] = useState<WorkflowRow[]>([])
  const [runs, setRuns] = useState<RunRow[]>([])
  const [auditLogs, setAuditLogs] = useState<AuditRow[]>([])
  const [auditError, setAuditError] = useState('')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [workflowSearch, setWorkflowSearch] = useState('')
  const [workflowStatus, setWorkflowStatus] = useState('ALL')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [workflowResponse, runResponse, auditResponse] = await Promise.all([
        fetch(`${API_BASE_URL}/api/agent-workflows`, { headers: headers() }),
        fetch(`${API_BASE_URL}/api/agent-runs`, { headers: headers() }),
        fetch(`${API_BASE_URL}/api/audit-logs`, { headers: headers() }).catch(() => null)
      ])
      if (!workflowResponse.ok) throw new Error(`Workflows: ${workflowResponse.status} ${workflowResponse.statusText}`)
      if (!runResponse.ok) throw new Error(`Agent runs: ${runResponse.status} ${runResponse.statusText}`)
      const workflowData = await workflowResponse.json()
      const runData = await runResponse.json()
      const nextWorkflows = Array.isArray(workflowData) ? workflowData : []
      const nextRuns = Array.isArray(runData) ? runData : []
      setWorkflows(nextWorkflows)
      setRuns(nextRuns)
      if (auditResponse?.ok) {
        const auditData = await auditResponse.json()
        setAuditLogs(Array.isArray(auditData) ? auditData : [])
        setAuditError('')
      } else {
        setAuditLogs([])
        setAuditError(auditResponse ? `Audit trail unavailable (${auditResponse.status}).` : 'Audit trail could not be reached.')
      }
      setSelectedId(current => current && nextWorkflows.some((item: WorkflowRow) => item.workflow_id === current)
        ? current
        : nextWorkflows[0]?.workflow_id ?? null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load AI operations.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const selected = workflows.find(item => item.workflow_id === selectedId) ?? null
  const selectedRuns = useMemo(() => runs
    .filter(run => Number(run.workflow_id) === Number(selectedId))
    .sort((a, b) => Number(a.step_no ?? 0) - Number(b.step_no ?? 0) ||
      new Date(a.started_at || 0).getTime() - new Date(b.started_at || 0).getTime()),
  [runs, selectedId])

  const visibleWorkflows = useMemo(() => workflows.filter(item => {
    const searchable = [item.workflow_id, item.shipment_id, item.exception_id, item.trigger_type, item.current_node, item.status, item.graph_name]
      .map(value => String(value ?? '')).join(' ').toLowerCase()
    return searchable.includes(workflowSearch.toLowerCase()) &&
      (workflowStatus === 'ALL' || item.status === workflowStatus)
  }).sort((a, b) => new Date(b.started_at || 0).getTime() - new Date(a.started_at || 0).getTime()), [workflows, workflowSearch, workflowStatus])

  const selectedAuditLogs = useMemo(() => auditLogs.filter(item =>
    Number(item.workflow_id) === Number(selectedId) ||
    selectedRuns.some(run => Number(run.run_id) === Number(item.run_id)) ||
    (selected?.shipment_id != null && Number(item.shipment_id) === Number(selected.shipment_id))
  ).sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime()), [auditLogs, selectedId, selectedRuns, selected])

  const counts = useMemo(() => ({
    running: workflows.filter(item => item.status === 'RUNNING').length,
    waiting: workflows.filter(item => item.status === 'WAITING_FOR_APPROVAL').length,
    failed: workflows.filter(item => item.status === 'FAILED').length,
    runs: runs.length
  }), [workflows, runs])

  return (
    <main className="operations-page ai-operations-page">
      <div className="op-page-header">
        <div className="op-heading-icon"><Workflow size={21} /></div>
        <div className="op-heading-copy">
          <div className="op-eyebrow">CARGOPILOT 360 / OPERATIONS</div>
          <h1>AI Operations</h1>
          <p>Trace workflow progress, agent execution, model usage and decision outputs.</p>
        </div>
        <button className="op-refresh" onClick={() => void load()} disabled={loading}>
          <RefreshCw size={15} className={loading ? 'op-spin' : ''} /> Refresh
        </button>
      </div>

      {error && <div className="op-error"><AlertTriangle size={16} />{error}</div>}

      <section className="op-metrics-grid">
        <div className="op-metric"><span className="op-metric-label">Workflows</span><strong>{workflows.length}</strong><small>Recorded workflow instances</small></div>
        <div className="op-metric"><span className="op-metric-label">Running</span><strong>{counts.running}</strong><small>Currently marked as running</small></div>
        <div className="op-metric"><span className="op-metric-label">Awaiting approval</span><strong>{counts.waiting}</strong><small>Human review required</small></div>
        <div className="op-metric"><span className="op-metric-label">Failed workflows</span><strong>{counts.failed}</strong><small>Workflows requiring review</small></div>
        <div className="op-metric"><span className="op-metric-label">Agent runs</span><strong>{counts.runs}</strong><small>Recorded execution steps</small></div>
      </section>

      {loading ? (
        <div className="op-loading"><span className="op-loader" />Loading AI workflow records...</div>
      ) : workflows.length === 0 ? (
        <div className="op-empty"><Activity size={24} /><strong>No AI workflows have been recorded.</strong><span>Run CargoPilot Supervisor for a shipment to create a workflow trace.</span></div>
      ) : (
        <div className="ai-ops-layout">
          <section className="ai-ops-workflow-panel">
            <div className="ai-ops-panel-heading">
              <div><span className="op-eyebrow">EXECUTION REGISTER</span><h2>Workflows</h2></div>
              <span>{visibleWorkflows.length} of {workflows.length} records</span>
            </div>
            <div className="ai-ops-workflow-filters">
              <input
                value={workflowSearch}
                onChange={event => setWorkflowSearch(event.target.value)}
                placeholder="Search workflow, shipment or node..."
                aria-label="Search workflows"
              />
              <select
                value={workflowStatus}
                onChange={event => setWorkflowStatus(event.target.value)}
                aria-label="Filter workflows by status"
              >
                <option value="ALL">All statuses</option>
                {Array.from(new Set(workflows.map(item => item.status).filter(Boolean))).sort().map(status => (
                  <option key={status} value={status}>{label(status)}</option>
                ))}
              </select>
            </div>
            <div className="ai-ops-workflow-list">
              {visibleWorkflows.length === 0 ? (
                <p className="ai-ops-muted">No workflows match the current search or status filter.</p>
              ) : visibleWorkflows.map(workflow => (
                <button key={workflow.workflow_id} className={`ai-ops-workflow-card ${selectedId === workflow.workflow_id ? 'is-selected' : ''}`} onClick={() => setSelectedId(workflow.workflow_id)}>
                  <div className="ai-ops-card-top"><strong>Workflow #{workflow.workflow_id}</strong><Status value={workflow.status} /></div>
                  <span>Shipment #{workflow.shipment_id} · {label(workflow.trigger_type)}</span>
                  <span>Current node: {label(workflow.current_node)}</span>
                  <small>{date(workflow.started_at)}</small>
                </button>
              ))}
            </div>
          </section>

          <section className="ai-ops-trace-panel">
            {selected && <>
              <div className="ai-ops-panel-heading">
                <div><span className="op-eyebrow">WORKFLOW TRACE</span><h2>Workflow #{selected.workflow_id}</h2></div>
                <Status value={selected.status} />
              </div>
              <div className="ai-ops-workflow-meta">
                <div><span>Shipment</span><strong>#{selected.shipment_id}</strong></div>
                <div><span>Trigger</span><strong>{label(selected.trigger_type)}</strong></div>
                <div><span>Current node</span><strong>{label(selected.current_node)}</strong></div>
                <div><span>Started</span><strong>{date(selected.started_at)}</strong></div>
                <div><span>Completed</span><strong>{date(selected.completed_at)}</strong></div>
                <div><span>Graph</span><strong>{selected.graph_name || '—'} {selected.graph_version ? `· v${selected.graph_version}` : ''}</strong></div>
                <div><span>Parent workflow</span><strong>{selected.parent_workflow_id ?? '—'}</strong></div>
                <div><span>Exception</span><strong>{selected.exception_id ?? '—'}</strong></div>
                <div><span>Thread</span><strong>{selected.thread_id || '—'}</strong></div>
              </div>
              {selected.error_message && <div className="op-error"><AlertTriangle size={15} />{selected.error_message}</div>}
              <div className="ai-ops-timeline-heading"><h3>Agent execution timeline</h3><span>{selectedRuns.length} runs</span></div>
              {selectedRuns.length === 0 ? <div className="op-empty">No agent runs are linked to this workflow yet.</div> : (
                <div className="ai-ops-run-list">
                  {selectedRuns.map(run => (
                    <details className="ai-ops-run" key={run.run_id}>
                      <summary>
                        <span className="ai-ops-step-number">{run.step_no ?? '—'}</span>
                        <span className="ai-ops-run-main">
                          <strong>{label(run.agent_type)}{run.node_name ? ` · ${label(run.node_name)}` : ''}</strong>
                          <small>{date(run.started_at)} · Run #{run.run_id}</small>
                        </span>
                        <span className="ai-ops-run-status"><Status value={run.execution_status} /></span>
                      </summary>
                      <div className="ai-ops-run-meta">
                        <div><span>Provider</span><strong>{run.provider_name || 'Not recorded'}</strong></div>
                        <div><span>Model</span><strong>{run.model_name || 'Not recorded'}</strong></div>
                        <div><span>Latency</span><strong>{run.latency_ms == null ? '—' : `${run.latency_ms.toLocaleString()} ms`}</strong></div>
                        <div><span>Retries</span><strong>{run.retry_count ?? 0}</strong></div>
                        <div><span>Prompt tokens</span><strong>{run.prompt_tokens == null ? '—' : run.prompt_tokens.toLocaleString()}</strong></div>
                        <div><span>Completion tokens</span><strong>{run.completion_tokens == null ? '—' : run.completion_tokens.toLocaleString()}</strong></div>
                        <div><span>Parent run</span><strong>{run.parent_run_id ?? '—'}</strong></div>
                        <div><span>Fallback used</span><strong>{run.output_data?.fallback_used === true || run.input_data?.fallback_used === true ? 'Yes' : 'Not indicated'}</strong></div>
                        <div><span>Completed</span><strong>{date(run.completed_at)}</strong></div>
                      </div>
                      {run.error_message && <div className="ai-ops-run-error">{run.error_message}</div>}
                      <h4>Recorded output</h4>
                      <JsonDetails value={run.output_data} />
                    </details>
                  ))}
                </div>
              )}
              <div className="ai-ops-audit-section">
                <div className="ai-ops-timeline-heading">
                  <h3>Audit trail</h3>
                  <span>{selectedAuditLogs.length} events</span>
                </div>
                {auditError && <p className="ai-ops-muted">{auditError}</p>}
                {!auditError && selectedAuditLogs.length === 0 ? (
                  <p className="ai-ops-muted">No audit events are linked to this workflow, its runs or shipment.</p>
                ) : (
                  <div className="ai-ops-audit-list">
                    {selectedAuditLogs.map((event, index) => (
                      <details className="ai-ops-audit-event" key={event.log_id ?? `${event.created_at}-${index}`}>
                        <summary>
                          <span className="ai-ops-audit-action">{label(event.action)}</span>
                          <span className="ai-ops-audit-meta">{label(event.actor_type)} · {label(event.entity_type)} #{event.entity_id ?? '—'}</span>
                          <small>{date(event.created_at)}</small>
                        </summary>
                        <div className="ai-ops-audit-meta-grid">
                          <div><span>Actor</span><strong>{event.actor_name || (event.actor_user_id ? `User #${event.actor_user_id}` : label(event.actor_type))}</strong></div>
                          <div><span>Run</span><strong>{event.run_id ?? '—'}</strong></div>
                          <div><span>Workflow</span><strong>{event.workflow_id ?? '—'}</strong></div>
                          <div><span>Shipment</span><strong>{event.shipment_id ?? '—'}</strong></div>
                        </div>
                        {event.details && <JsonDetails value={event.details} />}
                      </details>
                    ))}
                  </div>
                )}
              </div>
            </>}
          </section>
        </div>
      )}
    </main>
  )
}
