
import { useEffect, useMemo, useState } from 'react'
import {
  Activity,
  Anchor,
  ArrowUpRight,
  Bell,
  Box,
  CheckCircle2,
  ChevronDown,
  ClipboardList,
  FileText,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  Package,
  RefreshCw,
  Search,
  Settings,
  ShieldAlert,
  Sun,
  Truck,
  Users,
  X,
  Zap,
} from 'lucide-react'
import LoginPage from './LoginPage'
import DocumentsPage from './DocumentsPage'
import ActionControlPage from './ActionControlPage'
import OperationsPage from './OperationsPage'
import './App.css'

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

interface User {
  user_id: number
  name: string
  email: string
  role: 'ADMIN' | 'MANAGER' | 'OFFICER' | string
  is_active: boolean
}

interface DashboardOverview {
  total_shipments: number
  active_shipments: number
  high_risk_shipments: number
  open_exceptions: number
  resolved_exceptions: number
  avg_resolution_minutes: number
}

interface AutomationKPIs {
  total_actions: number
  auto_executed: number
  human_approved: number
  rejected: number
  automation_rate_pct: number
}

interface ExceptionStatistic {
  exception_type: string
  status: string
  total: number
}

interface Shipment {
  shipment_id: number
  shipment_ref: string
  origin: string
  destination: string
  shipper: string
  consignee: string
  container_no: string
  container_type: string
  expected_arrival: string | null
  actual_arrival: string | null
  status: string
  current_risk_score: number
  current_risk_level: string
}

type OperationsPageName =
  | 'Exceptions'
  | 'Investigations'
  | 'Risk Monitoring'
  | 'AI Operations'
  | 'Resolution Plans'
  | 'Actions & Approvals'
  | 'Analytics'
  | 'Audit Logs'

const operationsPages: OperationsPageName[] = [
  'Exceptions',
  'Investigations',
  'Risk Monitoring',
  'AI Operations',
  'Resolution Plans',
  'Actions & Approvals',
  'Analytics',
  'Audit Logs',
]

const navigation = [
  { label: 'Overview', icon: LayoutDashboard, section: 'MAIN' },
  { label: 'Shipments', icon: Package, section: 'MAIN' },
  { label: 'Documents', icon: FileText, section: 'MAIN' },
  { label: 'Exceptions', icon: ShieldAlert, section: 'OPERATIONS' },
  { label: 'Investigations', icon: ClipboardList, section: 'OPERATIONS' },
  { label: 'Risk Monitoring', icon: Activity, section: 'OPERATIONS' },
  { label: 'AI Operations', icon: Zap, section: 'INTELLIGENCE' },
  { label: 'Resolution Plans', icon: CheckCircle2, section: 'INTELLIGENCE' },
  { label: 'Actions & Approvals', icon: Users, section: 'INTELLIGENCE' },
  { label: 'Analytics', icon: Truck, section: 'MANAGEMENT' },
  { label: 'Audit Logs', icon: ClipboardList, section: 'MANAGEMENT' },
]

function getInitials(name: string) {
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map(part => part[0])
    .join('')
    .toUpperCase()
}

function formatResolutionTime(minutes: number) {
  if (!Number.isFinite(minutes) || minutes < 0) return '—'

  const hours = Math.floor(minutes / 60)
  const remainingMinutes = Math.round(minutes % 60)

  if (hours >= 24) {
    const days = Math.floor(hours / 24)
    const remainingHours = hours % 24
    return `${days}d ${remainingHours}h`
  }

  return `${hours}h ${remainingMinutes}m`
}

function formatShipmentDate(date: string | null) {
  if (!date) return 'Not available'

  const parsedDate = new Date(date)

  if (Number.isNaN(parsedDate.getTime())) return 'Not available'

  return parsedDate.toLocaleDateString('en-US', {
    month: 'short',
    day: '2-digit',
    year: 'numeric',
  })
}

function formatLabel(value: string) {
  return value
    .toLowerCase()
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

function getStatusClass(status: string) {
  return status.toLowerCase().replace(/_/g, '-')
}

function getRiskClass(risk: string) {
  return risk.toLowerCase()
}

function App() {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const saved = localStorage.getItem('cargopilot-theme')
    return saved === 'dark' ? 'dark' : 'light'
  })

  const [activePage, setActivePage] = useState('Overview')
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const [currentUser, setCurrentUser] = useState<User | null>(null)
  const [isCheckingAuth, setIsCheckingAuth] = useState(true)
  const [isLoggingIn, setIsLoggingIn] = useState(false)

  const [dashboardOverview, setDashboardOverview] =
    useState<DashboardOverview | null>(null)

  const [automationKPIs, setAutomationKPIs] =
    useState<AutomationKPIs | null>(null)

  const [exceptionStatistics, setExceptionStatistics] =
    useState<ExceptionStatistic[]>([])

  const [shipments, setShipments] = useState<Shipment[]>([])
  const [isShipmentsLoading, setIsShipmentsLoading] = useState(false)
  const [shipmentsError, setShipmentsError] = useState('')

  const [isDashboardLoading, setIsDashboardLoading] = useState(false)
  const [dashboardError, setDashboardError] = useState('')

  const [shipmentSearch, setShipmentSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [riskFilter, setRiskFilter] = useState('ALL')
  const [selectedShipment, setSelectedShipment] =
    useState<Shipment | null>(null)
  const [isSupervisorRunning, setIsSupervisorRunning] = useState(false)
  const [supervisorFeedback, setSupervisorFeedback] = useState<{
    tone: 'success' | 'error'
    message: string
  } | null>(null)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('cargopilot-theme', theme)
  }, [theme])

  // Restore login session.
  useEffect(() => {
    let cancelled = false

    const restoreSession = async () => {
      const token = sessionStorage.getItem('cargopilot-token')

      if (!token) {
        if (!cancelled) setIsCheckingAuth(false)
        return
      }

      try {
        const response = await fetch(`${API_BASE_URL}/auth/me`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        })

        if (!response.ok) {
          sessionStorage.removeItem('cargopilot-token')
          if (!cancelled) setCurrentUser(null)
          return
        }

        const user: User = await response.json()

        if (!cancelled) {
          setCurrentUser(user)
        }
      } catch {
        sessionStorage.removeItem('cargopilot-token')
        if (!cancelled) setCurrentUser(null)
      } finally {
        if (!cancelled) setIsCheckingAuth(false)
      }
    }

    restoreSession()

    return () => {
      cancelled = true
    }
  }, [])

  // Fetch dashboard and shipment data.
  useEffect(() => {
    if (!currentUser) return

    let cancelled = false

    const fetchDashboardData = async () => {
      const token = sessionStorage.getItem('cargopilot-token')
      if (!token) return

      const headers = {
        Authorization: `Bearer ${token}`,
      }

      setIsDashboardLoading(true)
      setIsShipmentsLoading(true)
      setDashboardError('')
      setShipmentsError('')

      try {
        const [
          overviewResponse,
          automationResponse,
          exceptionsResponse,
        ] = await Promise.all([
          fetch(`${API_BASE_URL}/api/dashboard/overview`, { headers }),
          fetch(`${API_BASE_URL}/api/dashboard/automation`, { headers }),
          fetch(`${API_BASE_URL}/api/dashboard/exception-stats`, { headers }),
        ])

        if (
          !overviewResponse.ok ||
          !automationResponse.ok ||
          !exceptionsResponse.ok
        ) {
          throw new Error(
            'Unable to load dashboard data. Please check your access and backend connection.',
          )
        }

        const overviewData = await overviewResponse.json()
        const automationData = await automationResponse.json()
        const exceptionsData = await exceptionsResponse.json()

        const overview = Array.isArray(overviewData)
          ? overviewData[0] ?? null
          : overviewData

        const automation = Array.isArray(automationData)
          ? automationData[0] ?? null
          : automationData

        if (!Array.isArray(exceptionsData)) {
          throw new Error(
            'The exception statistics response has an unexpected format.',
          )
        }

        if (!cancelled) {
          setDashboardOverview(overview)
          setAutomationKPIs(automation)
          setExceptionStatistics(exceptionsData)
        }
      } catch (error) {
        if (!cancelled) {
          setDashboardError(
            error instanceof Error
              ? error.message
              : 'Something went wrong while loading dashboard data.',
          )
        }
      } finally {
        if (!cancelled) {
          setIsDashboardLoading(false)
        }
      }

      try {
        const shipmentsResponse = await fetch(
          `${API_BASE_URL}/api/shipments/`,
          { headers },
        )

        if (!shipmentsResponse.ok) {
          throw new Error('Unable to load shipments.')
        }

        const shipmentsData = await shipmentsResponse.json()

        if (!Array.isArray(shipmentsData)) {
          throw new Error(
            'The shipments response has an unexpected format.',
          )
        }

        if (!cancelled) {
          setShipments(shipmentsData)
        }
      } catch (error) {
        if (!cancelled) {
          setShipmentsError(
            error instanceof Error
              ? error.message
              : 'Something went wrong while loading shipments.',
          )
        }
      } finally {
        if (!cancelled) {
          setIsShipmentsLoading(false)
        }
      }
    }

    fetchDashboardData()

    const refreshInterval = window.setInterval(
      fetchDashboardData,
      60000,
    )

    return () => {
      cancelled = true
      window.clearInterval(refreshInterval)
    }
  }, [currentUser])

  const toggleTheme = () => {
    setTheme(current => current === 'light' ? 'dark' : 'light')
  }

  const handleLogin = async (email: string, password: string) => {
    setIsLoggingIn(true)

    try {
      const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
          username: email,
          password: password,
        }),
      })

      const result = await response.json()

      if (!response.ok) {
        throw new Error(
          result.detail || 'Unable to sign in. Please check your credentials.',
        )
      }

      const token = result.access_token

      if (!token) {
        throw new Error('The server did not return an access token.')
      }

      sessionStorage.setItem('cargopilot-token', token)

      const userResponse = await fetch(`${API_BASE_URL}/auth/me`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })

      if (!userResponse.ok) {
        sessionStorage.removeItem('cargopilot-token')
        throw new Error('Unable to verify your account. Please sign in again.')
      }

      const user: User = await userResponse.json()

      setCurrentUser(user)
      setActivePage('Overview')
    } catch (error) {
      if (error instanceof TypeError) {
        throw new Error(
          'Cannot connect to the server. Check that the CargoPilot backend is running.',
        )
      }

      throw error
    } finally {
      setIsLoggingIn(false)
    }
  }

  const handleLogout = () => {
    sessionStorage.removeItem('cargopilot-token')
    setCurrentUser(null)
    setDashboardOverview(null)
    setAutomationKPIs(null)
    setExceptionStatistics([])
    setShipments([])
    setSelectedShipment(null)
    setActivePage('Overview')
    setSidebarOpen(false)
  }

  const selectPage = (page: string) => {
    setActivePage(page)
    setSidebarOpen(false)

    if (page !== 'Shipments') {
      setSelectedShipment(null)
    }
  }

  const refreshShipments = async () => {
    const token = sessionStorage.getItem('cargopilot-token')
    if (!token) return

    setIsShipmentsLoading(true)
    setShipmentsError('')

    try {
      const response = await fetch(`${API_BASE_URL}/api/shipments/`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })

      if (!response.ok) {
        throw new Error('Unable to refresh shipments.')
      }

      const data = await response.json()

      if (!Array.isArray(data)) {
        throw new Error('Unexpected shipment response format.')
      }

      setShipments(data)
      setSelectedShipment(null)
    } catch (error) {
      setShipmentsError(
        error instanceof Error ? error.message : 'Shipment refresh failed.',
      )
    } finally {
      setIsShipmentsLoading(false)
    }
  }

  const runShipmentSupervisor = async () => {
    if (!selectedShipment || !currentUser || !['ADMIN', 'MANAGER'].includes(currentUser.role)) {
      return
    }

    const token = sessionStorage.getItem('cargopilot-token')
    if (!token) {
      setSupervisorFeedback({
        tone: 'error',
        message: 'Your session has expired. Sign in again before starting a workflow.',
      })
      return
    }

    setIsSupervisorRunning(true)
    setSupervisorFeedback(null)

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/supervisor/shipments/${selectedShipment.shipment_id}/run`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
      )
      const body = await response.json().catch(() => ({}))

      if (!response.ok) {
        throw new Error(body.detail || 'Could not start the shipment supervisor.')
      }

      const status = formatLabel(String(body.workflow_status || 'RUNNING'))
      setSupervisorFeedback({
        tone: body.success === false ? 'error' : 'success',
        message: `${body.message || 'Supervisor workflow started.'} Workflow #${body.workflow_id} · ${status}.`,
      })
    } catch (error) {
      setSupervisorFeedback({
        tone: 'error',
        message: error instanceof Error ? error.message : 'Supervisor execution failed.',
      })
    } finally {
      setIsSupervisorRunning(false)
    }
  }

  const filteredShipments = useMemo(() => {
    const query = shipmentSearch.trim().toLowerCase()

    return shipments.filter(shipment => {
      const matchesSearch =
        !query ||
        [
          shipment.shipment_ref,
          shipment.container_no,
          shipment.shipper,
          shipment.consignee,
          shipment.origin,
          shipment.destination,
        ].some(value => value?.toLowerCase().includes(query))

      const matchesStatus =
        statusFilter === 'ALL' || shipment.status === statusFilter

      const matchesRisk =
        riskFilter === 'ALL' ||
        shipment.current_risk_level === riskFilter

      return matchesSearch && matchesStatus && matchesRisk
    })
  }, [shipments, shipmentSearch, statusFilter, riskFilter])

  if (isCheckingAuth) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'grid',
          placeItems: 'center',
          background: 'var(--bg-primary)',
          color: 'var(--text-primary)',
          fontSize: '14px',
        }}
      >
        Loading CargoPilot 360...
      </div>
    )
  }

  if (!currentUser) {
    return (
      <LoginPage
        onLogin={handleLogin}
        theme={theme}
        onToggleTheme={toggleTheme}
      />
    )
  }

  const initials = getInitials(currentUser.name)

  const metrics = [
    {
      title: 'Total Shipments',
      value: dashboardOverview?.total_shipments ?? '—',
      icon: Package,
      description: 'All registered shipments',
    },
    {
      title: 'Active Shipments',
      value: dashboardOverview?.active_shipments ?? '—',
      icon: Truck,
      description: 'Currently active',
    },
    {
      title: 'Open Exceptions',
      value: dashboardOverview?.open_exceptions ?? '—',
      icon: ShieldAlert,
      description: 'Require operational attention',
    },
    {
      title: 'High Risk Shipments',
      value: dashboardOverview?.high_risk_shipments ?? '—',
      icon: Activity,
      description: 'Currently classified as high risk',
    },
  ]

  const automationMetrics = [
    {
      title: 'Total Actions',
      value: automationKPIs?.total_actions ?? '—',
    },
    {
      title: 'Auto Executed',
      value: automationKPIs?.auto_executed ?? '—',
    },
    {
      title: 'Human Approved',
      value: automationKPIs?.human_approved ?? '—',
    },
    {
      title: 'Rejected',
      value: automationKPIs?.rejected ?? '—',
    },
  ]

  const shipmentCounts = {
    total: shipments.length,
    active: shipments.filter(
      shipment => !['DELIVERED', 'CANCELLED'].includes(shipment.status),
    ).length,
    highRisk: shipments.filter(
      shipment => shipment.current_risk_level === 'HIGH',
    ).length,
    delivered: shipments.filter(
      shipment => shipment.status === 'DELIVERED',
    ).length,
  }

  return (
    <div className="app-shell">
      {sidebarOpen && (
        <button
          className="sidebar-overlay"
          aria-label="Close navigation"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside className={`sidebar ${sidebarOpen ? 'sidebar-open' : ''}`}>
        <div className="brand">
          <div className="brand-icon">
            <Anchor size={23} />
          </div>

          <div className="brand-copy">
            <span className="brand-name">
              CargoPilot<span>360</span>
            </span>
            <span className="brand-caption">LOGISTICS INTELLIGENCE</span>
          </div>

          <button
            className="mobile-close"
            onClick={() => setSidebarOpen(false)}
            aria-label="Close menu"
          >
            <X size={20} />
          </button>
        </div>

        <div className="workspace">
          <div className="workspace-icon">
            <Box size={18} />
          </div>
          <div className="workspace-copy">
            <span>Workspace</span>
            <strong>Demo Logistics Co.</strong>
          </div>
          <ChevronDown size={15} />
        </div>

        <nav className="sidebar-navigation">
          {['MAIN', 'OPERATIONS', 'INTELLIGENCE', 'MANAGEMENT'].map(section => (
            <div className="nav-section" key={section}>
              <p className="nav-heading">{section}</p>

              {navigation
                .filter(item => item.section === section)
                .map(item => {
                  const Icon = item.icon

                  return (
                    <button
                      key={item.label}
                      className={`nav-item ${
                        activePage === item.label ? 'active' : ''
                      }`}
                      onClick={() => selectPage(item.label)}
                    >
                      <Icon size={18} strokeWidth={1.8} />
                      <span>{item.label}</span>

                      {item.label === 'Exceptions' &&
                        dashboardOverview && (
                          <span className="nav-count">
                            {dashboardOverview.open_exceptions}
                          </span>
                        )}
                    </button>
                  )
                })}
            </div>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <button
            className={`nav-item ${activePage === 'Settings' ? 'active' : ''}`}
            onClick={() => selectPage('Settings')}
          >
            <Settings size={18} />
            <span>Settings</span>
          </button>

          <div className="user-profile">
            <div className="avatar">{initials}</div>

            <div className="user-details">
              <strong>{currentUser.name}</strong>
              <span>{currentUser.role}</span>
            </div>

            <button
              className="icon-button"
              onClick={handleLogout}
              aria-label="Sign out"
              title="Sign out"
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="icon-button mobile-menu"
              onClick={() => setSidebarOpen(true)}
              aria-label="Open navigation"
            >
              <Menu size={21} />
            </button>

            <div className="breadcrumb">
              <span>Workspace</span>
              <span className="breadcrumb-separator">/</span>
              <strong>{activePage}</strong>
            </div>
          </div>

          <div className="topbar-actions">
            <label className="search-box">
              <Search size={17} />
              <input placeholder="Search anything..." />
              <kbd>⌘ K</kbd>
            </label>

            <button
              className="icon-button theme-button"
              onClick={toggleTheme}
              aria-label="Toggle colour theme"
              title="Toggle theme"
            >
              {theme === 'light' ? <Moon size={19} /> : <Sun size={19} />}
            </button>

            <button
              className="icon-button notification-button"
              aria-label="Notifications"
            >
              <Bell size={19} />
              <span />
            </button>

            <div className="topbar-avatar">{initials}</div>
          </div>
        </header>

        <div className="page-content">
          {/* OVERVIEW */}
          {activePage === 'Overview' && (
            <>
              <section className="page-heading">
                <div>
                  <div className="eyebrow">
                    <span className="live-dot" />
                    LIVE OPERATIONS OVERVIEW
                  </div>

                  <h1>Welcome, {currentUser.name}</h1>

                  <p>
                    Here's what's happening across your logistics operations
                    today.
                  </p>
                </div>

                <button
                  className="primary-button"
                  onClick={() => selectPage('AI Operations')}
                >
                  <Zap size={16} /> AI Operations
                </button>
              </section>

              {dashboardError && (
                <div className="login-error" role="alert">
                  {dashboardError}
                </div>
              )}

              {isDashboardLoading && !dashboardOverview && (
                <p>Loading live dashboard data...</p>
              )}

              <section className="metric-grid">
                {metrics.map(metric => {
                  const Icon = metric.icon

                  return (
                    <article className="metric-card" key={metric.title}>
                      <div className="metric-top">
                        <span>{metric.title}</span>
                        <div className="metric-icon">
                          <Icon size={19} />
                        </div>
                      </div>

                      <div className="metric-value">{metric.value}</div>

                      <div className="metric-footer">
                        <span className="metric-change">Live data</span>
                        <span>{metric.description}</span>
                      </div>
                    </article>
                  )
                })}
              </section>

              <section className="panel" style={{ marginBottom: '24px' }}>
                <div className="panel-heading">
                  <div>
                    <h2>Automation Performance</h2>
                    <p>Live action execution statistics</p>
                  </div>

                  <div className="ai-icon">
                    <Zap size={18} />
                  </div>
                </div>

                <div className="metric-grid">
                  {automationMetrics.map(metric => (
                    <article className="metric-card" key={metric.title}>
                      <div className="metric-top">
                        <span>{metric.title}</span>
                      </div>
                      <div className="metric-value">{metric.value}</div>
                    </article>
                  ))}
                </div>

                <div className="ai-stat-row" style={{ marginTop: '20px' }}>
                  <span>Automation Rate</span>
                  <strong>
                    {automationKPIs
                      ? `${automationKPIs.automation_rate_pct}%`
                      : '—'}
                  </strong>
                </div>
              </section>

              <section className="dashboard-grid">
                <article className="panel shipment-panel">
                  <div className="panel-heading">
                    <div>
                      <h2>Recent Shipments</h2>
                      <p>
                        {shipments.length} shipments retrieved from your
                        operations database
                      </p>
                    </div>

                    <button
                      className="text-button"
                      onClick={() => selectPage('Shipments')}
                    >
                      View all <ArrowUpRight size={15} />
                    </button>
                  </div>

                  {shipmentsError && (
                    <div className="login-error" role="alert">
                      {shipmentsError}
                    </div>
                  )}

                  <div className="table-container">
                    <table className="shipment-table">
                      <thead>
                        <tr>
                          <th>SHIPMENT ID</th>
                          <th>ROUTE</th>
                          <th>STATUS</th>
                          <th>RISK</th>
                          <th>ETA</th>
                        </tr>
                      </thead>

                      <tbody>
                        {shipments.length > 0 ? (
                          shipments.map(shipment => (
                            <tr key={shipment.shipment_id}>
                              <td className="shipment-id">
                                {shipment.shipment_ref}
                              </td>

                              <td>
                                {shipment.origin.replace(/, Sri Lanka$/, '')}
                                {' → '}
                                {shipment.destination.replace(
                                  /, Sri Lanka$/,
                                  '',
                                )}
                              </td>

                              <td>
                                <span
                                  className={`status status-${getStatusClass(
                                    shipment.status,
                                  )}`}
                                >
                                  {formatLabel(shipment.status)}
                                </span>
                              </td>

                              <td>
                                <span
                                  className={`risk risk-${getRiskClass(
                                    shipment.current_risk_level,
                                  )}`}
                                >
                                  {formatLabel(shipment.current_risk_level)}
                                </span>
                              </td>

                              <td>
                                {formatShipmentDate(
                                  shipment.expected_arrival,
                                )}
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan={5}>
                              {isShipmentsLoading
                                ? 'Loading shipments...'
                                : 'No shipments available.'}
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>

                  <div className="ai-stat-row" style={{ marginTop: '14px' }}>
                    <span>Shipment data</span>
                    <strong>
                      {isShipmentsLoading ? 'Refreshing...' : 'Live'}
                    </strong>
                  </div>
                </article>

                <article className="panel intelligence-panel">
                  <div className="panel-heading">
                    <div>
                      <h2>AI Intelligence</h2>
                      <p>Automated operations summary</p>
                    </div>
                    <div className="ai-icon">
                      <Zap size={18} />
                    </div>
                  </div>

                  <div className="ai-status">
                    <span className="live-dot" />
                    AI ENGINE STATUS
                    <strong>Operational</strong>
                  </div>

                  <div className="ai-highlight">
                    <div className="highlight-icon">
                      <ShieldAlert size={20} />
                    </div>
                    <div>
                      <strong>Attention required</strong>
                      <p>
                        {dashboardOverview
                          ? `${dashboardOverview.open_exceptions} open exceptions require attention.`
                          : 'Loading operational status...'}
                      </p>
                    </div>
                  </div>

                  <div className="ai-stat-row">
                    <span>Open exceptions</span>
                    <strong>
                      {dashboardOverview?.open_exceptions ?? '—'}
                    </strong>
                  </div>

                  <div className="ai-stat-row">
                    <span>Resolved exceptions</span>
                    <strong>
                      {dashboardOverview?.resolved_exceptions ?? '—'}
                    </strong>
                  </div>

                  <div className="ai-stat-row">
                    <span>Average resolution time</span>
                    <strong>
                      {dashboardOverview
                        ? formatResolutionTime(
                            dashboardOverview.avg_resolution_minutes,
                          )
                        : '—'}
                    </strong>
                  </div>

                  <button
                    className="ai-button"
                    onClick={() => selectPage('AI Operations')}
                  >
                    Explore AI Operations <ArrowUpRight size={16} />
                  </button>
                </article>
              </section>

              <section className="panel" style={{ marginTop: '24px' }}>
                <div className="panel-heading">
                  <div>
                    <h2>Exception Breakdown</h2>
                    <p>Exceptions grouped by type and current status</p>
                  </div>

                  <button
                    className="text-button"
                    onClick={() => selectPage('Exceptions')}
                  >
                    View all <ArrowUpRight size={15} />
                  </button>
                </div>

                {exceptionStatistics.length === 0 ? (
                  <p>
                    {isDashboardLoading
                      ? 'Loading exception statistics...'
                      : 'No exception statistics available.'}
                  </p>
                ) : (
                  <div className="table-container">
                    <table className="shipment-table">
                      <thead>
                        <tr>
                          <th>EXCEPTION TYPE</th>
                          <th>STATUS</th>
                          <th>COUNT</th>
                        </tr>
                      </thead>

                      <tbody>
                        {exceptionStatistics.map((exception, index) => (
                          <tr
                            key={`${exception.exception_type}-${exception.status}-${index}`}
                          >
                            <td>
                              {exception.exception_type.replace(/_/g, ' ')}
                            </td>
                            <td>
                              <span className="status">
                                {exception.status.replace(/_/g, ' ')}
                              </span>
                            </td>
                            <td className="shipment-id">
                              {exception.total}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              <footer className="dashboard-footer">
                <span>
                  <span className="footer-dot" /> CargoPilot 360
                </span>
                <span>Logistics intelligence. Connected operations.</span>
              </footer>
            </>
          )}

          {/* SHIPMENTS WORKSPACE */}
          {activePage === 'Shipments' && (
            <>
              <section className="page-heading">
                <div>
                  <div className="eyebrow">
                    <Package size={13} />
                    LOGISTICS MANAGEMENT
                  </div>

                  <h1>Shipments</h1>

                  <p>
                    Monitor, search and manage your registered shipments.
                  </p>
                </div>

                <button
                  className="refresh-data-button"
                  onClick={refreshShipments}
                  disabled={isShipmentsLoading}
                >
                  <RefreshCw
                    size={16}
                    className={isShipmentsLoading ? 'refresh-spinning' : ''}
                  />
                  {isShipmentsLoading ? 'Refreshing...' : 'Refresh Data'}
                </button>
              </section>

              {shipmentsError && (
                <div className="login-error" role="alert">
                  {shipmentsError}
                </div>
              )}

              <section className="shipment-summary-grid">
                <article className="shipment-summary-card">
                  <div className="shipment-summary-icon">
                    <Package size={19} />
                  </div>
                  <div>
                    <span>Total shipments</span>
                    <strong>{shipmentCounts.total}</strong>
                  </div>
                </article>

                <article className="shipment-summary-card">
                  <div className="shipment-summary-icon">
                    <Truck size={19} />
                  </div>
                  <div>
                    <span>Active shipments</span>
                    <strong>{shipmentCounts.active}</strong>
                  </div>
                </article>

                <article className="shipment-summary-card">
                  <div className="shipment-summary-icon">
                    <ShieldAlert size={19} />
                  </div>
                  <div>
                    <span>High risk</span>
                    <strong>{shipmentCounts.highRisk}</strong>
                  </div>
                </article>

                <article className="shipment-summary-card">
                  <div className="shipment-summary-icon">
                    <CheckCircle2 size={19} />
                  </div>
                  <div>
                    <span>Delivered</span>
                    <strong>{shipmentCounts.delivered}</strong>
                  </div>
                </article>
              </section>

              <section className="panel shipment-management-panel">
                <div className="shipment-toolbar">
                  <div className="shipment-toolbar-title">
                    <div>
                      <h2>All Shipments</h2>
                      <p>
                        Showing {filteredShipments.length} of {shipments.length}{' '}
                        shipments
                      </p>
                    </div>
                  </div>

                  <div className="shipment-filters">
                    <label className="shipment-search">
                      <Search size={17} />
                      <input
                        type="search"
                        value={shipmentSearch}
                        onChange={event =>
                          setShipmentSearch(event.target.value)
                        }
                        placeholder="Search shipments..."
                      />
                    </label>

                    <label className="shipment-filter">
                      <span>Status</span>
                      <select
                        value={statusFilter}
                        onChange={event =>
                          setStatusFilter(event.target.value)
                        }
                      >
                        <option value="ALL">All statuses</option>
                        <option value="IN_TRANSIT">In Transit</option>
                        <option value="DELIVERED">Delivered</option>
                        <option value="DOCUMENTATION">Documentation</option>
                        <option value="ON_HOLD">On Hold</option>
                        <option value="CUSTOMS">Customs</option>
                        <option value="CANCELLED">Cancelled</option>
                      </select>
                    </label>

                    <label className="shipment-filter">
                      <span>Risk</span>
                      <select
                        value={riskFilter}
                        onChange={event =>
                          setRiskFilter(event.target.value)
                        }
                      >
                        <option value="ALL">All risk levels</option>
                        <option value="LOW">Low</option>
                        <option value="MEDIUM">Medium</option>
                        <option value="HIGH">High</option>
                      </select>
                    </label>
                  </div>
                </div>

                <div className="table-container">
                  <table className="shipment-table full-shipment-table">
                    <thead>
                      <tr>
                        <th>SHIPMENT REFERENCE</th>
                        <th>ROUTE</th>
                        <th>CONTAINER</th>
                        <th>STATUS</th>
                        <th>RISK</th>
                        <th>RISK SCORE</th>
                        <th>EXPECTED ARRIVAL</th>
                        <th>DETAILS</th>
                      </tr>
                    </thead>

                    <tbody>
                      {filteredShipments.map(shipment => (
                        <tr
                          key={shipment.shipment_id}
                          className={
                            selectedShipment?.shipment_id ===
                            shipment.shipment_id
                              ? 'selected-shipment-row'
                              : ''
                          }
                        >
                          <td className="shipment-id">
                            {shipment.shipment_ref}
                          </td>

                          <td>
                            <div className="shipment-route-cell">
                              <span>
                                {shipment.origin.replace(/, Sri Lanka$/, '')}
                              </span>
                              <span className="route-arrow">→</span>
                              <span>
                                {shipment.destination.replace(
                                  /, Sri Lanka$/,
                                  '',
                                )}
                              </span>
                            </div>
                          </td>

                          <td>{shipment.container_no || '—'}</td>

                          <td>
                            <span
                              className={`status status-${getStatusClass(
                                shipment.status,
                              )}`}
                            >
                              {formatLabel(shipment.status)}
                            </span>
                          </td>

                          <td>
                            <span
                              className={`risk risk-${getRiskClass(
                                shipment.current_risk_level,
                              )}`}
                            >
                              {formatLabel(shipment.current_risk_level)}
                            </span>
                          </td>

                          <td className="shipment-score">
                            {shipment.current_risk_score}
                          </td>

                          <td>
                            {formatShipmentDate(shipment.expected_arrival)}
                          </td>

                          <td>
                            <button
                              className="shipment-view-button"
                              onClick={() =>
                                setSelectedShipment(
                                  selectedShipment?.shipment_id ===
                                    shipment.shipment_id
                                    ? null
                                    : shipment,
                                )
                              }
                            >
                              {selectedShipment?.shipment_id ===
                              shipment.shipment_id
                                ? 'Close'
                                : 'View'}
                              <ArrowUpRight size={14} />
                            </button>
                          </td>
                        </tr>
                      ))}

                      {filteredShipments.length === 0 && (
                        <tr>
                          <td colSpan={8} className="empty-table-message">
                            {isShipmentsLoading
                              ? 'Loading shipment records...'
                              : 'No shipments match your search or filters.'}
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="shipment-table-footer">
                  <span>
                    {isShipmentsLoading
                      ? 'Updating shipment records...'
                      : 'Shipment records retrieved from the operations database.'}
                  </span>
                  <span>{filteredShipments.length} records</span>
                </div>
              </section>

              {selectedShipment && (
                <section className="panel shipment-details-panel">
                  <div className="panel-heading">
                    <div>
                      <div className="eyebrow">SHIPMENT DETAILS</div>
                      <h2>{selectedShipment.shipment_ref}</h2>
                      <p>
                        Detailed information from your shipment record.
                      </p>
                    </div>

                    <button
                      className="icon-button"
                      onClick={() => setSelectedShipment(null)}
                      aria-label="Close shipment details"
                    >
                      <X size={19} />
                    </button>
                  </div>

                  <div className="shipment-detail-grid">
                    <div className="shipment-detail-item">
                      <span>Shipment ID</span>
                      <strong>{selectedShipment.shipment_id}</strong>
                    </div>

                    <div className="shipment-detail-item">
                      <span>Container number</span>
                      <strong>{selectedShipment.container_no || '—'}</strong>
                    </div>

                    <div className="shipment-detail-item">
                      <span>Container type</span>
                      <strong>{selectedShipment.container_type || '—'}</strong>
                    </div>

                    <div className="shipment-detail-item">
                      <span>Current status</span>
                      <strong>{formatLabel(selectedShipment.status)}</strong>
                    </div>

                    <div className="shipment-detail-item">
                      <span>Shipper</span>
                      <strong>{selectedShipment.shipper || '—'}</strong>
                    </div>

                    <div className="shipment-detail-item">
                      <span>Consignee</span>
                      <strong>{selectedShipment.consignee || '—'}</strong>
                    </div>

                    <div className="shipment-detail-item">
                      <span>Origin</span>
                      <strong>{selectedShipment.origin || '—'}</strong>
                    </div>

                    <div className="shipment-detail-item">
                      <span>Destination</span>
                      <strong>{selectedShipment.destination || '—'}</strong>
                    </div>

                    <div className="shipment-detail-item">
                      <span>Expected arrival</span>
                      <strong>
                        {formatShipmentDate(selectedShipment.expected_arrival)}
                      </strong>
                    </div>

                    <div className="shipment-detail-item">
                      <span>Actual arrival</span>
                      <strong>
                        {formatShipmentDate(selectedShipment.actual_arrival)}
                      </strong>
                    </div>

                    <div className="shipment-detail-item">
                      <span>Risk level</span>
                      <strong>
                        <span
                          className={`risk risk-${getRiskClass(
                            selectedShipment.current_risk_level,
                          )}`}
                        >
                          {formatLabel(selectedShipment.current_risk_level)}
                        </span>
                      </strong>
                    </div>

                    <div className="shipment-detail-item">
                      <span>Risk score</span>
                      <strong>
                        {selectedShipment.current_risk_score} / 100
                      </strong>
                    </div>
                  </div>

                  {currentUser && ['ADMIN', 'MANAGER'].includes(currentUser.role) && (
                    <div className="shipment-supervisor-control">
                      <div>
                        <strong>Run CargoPilot Supervisor</strong>
                        <p>Process documents, investigate exceptions, assess risk and prepare actions for manager approval.</p>
                      </div>
                      <button
                        className="primary-button"
                        onClick={() => void runShipmentSupervisor()}
                        disabled={isSupervisorRunning || ['DELIVERED', 'CANCELLED'].includes(selectedShipment.status)}
                      >
                        <RefreshCw size={15} className={isSupervisorRunning ? 'refresh-spinning' : ''} />
                        {isSupervisorRunning ? 'Running workflow...' : 'Run Supervisor'}
                      </button>
                    </div>
                  )}

                  {supervisorFeedback && (
                    <div className={`document-alert document-alert-${supervisorFeedback.tone}`}>
                      <span>{supervisorFeedback.message}</span>
                      <button onClick={() => setSupervisorFeedback(null)} aria-label="Dismiss supervisor message">
                        <X size={15} />
                      </button>
                    </div>
                  )}
                </section>
              )}
            </>
          )}

          {/* DOCUMENTS WORKSPACE */}
          {activePage === 'Documents' && (
            <DocumentsPage shipments={shipments} />
          )}

          {/* MANAGER ACTION APPROVAL AND RECOVERY WORKSPACE */}
          {activePage === 'Actions & Approvals' && (
            <ActionControlPage currentUser={currentUser} />
          )}

          {/* REMAINING OPERATIONS MODULES */}
          {operationsPages.includes(activePage as OperationsPageName) &&
            activePage !== 'Actions & Approvals' && (
              <OperationsPage
                page={activePage as OperationsPageName}
                shipments={shipments}
              />
            )}

          {/* SETTINGS */}
          {activePage === 'Settings' && (
            <section className="placeholder-page">
              <div className="placeholder-icon">
                <Settings size={28} />
              </div>
              <h1>Settings</h1>
              <p>Workspace settings will be available here.</p>
              <button
                className="primary-button"
                onClick={() => selectPage('Overview')}
              >
                Back to Overview
              </button>
            </section>
          )}
        </div>
      </main>
    </div>
  )
}

export default App
