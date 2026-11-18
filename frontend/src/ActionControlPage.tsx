import { useCallback, useEffect, useState } from 'react'
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  Clock3,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from 'lucide-react'
import './ActionControlPage.css'

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

type User = {
  user_id: number
  name: string
  role: string
}

type ActionRecord = {
  action_id: number
  plan_id: number
  workflow_id: number
  action_type: string
  action_description: string
  approval_status: string
  execution_status: string
  requires_approval: boolean
  created_at?: string
  [key: string]: any
}

type PendingAction = ActionRecord & {
  plan_priority?: string
  plan_status?: string
  proposed_solution?: string
  reasoning?: string
}

type RecoveryRecord = {
  action_id: number
  action_type: string
  action_description: string
  execution_id: number
  attempt_no: number
  failed_at?: string
  error?: string
  recovery_analysis?: Record<string, any> | null
  recovery_request_allowed: boolean
  alternative_recovery_allowed: boolean
  plan_id: number
  workflow_id: number
}

type Props = {
  currentUser: User
}

function getToken() {
  return sessionStorage.getItem('cargopilot-token')
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken()
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })

  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(
      body.detail || body.message || `Request failed (${response.status})`,
    )
  }
  return body as T
}

function humanize(value: unknown) {
  return String(value ?? '—')
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, letter => letter.toUpperCase())
}

function formatDate(value?: string) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

function Status({ value }: { value: string }) {
  const normalized = value.toLowerCase()
  const tone =
    /approved|succeeded|completed/.test(normalized) ? 'success' :
    /failed|rejected|uncertain/.test(normalized) ? 'danger' :
    /pending|waiting|executing|started/.test(normalized) ? 'warning' : 'neutral'

  return <span className={`action-status action-status-${tone}`}>{humanize(value)}</span>
}

export default function ActionControlPage({ currentUser }: Props) {
  const isManager = ['ADMIN', 'MANAGER'].includes(currentUser.role)
  const [actions, setActions] = useState<ActionRecord[]>([])
  const [pending, setPending] = useState<PendingAction[]>([])
  const [recoveries, setRecoveries] = useState<RecoveryRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [busyActionId, setBusyActionId] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [rejectingActionId, setRejectingActionId] = useState<number | null>(null)
  const [rejectionReason, setRejectionReason] = useState('')

  const loadData = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const actionRows = await request<ActionRecord[]>('/api/actions/')
      setActions(Array.isArray(actionRows) ? actionRows : [])

      if (isManager) {
        const [pendingRows, recoveryRows] = await Promise.all([
          request<PendingAction[]>('/api/actions/pending-approval'),
          request<RecoveryRecord[]>('/api/actions/recovery-review'),
        ])
        setPending(Array.isArray(pendingRows) ? pendingRows : [])
        setRecoveries(Array.isArray(recoveryRows) ? recoveryRows : [])
      } else {
        setPending([])
        setRecoveries([])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load action records.')
    } finally {
      setLoading(false)
    }
  }, [isManager])

  useEffect(() => {
    void loadData()
  }, [loadData])

  const performAction = async (
    actionId: number,
    path: string,
    method = 'POST',
    body?: Record<string, string>,
    successMessage = 'Action completed.',
  ) => {
    setBusyActionId(actionId)
    setError('')
    setNotice('')
    try {
      const result = await request<Record<string, any>>(path, {
        method,
        ...(body ? { body: JSON.stringify(body) } : {}),
      })
      setNotice(result.message || successMessage)
      setRejectingActionId(null)
      setRejectionReason('')
      await loadData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The requested operation failed.')
    } finally {
      setBusyActionId(null)
    }
  }

  const submitRejection = (actionId: number) => {
    if (!rejectionReason.trim()) {
      setError('Enter a reason before rejecting this action.')
      return
    }
    void performAction(
      actionId,
      `/api/actions/${actionId}/reject`,
      'POST',
      { rejection_reason: rejectionReason.trim() },
      'Action rejected.',
    )
  }

  const approvedAwaitingExecution = actions.filter(action =>
    action.approval_status === 'APPROVED' &&
    action.execution_status === 'NOT_STARTED',
  )

  const failedActions = actions.filter(action =>
    action.execution_status === 'FAILED',
  )

  return (
    <main className="action-control-page">
      <header className="action-page-heading">
        <div>
          <span className="action-eyebrow">CARGOPILOT 360 / HUMAN OVERSIGHT</span>
          <h1>Actions &amp; Approvals</h1>
          <p>Review recommendations, approve operational actions and supervise recovery.</p>
        </div>
        <button className="action-refresh" onClick={() => void loadData()} disabled={loading}>
          <RefreshCw size={15} className={loading ? 'action-spin' : ''} />
          Refresh
        </button>
      </header>

      {error && <div className="action-alert action-alert-error"><AlertCircle size={17} />{error}</div>}
      {notice && <div className="action-alert action-alert-success"><CheckCircle2 size={17} />{notice}</div>}

      <section className="action-metrics">
        <article><span>Total actions</span><strong>{actions.length}</strong></article>
        <article><span>Awaiting approval</span><strong>{pending.length}</strong></article>
        <article><span>Approved, not executed</span><strong>{approvedAwaitingExecution.length}</strong></article>
        <article><span>Failed actions</span><strong>{failedActions.length}</strong></article>
      </section>

      {!isManager && (
        <div className="action-alert action-alert-info">
          <ShieldCheck size={17} />
          Approval, execution and recovery controls are available to ADMIN and MANAGER accounts only.
        </div>
      )}

      {loading ? (
        <div className="action-empty"><RefreshCw size={22} className="action-spin" />Loading action records...</div>
      ) : (
        <>
          {isManager && (
            <section className="action-panel">
              <div className="action-panel-heading">
                <div><h2>Pending approval queue</h2><p>Each proposed action requires an explicit manager decision.</p></div>
                <span className="action-count">{pending.length} pending</span>
              </div>

              {pending.length === 0 ? (
                <div className="action-empty"><CheckCircle2 size={22} />There are no actions awaiting approval.</div>
              ) : (
                <div className="action-card-list">
                  {pending.map(action => (
                    <article className="action-card" key={action.action_id}>
                      <div className="action-card-top">
                        <div><span className="action-record-id">ACTION #{action.action_id} · PLAN #{action.plan_id}</span><h3>{humanize(action.action_type)}</h3></div>
                        <Status value={action.approval_status} />
                      </div>
                      <p>{action.action_description}</p>
                      {action.proposed_solution && <div className="action-proposal"><span>PROPOSED SOLUTION</span>{action.proposed_solution}</div>}
                      {action.reasoning && <details className="action-reasoning"><summary>Review decision reasoning</summary><p>{action.reasoning}</p></details>}
                      <div className="action-meta">
                        <span>Priority: <strong>{humanize(action.plan_priority)}</strong></span>
                        <span>Workflow: <strong>#{action.workflow_id}</strong></span>
                        <span>Created: <strong>{formatDate(action.created_at)}</strong></span>
                      </div>
                      {rejectingActionId === action.action_id ? (
                        <div className="action-rejection-form">
                          <label htmlFor={`reject-${action.action_id}`}>Reason for rejection</label>
                          <textarea id={`reject-${action.action_id}`} value={rejectionReason} onChange={event => setRejectionReason(event.target.value)} maxLength={1000} placeholder="Explain why this action should not proceed." />
                          <div><button className="action-button action-button-muted" onClick={() => { setRejectingActionId(null); setRejectionReason('') }}>Cancel</button><button className="action-button action-button-danger" disabled={busyActionId === action.action_id || !rejectionReason.trim()} onClick={() => submitRejection(action.action_id)}>Confirm rejection</button></div>
                        </div>
                      ) : (
                        <div className="action-card-buttons">
                          <button className="action-button action-button-primary" disabled={busyActionId === action.action_id} onClick={() => void performAction(action.action_id, `/api/actions/${action.action_id}/approve`, 'POST', undefined, 'Action approved.')}><CheckCircle2 size={15} />Approve</button>
                          <button className="action-button action-button-muted" disabled={busyActionId === action.action_id} onClick={() => { setRejectingActionId(action.action_id); setRejectionReason('') }}><XCircle size={15} />Reject</button>
                        </div>
                      )}
                    </article>
                  ))}
                </div>
              )}
            </section>
          )}

          {isManager && (
            <section className="action-panel">
              <div className="action-panel-heading">
                <div><h2>Approved actions ready to execute</h2><p>Execution is a separate step after approval.</p></div>
                <span className="action-count">{approvedAwaitingExecution.length} ready</span>
              </div>
              {approvedAwaitingExecution.length === 0 ? (
                <div className="action-empty"><Clock3 size={22} />No approved actions are waiting for execution.</div>
              ) : (
                <div className="action-card-list">
                  {approvedAwaitingExecution.map(action => (
                    <article className="action-card" key={action.action_id}>
                      <div className="action-card-top"><div><span className="action-record-id">ACTION #{action.action_id} · PLAN #{action.plan_id}</span><h3>{humanize(action.action_type)}</h3></div><Status value={action.execution_status} /></div>
                      <p>{action.action_description}</p>
                      <div className="action-card-buttons">
                        <button className="action-button action-button-primary" disabled={busyActionId === action.action_id} onClick={() => void performAction(action.action_id, `/api/actions/${action.action_id}/execute`, 'POST', undefined, 'Action execution finished.')}><Activity size={15} />Execute approved action</button>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </section>
          )}

          {isManager && (
            <section className="action-panel">
              <div className="action-panel-heading">
                <div><h2>Failed action recovery</h2><p>Recovery creates a new proposal; it never resets or silently re-runs the failed action.</p></div>
                <span className="action-count">{recoveries.length} records</span>
              </div>
              {recoveries.length === 0 ? (
                <div className="action-empty"><CheckCircle2 size={22} />No failed actions require recovery review.</div>
              ) : (
                <div className="action-card-list">
                  {recoveries.map(record => (
                    <article className="action-card" key={record.action_id}>
                      <div className="action-card-top"><div><span className="action-record-id">ACTION #{record.action_id} · ATTEMPT {record.attempt_no}</span><h3>{humanize(record.action_type)}</h3></div><Status value="FAILED" /></div>
                      <p>{record.action_description}</p>
                      <div className="action-failure"><span>FAILURE DETAILS</span>{record.error || 'No error details were recorded.'}</div>
                      {record.recovery_analysis && <div className="action-recovery-analysis"><span>RECOVERY ASSESSMENT</span><div><strong>{humanize(record.recovery_analysis.recovery_decision)}</strong><p>{record.recovery_analysis.reason || 'No further explanation supplied.'}</p></div></div>}
                      <div className="action-meta"><span>Plan: <strong>#{record.plan_id}</strong></span><span>Failed: <strong>{formatDate(record.failed_at)}</strong></span></div>
                      <div className="action-card-buttons">
                        <button className="action-button action-button-primary" disabled={!record.recovery_request_allowed || busyActionId === record.action_id} onClick={() => void performAction(record.action_id, `/api/actions/${record.action_id}/recover`, 'POST', undefined, 'A replacement proposal was created for fresh approval.')}>Request safe retry proposal</button>
                        <button className="action-button action-button-muted" disabled={!record.alternative_recovery_allowed || busyActionId === record.action_id} onClick={() => void performAction(record.action_id, `/api/actions/${record.action_id}/recover-alternative`, 'POST', undefined, 'Alternative recovery assessment completed.')}>Find alternative action</button>
                      </div>
                      {!record.recovery_request_allowed && !record.alternative_recovery_allowed && <small className="action-disabled-note">This failure is not eligible for automated recovery. Manual review is required.</small>}
                    </article>
                  ))}
                </div>
              )}
            </section>
          )}

          <section className="action-panel">
            <div className="action-panel-heading">
              <div><h2>Action register</h2><p>Recorded action status and approval history.</p></div>
              <span className="action-count">{actions.length} actions</span>
            </div>
            {actions.length === 0 ? (
              <div className="action-empty">No action records are available.</div>
            ) : (
              <div className="action-table-wrap">
                <table className="action-table">
                  <thead><tr><th>Action</th><th>Plan</th><th>Approval</th><th>Execution</th><th>Created</th></tr></thead>
                  <tbody>
                    {actions.map(action => (
                      <tr key={action.action_id}>
                        <td><strong>#{action.action_id} · {humanize(action.action_type)}</strong><small>{action.action_description}</small></td>
                        <td>#{action.plan_id}</td>
                        <td><Status value={action.approval_status} /></td>
                        <td><Status value={action.execution_status} /></td>
                        <td>{formatDate(action.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </main>
  )
}
