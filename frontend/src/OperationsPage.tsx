
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Activity, AlertTriangle, ArrowUpRight, CheckCircle2, Clock3,
  FileSearch, Filter, RefreshCw, Search, ShieldAlert, Workflow, X
} from 'lucide-react'
import './OperationsPages.css'
import AIOperationsPage from './AIOperationsPage'

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

type PageKey =
  | 'Exceptions'
  | 'Investigations'
  | 'Risk Monitoring'
  | 'AI Operations'
  | 'Resolution Plans'
  | 'Actions & Approvals'
  | 'Analytics'
  | 'Audit Logs'

type ShipmentRef = {
  shipment_id: number
  shipment_ref?: string
  container_no?: string
}

type Props = {
  page: PageKey
  shipments?: ShipmentRef[]
}

type Row = Record<string, any>

const PAGE_CONFIG: Record<PageKey, {
  description: string
  endpoints: string[]
  icon: typeof Activity
  empty: string
}> = {
  Exceptions: {
    description: 'Monitor operational exceptions, manage their lifecycle and verify resolutions.',
    endpoints: ['/api/exceptions/'],
    icon: AlertTriangle,
    empty: 'No exceptions have been recorded.'
  },
  Investigations: {
    description: 'Review investigation findings, evidence and operational causes.',
    endpoints: ['/api/investigations/'],
    icon: FileSearch,
    empty: 'No investigations have been recorded.'
  },
  'Risk Monitoring': {
    description: 'Track shipment risk assessments and identify shipments requiring attention.',
    endpoints: ['/api/risk-assessments/'],
    icon: ShieldAlert,
    empty: 'No risk assessments are available.'
  },
  'AI Operations': {
    description: 'Monitor agent workflows, runs and automated operations.',
    endpoints: ['/api/agent-workflows/', '/api/agent-runs/'],
    icon: Workflow,
    empty: 'No agent workflows or runs have been recorded.'
  },
  'Resolution Plans': {
    description: 'Review recommended resolution plans and their current progress.',
    endpoints: ['/api/resolution-plans/'],
    icon: CheckCircle2,
    empty: 'No resolution plans are available.'
  },
  'Actions & Approvals': {
    description: 'Review operational actions, approval requirements and execution outcomes.',
    endpoints: ['/api/actions/', '/api/action-executions/'],
    icon: Activity,
    empty: 'No actions or execution records are available.'
  },
  Analytics: {
    description: 'Review operational performance indicators and exception trends.',
    endpoints: ['/api/dashboard/overview', '/api/dashboard/automation-kpis'],
    icon: ArrowUpRight,
    empty: 'Analytics data is not available yet.'
  },
  'Audit Logs': {
    description: 'Inspect the recorded activity trail for operational traceability.',
    endpoints: ['/api/audit-logs/'],
    icon: Clock3,
    empty: 'No audit log entries are available.'
  }
}

function getToken() {
  return sessionStorage.getItem('cargopilot-token')
}

function unwrapRows(payload: any): Row[] {
  if (Array.isArray(payload)) return payload
  if (!payload || typeof payload !== 'object') return []

  for (const key of [
    'items', 'results', 'data', 'records', 'exceptions',
    'investigations', 'assessments', 'workflows', 'runs',
    'plans', 'actions', 'logs'
  ]) {
    if (Array.isArray(payload[key])) return payload[key]
  }

  return [payload]
}

function humanize(value: string) {
  return value
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .toLowerCase()
    .replace(/\b\w/g, letter => letter.toUpperCase())
}

function displayValue(value: any): string {
  if (value === null || value === undefined || value === '') return '—'

  if (typeof value === 'boolean') return value ? 'Yes' : 'No'

  if (typeof value === 'object') {
    return Array.isArray(value) ? `${value.length} items` : JSON.stringify(value)
  }

  return String(value)
}

/* Decode HTML entities and remove unwanted Markdown formatting. */
function decodeDetailText(value: string): string {
  return value
    .replace(/&#x([0-9a-f]+);/gi, (_, code) =>
      String.fromCodePoint(parseInt(code, 16))
    )
    .replace(/&#(\d+);/g, (_, code) =>
      String.fromCodePoint(Number(code))
    )
    .replace(/\*\*/g, '')
    .trim()
}

/* Detect JSON whether it arrives as an object or embedded in a string. */
function parseDetailValue(value: any): {
  prefix: string
  data: any
  isStructured: boolean
} {
  if (value === null || value === undefined || value === '') {
    return {
      prefix: '',
      data: '—',
      isStructured: false
    }
  }

  if (typeof value === 'object') {
    return {
      prefix: '',
      data: value,
      isStructured: true
    }
  }

  if (typeof value !== 'string') {
    return {
      prefix: '',
      data: String(value),
      isStructured: false
    }
  }

  const cleaned = decodeDetailText(value)

  const start = cleaned.indexOf('{')
  const end = cleaned.lastIndexOf('}')

  if (start !== -1 && end > start) {
    const prefix = cleaned.slice(0, start).trim()
    const jsonText = cleaned.slice(start, end + 1)

    try {
      return {
        prefix,
        data: JSON.parse(jsonText),
        isStructured: true
      }
    } catch {
      // Keep the original text if the embedded JSON is invalid.
    }
  }

  try {
    return {
      prefix: '',
      data: JSON.parse(cleaned),
      isStructured: true
    }
  } catch {
    return {
      prefix: '',
      data: cleaned,
      isStructured: false
    }
  }
}

function formatDetailValue(key: string, value: any): string {
  if (value === null || value === undefined || value === '') {
    return '—'
  }

  const normalized = key.toLowerCase()

  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No'
  }

  if (typeof value === 'number') {
    if (normalized.includes('response_sla_hours')) {
      return `${value} hours`
    }

    if (
      normalized.includes('minutes') ||
      normalized.includes('tta') ||
      normalized.includes('ttr')
    ) {
      return `${Number(value).toLocaleString(undefined, {
        maximumFractionDigits: 2
      })} minutes`
    }

    if (
      normalized.includes('score') &&
      value >= 0 &&
      value <= 1
    ) {
      return `${(value * 100).toFixed(1)}%`
    }

    return value.toLocaleString()
  }

  if (typeof value === 'object') {
    return Array.isArray(value)
      ? `${value.length} items`
      : 'Structured information'
  }

  return String(value)
}

function findId(row: Row) {
  return row.plan_id ??
    row.exception_id ??
    row.investigation_id ??
    row.assessment_id ??
    row.risk_assessment_id ??
    row.workflow_id ??
    row.run_id ??
    row.action_id ??
    row.audit_log_id ??
    row.id ??
    '—'
}

function shipmentLabel(row: Row, shipments: ShipmentRef[]) {
  const id = row.shipment_id
  if (id === undefined || id === null) return '—'

  const shipment = shipments.find(
    item => item.shipment_id === Number(id)
  )

  return shipment?.shipment_ref || `Shipment #${id}`
}

function getStatus(row: Row) {
  return String(
    row.status ?? row.execution_status ?? row.workflow_status ?? 'UNKNOWN'
  ).toUpperCase()
}

function getSeverity(row: Row) {
  return String(
    row.severity ?? row.priority ?? row.risk_level ??
    row.current_risk_level ?? row.urgency ?? 'UNSPECIFIED'
  ).toUpperCase()
}

function getExceptionType(row: Row) {
  return String(
    row.exception_type ?? row.type ?? row.category ?? 'Operational Exception'
  )
}

function formatDate(value: any) {
  if (!value) return '—'

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) return String(value)

  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function StatusPill({ value }: { value: any }) {
  const text = displayValue(value)
  const normalized = text.toLowerCase()

  const tone =
    /resolved|closed|completed|verified|success|executed|approved/.test(normalized)
      ? 'success'
      : /breach|high|critical|failed|rejected|mismatch|overdue/.test(normalized)
        ? 'danger'
        : /investigating|progress|pending|awaiting|medium|running|processing/.test(normalized)
          ? 'warning'
          : 'neutral'

  return (
    <span className={`op-status op-status-${tone}`}>
      {humanize(text)}
    </span>
  )
}

function Metric({
  label,
  value,
  detail
}: {
  label: string
  value: string | number
  detail?: string
}) {
  return (
    <div className="op-metric">
      <span className="op-metric-label">{label}</span>
      <strong>{value}</strong>
      {detail && <small>{detail}</small>}
    </div>
  )
}

function ExceptionPriority({ value }: { value: string }) {
  const severity = value.toUpperCase()

  const tone =
    /CRITICAL/.test(severity) ? 'critical' :
    /HIGH/.test(severity) ? 'high' :
    /MEDIUM/.test(severity) ? 'medium' : 'low'

  return (
    <span className={`exception-priority exception-priority-${tone}`}>
      <span />
      {humanize(severity)}
    </span>
  )
}

/* Recursively display structured objects and nested JSON. */
function StructuredData({ data }: { data: any }) {
  if (data === null || data === undefined || data === '') {
    return <div className="op-detail-text">—</div>
  }

  if (typeof data !== 'object') {
    return <div className="op-detail-text">{String(data)}</div>
  }

  if (Array.isArray(data)) {
    return (
      <div className="op-structured-list">
        {data.map((item, index) => (
          <div className="op-structured-item" key={index}>
            {typeof item === 'object' && item !== null
              ? <StructuredData data={item} />
              : String(item ?? '—')}
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="op-structured-grid">
      {Object.entries(data).map(([key, item]) => {
        const normalized = key.toLowerCase()

        const isStatus =
          /status|risk_level|priority|approval/.test(normalized)

        const isLongText =
          /reason|description|explanation|recommendation|solution|summary|finding|cause|message/.test(normalized)

        const isSla =
          /sla|tta|ttr|paused_minutes|elapsed_minutes/.test(normalized)

        const isNested =
          typeof item === 'object' && item !== null

        return (
          <div
            className={`op-structured-field ${
              isLongText || isNested ? 'op-structured-wide' : ''
            }`}
            key={key}
          >
            <span>{humanize(key)}</span>

            {isStatus ? (
              <StatusPill value={item} />
            ) : isNested ? (
              <StructuredData data={item} />
            ) : (
              <strong>
                {formatDetailValue(
                  isSla && typeof item === 'number'
                    ? `${key}_minutes`
                    : key,
                  item
                )}
              </strong>
            )}
          </div>
        )
      })}
    </div>
  )
}



function ReasoningDetails({ value }: { value: string }) {
  const labels = [
    'Exception type',
    'Investigation recommendation',
    'Investigation summary',
    'Possible cause',
    'Risk explanation',
    'Risk level',
    'Risk score',
    'Description',
    'Severity'
  ]

  const escapedLabels = labels.map(label =>
    label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  )

  const pattern = new RegExp(
    `(${escapedLabels.join('|')}):\\s*`,
    'gi'
  )

  const matches = Array.from(value.matchAll(pattern))

  if (!matches.length) {
    return <div className="op-detail-text">{value}</div>
  }

  const sections = matches.map((match, index) => {
    const start = (match.index ?? 0) + match[0].length
    const end = matches[index + 1]?.index ?? value.length

    return {
      label: match[1],
      value: value.slice(start, end).trim()
    }
  })

  return (
    <div className="op-reasoning-grid">
      {sections.map((section, index) => {
        const wide =
  /description|summary|recommendation|explanation|cause/i.test(section.label)

        const status =
          /severity|risk level/i.test(section.label)

        return (
          <div
            className={`op-reasoning-card ${
              wide ? 'op-reasoning-wide' : ''
            }`}
            key={`${section.label}-${index}`}
          >
            <span>{section.label}</span>

            {status ? (
              <StatusPill value={section.value} />
            ) : (
              <strong>{section.value}</strong>
            )}
          </div>
        )
      })}
    </div>
  )
}


function DetailValue({
  value,
  fieldKey
}: {
  value: any
  fieldKey: string
}) {
  const parsed = parseDetailValue(value)

  if (
    fieldKey.toLowerCase() === 'reasoning' &&
    typeof parsed.data === 'string'
  ) {
    return <ReasoningDetails value={parsed.data} />
  }

  if (!parsed.isStructured) {
    return (
      <div className="op-detail-text">
        {parsed.data}
      </div>
    )
  }

  return (
    <div className="op-structured-container">
      {parsed.prefix && (
        <div className="op-structured-heading">
          {parsed.prefix}
        </div>
      )}

      <StructuredData data={parsed.data} />
    </div>
  )
}


function OperationsPageContent({
  page,
  shipments = []
}: Props) {
  const config = PAGE_CONFIG[page]
  const Icon = config.icon

  const [datasets, setDatasets] = useState<
    { endpoint: string; rows: Row[]; error?: string }[]
  >([])

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [severityFilter, setSeverityFilter] = useState('ALL')
  const [typeFilter, setTypeFilter] = useState('ALL')
  const [selected, setSelected] = useState<Row | null>(null)
  const [actionBusy, setActionBusy] = useState(false)
  const [notice, setNotice] = useState('')

  const loadData = useCallback(async () => {
    setLoading(true)
    setError('')

    const token = getToken()

    const results = await Promise.all(
      config.endpoints.map(async endpoint => {
        try {
          const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            headers: token
              ? { Authorization: `Bearer ${token}` }
              : {}
          })

          if (!response.ok) {
            throw new Error(`${response.status} ${response.statusText}`)
          }

          const payload = await response.json()

          return {
            endpoint,
            rows: unwrapRows(payload)
          }
        } catch (err) {
          return {
            endpoint,
            rows: [],
            error: err instanceof Error ? err.message : 'Request failed'
          }
        }
      })
    )

    setDatasets(results)

    const failed = results.filter(item => item.error)

    if (failed.length === results.length) {
      setError(
        `Could not load this page. ${
          failed.map(item => `${item.endpoint}: ${item.error}`).join(' | ')
        }`
      )
    }

    setLoading(false)
  }, [config.endpoints])

  useEffect(() => {
    void loadData()
  }, [loadData])

  const allRows = useMemo(() => {
    return datasets.flatMap(dataset =>
      dataset.rows.map((row, index) => ({
        ...row,
        __source: dataset.endpoint,
        __rowKey: `${dataset.endpoint}-${findId(row)}-${index}`
      }))
    )
  }, [datasets])

  const exceptionStats = useMemo(() => {
    const isClosed = (row: Row) =>
      ['RESOLVED', 'CLOSED', 'COMPLETED', 'VERIFIED'].includes(getStatus(row))

    return {
      total: allRows.length,
      open: allRows.filter(row => !isClosed(row)).length,
      high: allRows.filter(row =>
        /HIGH|CRITICAL/.test(getSeverity(row))
      ).length,
      breached: allRows.filter(row =>
        /BREACHED/.test(String(row.sla_status ?? ''))
      ).length
    }
  }, [allRows])

  const exceptionTypes = useMemo(() => {
    return Array.from(new Set(
      allRows.map(row => getExceptionType(row))
    )).sort()
  }, [allRows])

  const statusOptions = useMemo(() => {
    return Array.from(new Set(
      allRows.map(row => getStatus(row))
    )).filter(status => status !== 'UNKNOWN').sort()
  }, [allRows])

  const filteredRows = useMemo(() => {
    return allRows.filter(row => {
      const searchable = Object.entries(row)
        .filter(([key]) => !key.startsWith('__'))
        .map(([, value]) =>
          typeof value === 'object'
            ? JSON.stringify(value)
            : String(value ?? '')
        )
        .join(' ')
        .toLowerCase()

      const matchesSearch = searchable.includes(search.toLowerCase())
      const matchesStatus =
        statusFilter === 'ALL' || getStatus(row) === statusFilter
      const matchesSeverity =
        severityFilter === 'ALL' || getSeverity(row) === severityFilter
      const matchesType =
        typeFilter === 'ALL' || getExceptionType(row) === typeFilter

      return matchesSearch && matchesStatus && matchesSeverity && matchesType
    })
  }, [allRows, search, statusFilter, severityFilter, typeFilter])

  const updateExceptionStatus = async (status: string) => {
    if (!selected?.exception_id) return

    setActionBusy(true)
    setNotice('')

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/exceptions/${selected.exception_id}/status`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(getToken()
              ? { Authorization: `Bearer ${getToken()}` }
              : {})
          },
          body: JSON.stringify({ status })
        }
      )

      const body = await response.json().catch(() => ({}))

      if (!response.ok) {
        throw new Error(
          body.detail || body.message || `Request failed (${response.status})`
        )
      }

      setNotice(
        `Exception #${selected.exception_id} updated to ${humanize(status)}.`
      )

      setSelected(current =>
        current ? { ...current, status } : null
      )

      await loadData()
    } catch (err) {
      setNotice(
        err instanceof Error
          ? err.message
          : 'Could not update exception status.'
      )
    } finally {
      setActionBusy(false)
    }
  }

  const verifyException = async () => {
    if (!selected?.exception_id) return

    setActionBusy(true)
    setNotice('')

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/resolution-verifications/exceptions/${selected.exception_id}/verify`,
        {
          method: 'POST',
          headers: getToken()
            ? { Authorization: `Bearer ${getToken()}` }
            : {}
        }
      )

      const body = await response.json().catch(() => ({}))

      if (!response.ok) {
        throw new Error(
          body.detail || body.message || `Verification failed (${response.status})`
        )
      }

      setNotice(
        body.message ||
        `Verification result: ${body.verification_status || 'completed'}.`
      )

      await loadData()

      setSelected(current =>
        current
          ? {
              ...current,
              ...body,
              status: body.exception_status || current.status
            }
          : null
      )
    } catch (err) {
      setNotice(
        err instanceof Error
          ? err.message
          : 'Could not verify this exception.'
      )
    } finally {
      setActionBusy(false)
    }
  }

  const preferredColumns =
    page === 'Investigations'
      ? ['investigation_id', 'shipment_id', 'exception_id', 'status', 'urgency', 'created_at']
      : page === 'Risk Monitoring'
        ? ['assessment_id', 'shipment_id', 'risk_score', 'risk_level', 'created_at']
        : page === 'AI Operations'
          ? ['workflow_id', 'run_id', 'workflow_name', 'agent_type', 'trigger_type', 'execution_status', 'created_at']
          : page === 'Resolution Plans'
            ? ['plan_id', 'exception_id', 'shipment_id', 'status', 'priority', 'created_at']
            : page === 'Actions & Approvals'
              ? ['action_id', 'exception_id', 'action_type', 'status', 'approval_status', 'created_at']
              : page === 'Audit Logs'
                ? ['audit_log_id', 'user_id', 'action', 'entity_type', 'entity_id', 'created_at']
                : []

  const columns = useMemo(() => {
    if (!filteredRows.length) return []

    const available = Array.from(new Set(
      filteredRows.flatMap(row =>
        Object.keys(row).filter(key => !key.startsWith('__'))
      )
    ))

    const preferred = preferredColumns.filter(key =>
      available.includes(key)
    )

    const remaining = available.filter(key =>
      !preferred.includes(key) &&
      !/^(sources|metadata|raw_payload|updated_at|__)/i.test(key)
    )

    return [...preferred, ...remaining].slice(0, 7)
  }, [filteredRows, preferredColumns])

  const isAnalytics = page === 'Analytics'
  const isExceptions = page === 'Exceptions'

  return (
    <main className={`operations-page ${isExceptions ? 'exceptions-page' : ''}`}>

      <div className="op-page-header">
        <div className="op-heading-icon">
          <Icon size={21} />
        </div>

        <div className="op-heading-copy">
          <div className="op-eyebrow">CARGOPILOT 360 / OPERATIONS</div>
          <h1>{page}</h1>
          <p>{config.description}</p>
        </div>

        <button
          className="op-refresh"
          onClick={() => void loadData()}
          disabled={loading}
        >
          <RefreshCw
            size={15}
            className={loading ? 'op-spin' : ''}
          />
          Refresh
        </button>
      </div>

      {notice && (
        <div className="op-notice" role="status">
          {notice}
        </div>
      )}

      {error && (
        <div className="op-error">
          <AlertTriangle size={16} />
          {error}
        </div>
      )}

      {isExceptions ? (
        <section className="exception-summary-grid">
          <Metric
            label="Total Exceptions"
            value={exceptionStats.total}
            detail="All recorded exceptions"
          />

          <Metric
            label="Open Exceptions"
            value={exceptionStats.open}
            detail="Require operational attention"
          />

          <Metric
            label="High Priority"
            value={exceptionStats.high}
            detail="High or critical severity"
          />

          <Metric
            label="SLA Breached"
            value={exceptionStats.breached}
            detail="Explicitly marked as breached"
          />
        </section>
      ) : isAnalytics ? (
        <section className="op-metrics-grid">
          {datasets.map(dataset =>
            dataset.rows.map((row, index) =>
              Object.entries(row)
                .filter(([key, value]) =>
                  typeof value === 'number' &&
                  !key.toLowerCase().includes('id')
                )
                .map(([key, value]) => (
                  <Metric
                    key={`${dataset.endpoint}-${key}-${index}`}
                    label={humanize(key)}
                    value={Number(value).toLocaleString()}
                  />
                ))
            )
          )}

          {!allRows.length && !loading && (
            <div className="op-empty">
              Analytics endpoints returned no KPI values.
            </div>
          )}
        </section>
      ) : (
        <section className="op-metrics-grid">
          <Metric label="Total records" value={allRows.length} />
          <Metric
            label="Active / pending"
            value={allRows.filter(row =>
              !['RESOLVED', 'CLOSED', 'COMPLETED', 'VERIFIED', 'EXECUTED'].includes(getStatus(row))
            ).length}
          />
          <Metric
            label="High priority"
            value={allRows.filter(row =>
              /HIGH|CRITICAL/.test(getSeverity(row))
            ).length}
          />
          <Metric
            label="SLA breached"
            value={allRows.filter(row =>
              /BREACHED/i.test(String(row.sla_status ?? ''))
            ).length}
          />
        </section>
      )}

      {isExceptions ? (
        <section className="exception-register">

          <div className="exception-register-header">
            <div>
              <span className="op-eyebrow">OPERATIONAL CONTROL</span>
              <h2>Exception Register</h2>
              <p>
                Review, prioritise and manage shipment exceptions.
              </p>
            </div>

            <span className="exception-record-count">
              {filteredRows.length} of {allRows.length} records
            </span>
          </div>

          <div className="exception-filter-bar">
            <label className="exception-search">
              <Search size={16} />
              <input
                value={search}
                onChange={event => setSearch(event.target.value)}
                placeholder="Search exceptions, shipments or containers..."
              />
            </label>

            <label className="exception-select">
              <Filter size={14} />
              <select
                value={statusFilter}
                onChange={event => setStatusFilter(event.target.value)}
              >
                <option value="ALL">All statuses</option>
                {statusOptions.map(status => (
                  <option key={status} value={status}>
                    {humanize(status)}
                  </option>
                ))}
              </select>
            </label>

            <label className="exception-select">
              <select
                value={severityFilter}
                onChange={event => setSeverityFilter(event.target.value)}
              >
                <option value="ALL">All priorities</option>
                {Array.from(new Set(allRows.map(getSeverity))).map(severity => (
                  <option key={severity} value={severity}>
                    {humanize(severity)}
                  </option>
                ))}
              </select>
            </label>

            <label className="exception-select exception-type-select">
              <select
                value={typeFilter}
                onChange={event => setTypeFilter(event.target.value)}
              >
                <option value="ALL">All exception types</option>
                {exceptionTypes.map(type => (
                  <option key={type} value={type}>
                    {humanize(type)}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {loading ? (
            <div className="op-loading">
              <span className="op-loader" />
              Loading exceptions...
            </div>
          ) : filteredRows.length ? (
            <div className="exception-list-wrap">
              <table className="exception-table">
                <thead>
                  <tr>
                    <th>Exception</th>
                    <th>Shipment</th>
                    <th>Priority</th>
                    <th>Status</th>
                    <th>SLA</th>
                    <th>Detected</th>
                    <th />
                  </tr>
                </thead>

                <tbody>
                  {filteredRows.map(row => (
                    <tr key={row.__rowKey}>
                      <td>
                        <div className="exception-name">
                          <strong>{humanize(getExceptionType(row))}</strong>
                          <span>EXC-{row.exception_id ?? findId(row)}</span>
                        </div>
                      </td>

                      <td>
                        <div className="exception-shipment">
                          <strong>
                            {shipmentLabel(row, shipments)}
                          </strong>
                          <span>
                            {row.container_no ||
                              shipments.find(item =>
                                item.shipment_id === Number(row.shipment_id)
                              )?.container_no ||
                              'Container not specified'}
                          </span>
                        </div>
                      </td>

                      <td>
                        <ExceptionPriority value={getSeverity(row)} />
                      </td>

                      <td>
                        <StatusPill value={getStatus(row)} />
                      </td>

                      <td>
                        <StatusPill
                          value={row.sla_status ?? 'Not specified'}
                        />
                      </td>

                      <td className="exception-date">
                        {formatDate(
                          row.detected_at ?? row.created_at ?? row.created_on
                        )}
                      </td>

                      <td>
                        <button
                          className="exception-view-button"
                          onClick={() => {
                            setSelected(row)
                            setNotice('')
                          }}
                        >
                          Review
                          <ArrowUpRight size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="op-empty exception-empty">
              <div className="op-empty-mark">
                <CheckCircle2 size={23} />
              </div>
              <strong>{config.empty}</strong>
              <span>
                {search || statusFilter !== 'ALL' ||
                severityFilter !== 'ALL' || typeFilter !== 'ALL'
                  ? 'Try changing your filters or search terms.'
                  : 'New operational exceptions will appear here.'}
              </span>
            </div>
          )}
        </section>
      ) : (
        <section className="op-data-panel">
          <div className="op-toolbar">
            <div>
              <h2>{page} register</h2>
              <p>{filteredRows.length} records displayed</p>
            </div>

            <div className="op-controls">
              <label className="op-search">
                <Search size={15} />
                <input
                  value={search}
                  onChange={event => setSearch(event.target.value)}
                  placeholder="Search records..."
                />
              </label>

              <label className="op-filter">
                <Filter size={14} />
                <select
                  value={statusFilter}
                  onChange={event => setStatusFilter(event.target.value)}
                >
                  <option value="ALL">All statuses</option>
                  {statusOptions.map(status => (
                    <option key={status} value={status}>
                      {humanize(status)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>

          {loading ? (
            <div className="op-loading">
              <span className="op-loader" />
              Loading {page.toLowerCase()}...
            </div>
          ) : filteredRows.length ? (
            <div className="op-table-wrap">
              <table className="op-table">
                <thead>
                  <tr>
                    {columns.map(column => (
                      <th key={column}>{humanize(column)}</th>
                    ))}
                    <th>Details</th>
                  </tr>
                </thead>

                <tbody>
                  {filteredRows.map(row => (
                    <tr key={row.__rowKey}>
                      {columns.map(column => (
                        <td key={column}>
                          {column.toLowerCase().includes('status') ||
                          column === 'severity' ||
                          column.includes('risk_level')
                            ? <StatusPill value={row[column]} />
                            : column === 'shipment_id'
                              ? shipmentLabel(row, shipments)
                              : displayValue(row[column])}
                        </td>
                      ))}

                      <td>
                        <button
                          className="op-view-button"
                          onClick={() => {
                            setSelected(row)
                            setNotice('')
                          }}
                        >
                          View details
                          <ArrowUpRight size={13} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="op-empty">
              <div className="op-empty-mark">
                <Icon size={23} />
              </div>
              <strong>{config.empty}</strong>
              <span>Try adjusting your search or filters.</span>
            </div>
          )}
        </section>
      )}

      {/* DETAILS DRAWER */}
      {selected && (
        <div
          className="op-modal-backdrop exception-backdrop"
          onMouseDown={event => {
            if (event.target === event.currentTarget) {
              setSelected(null)
            }
          }}
        >
          <aside
            className="op-detail-modal exception-drawer"
            role="dialog"
            aria-modal="true"
            aria-label={`${page} record details`}
          >
            <header className="op-modal-header">
              <div>
                <span className="op-eyebrow">
                  {page.toUpperCase()} / RECORD DETAILS
                </span>

                <h2>
                  {page === 'Exceptions'
                    ? humanize(getExceptionType(selected))
                    : `${page} #${findId(selected)}`}
                </h2>

                <p>
                  Record #{findId(selected)}
                  {selected.shipment_id
                    ? ` · ${shipmentLabel(selected, shipments)}`
                    : ''}
                </p>
              </div>

              <button
                className="op-icon-button"
                onClick={() => setSelected(null)}
                aria-label="Close details"
              >
                <X size={18} />
              </button>
            </header>

            <div className="op-detail-content">
              {page === 'Exceptions' && (
                <div className="exception-drawer-summary">
                  <div>
                    <span>Priority</span>
                    <ExceptionPriority value={getSeverity(selected)} />
                  </div>

                  <div>
                    <span>Current status</span>
                    <StatusPill value={getStatus(selected)} />
                  </div>
                </div>
              )}

              <h3 className="exception-section-title">
                Record information
              </h3>

              <div className="op-detail-grid">
                {Object.entries(selected)
                  .filter(([key]) => !key.startsWith('__'))
                  .map(([key, value]) => {
                    const normalized = key.toLowerCase()

                    const isTechnical =
                      /payload|metadata|evidence|response|request|source|context/.test(normalized)

                    const isLongText =
                      /reason|description|explanation|recommendation|solution|summary|finding|cause/.test(normalized)

                    const isSla =
                      /sla|tta|ttr|paused_minutes|elapsed_minutes/.test(normalized)

                    return (
                      <div
                        className={`op-detail-field ${
                          isTechnical ? 'op-detail-technical' : ''
                        } ${
                          isLongText || isSla ? 'op-detail-wide' : ''
                        }`}
                        key={key}
                      >
                        <span>{humanize(key)}</span>
                        <DetailValue value={value} fieldKey={key} />
                      </div>
                    )
                  })}
              </div>

              {page === 'Exceptions' && (
                <div className="op-exception-actions">
                  <h3>Exception actions</h3>

                  <p>
                    Update the exception lifecycle or run a supported
                    resolution verification. Resolved and closed
                    exceptions cannot be reopened.
                  </p>

                  <label className="exception-action-label">
                    Update status
                  </label>

                  <select
                    className="exception-status-select"
                    aria-label="Update exception status"
                    value={String(selected.status || 'OPEN').toUpperCase()}
                    disabled={
                      actionBusy ||
                      ['RESOLVED', 'CLOSED'].includes(
                        String(selected.status).toUpperCase()
                      )
                    }
                    onChange={event =>
                      void updateExceptionStatus(event.target.value)
                    }
                  >
                    {[
                      'OPEN',
                      'INVESTIGATING',
                      'AWAITING_APPROVAL',
                      'IN_PROGRESS',
                      'AWAITING_RESPONSE',
                      'PENDING_3RD_PARTY',
                      'CLOSED'
                    ].map(status => (
                      <option key={status} value={status}>
                        {humanize(status)}
                      </option>
                    ))}
                  </select>

                  {selected.eligible_for_verification === true &&
                    !['RESOLVED', 'CLOSED'].includes(
                      String(selected.status).toUpperCase()
                    ) && (
                      <button
                        className="op-primary-action exception-verify-button"
                        onClick={() => void verifyException()}
                        disabled={actionBusy}
                      >
                        {actionBusy
                          ? 'Processing...'
                          : 'Verify resolution'}
                      </button>
                    )}
                </div>
              )}
            </div>
          </aside>
        </div>
      )}
    </main>
  )
}


export default function OperationsPage(props: Props) {
  if (props.page === 'AI Operations') return <AIOperationsPage />
  return <OperationsPageContent {...props} />
}
