import React, { useState, useEffect } from 'react';

const BACKEND_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';
const API_BASE = `${BACKEND_URL}/api/v1`;

export default function App() {
  // Auth state
  const [token, setToken] = useState(() => localStorage.getItem('sw_token') || '');
  const [currentUser, setCurrentUser] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('sw_user')) || null;
    } catch {
      return null;
    }
  });
  const [authMode, setAuthMode] = useState('login'); // 'login' | 'register'
  const [authEmail, setAuthEmail] = useState('admin@errivanta.io');
  const [authPassword, setAuthPassword] = useState('password123');
  const [authFullName, setAuthFullName] = useState('');
  const [authOrgName, setAuthOrgName] = useState('Demo Organization');
  const [authError, setAuthError] = useState('');

  // Dashboard state
  const [activeTab, setActiveTab] = useState('overview'); // 'overview' | 'incidents' | 'apikeys'
  const [selectedServiceId, setSelectedServiceId] = useState(null);
  const [overview, setOverview] = useState(null);
  const [services, setServices] = useState([]);
  const [serviceDetail, setServiceDetail] = useState(null);
  const [serviceEvents, setServiceEvents] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [incidentFilter, setIncidentFilter] = useState('ALL'); // 'ALL' | 'OPEN' | 'RESOLVED'
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(new Date());

  // New Service / Key Generation form state
  const [newServiceName, setNewServiceName] = useState('');
  const [newOrgName, setNewOrgName] = useState(currentUser?.organization_name || 'Demo Organization');
  const [newlyCreatedKey, setNewlyCreatedKey] = useState(null);
  const [copiedKey, setCopiedKey] = useState(false);

  // Headers helper with JWT Bearer Token
  const getAuthHeaders = () => {
    const headers = { 'Content-Type': 'application/json' };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  };

  // Auth Handlers
  const handleAuthSubmit = async (e) => {
    e.preventDefault();
    setAuthError('');
    try {
      const endpoint = authMode === 'login' ? `${API_BASE}/auth/login` : `${API_BASE}/auth/register`;
      const payload = authMode === 'login'
        ? { email: authEmail, password: authPassword }
        : { email: authEmail, password: authPassword, full_name: authFullName || 'Admin', organization_name: authOrgName || 'My Org' };

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Authentication failed');
      }

      const data = await res.json();
      setToken(data.access_token);
      setCurrentUser(data.user);
      localStorage.setItem('sw_token', data.access_token);
      localStorage.setItem('sw_user', JSON.stringify(data.user));
      setNewOrgName(data.user.organization_name);
    } catch (err) {
      setAuthError(err.message);
    }
  };

  const handleLogout = () => {
    setToken('');
    setCurrentUser(null);
    localStorage.removeItem('sw_token');
    localStorage.removeItem('sw_user');
    setOverview(null);
    setServices([]);
    setIncidents([]);
  };

  // Polling data fetcher
  const fetchData = async () => {
    if (!token) return;
    try {
      const headers = getAuthHeaders();

      // 1. Overview counts
      const resOverview = await fetch(`${API_BASE}/dashboard/overview`, { headers });
      if (resOverview.ok) {
        setOverview(await resOverview.json());
      } else if (resOverview.status === 401) {
        handleLogout();
        return;
      }

      // 2. Services list
      const resServices = await fetch(`${API_BASE}/services`, { headers });
      if (resServices.ok) {
        setServices(await resServices.json());
      }

      // 3. Incidents
      const resIncidents = await fetch(`${API_BASE}/incidents`, { headers });
      if (resIncidents.ok) {
        setIncidents(await resIncidents.json());
      }

      // 4. Selected Service details if active
      if (selectedServiceId) {
        const resMetrics = await fetch(`${API_BASE}/services/${selectedServiceId}/metrics?window=5`, { headers });
        if (resMetrics.ok) {
          setServiceDetail(await resMetrics.json());
        }

        const resEvents = await fetch(`${API_BASE}/services/${selectedServiceId}/events?limit=15`, { headers });
        if (resEvents.ok) {
          setServiceEvents(await resEvents.json());
        }
      }

      setLastUpdated(new Date());
    } catch (err) {
      console.error('Error fetching ServiceWatch data:', err);
    }
  };

  useEffect(() => {
    if (token) {
      fetchData();
      if (!autoRefresh) return;
      const interval = setInterval(fetchData, 3000);
      return () => clearInterval(interval);
    }
  }, [token, selectedServiceId, autoRefresh]);

  const handleResolveIncident = async (incidentId) => {
    try {
      const res = await fetch(`${API_BASE}/incidents/${incidentId}/resolve`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        fetchData();
      }
    } catch (err) {
      console.error('Error resolving incident:', err);
    }
  };

  const handleRegisterService = async (e) => {
    e.preventDefault();
    if (!newServiceName.trim()) return;
    try {
      const res = await fetch(`${API_BASE}/services/register`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          organization_name: newOrgName.trim() || currentUser?.organization_name || 'Demo Organization',
          service_name: newServiceName.trim(),
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setNewlyCreatedKey(data);
        setNewServiceName('');
        fetchData();
      }
    } catch (err) {
      console.error('Error registering service:', err);
    }
  };

  // If not authenticated, show modern SaaS login / register screen
  if (!token) {
    return (
      <div className="app-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', background: 'linear-gradient(135deg, #090d16 0%, #0f172a 100%)' }}>
        <div style={{ width: '100%', maxWidth: '440px', padding: '2.5rem', backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '12px', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.5)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem', justifyContent: 'center' }}>
            <div className="brand-icon" style={{ width: 42, height: 42, fontSize: '1.25rem' }}>EV</div>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>Errivanta</h2>
          </div>
          <p style={{ textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '2rem' }}>
            {authMode === 'login' ? 'Sign in to access your organization monitoring dashboard' : 'Create an organization monitoring account'}
          </p>

          {authError && (
            <div style={{ padding: '0.75rem 1rem', backgroundColor: 'rgba(239, 68, 68, 0.1)', border: '1px solid var(--color-critical)', borderRadius: '6px', color: '#fca5a5', fontSize: '0.85rem', marginBottom: '1.25rem' }}>
              {authError}
            </div>
          )}

          <form onSubmit={handleAuthSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {authMode === 'register' && (
              <>
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.4rem', fontWeight: 600 }}>
                    ORGANIZATION NAME
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Acme Corp"
                    value={authOrgName}
                    onChange={(e) => setAuthOrgName(e.target.value)}
                    style={{ width: '100%', padding: '0.75rem', backgroundColor: 'var(--bg-primary)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-primary)' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.4rem', fontWeight: 600 }}>
                    FULL NAME
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Alex Smith"
                    value={authFullName}
                    onChange={(e) => setAuthFullName(e.target.value)}
                    style={{ width: '100%', padding: '0.75rem', backgroundColor: 'var(--bg-primary)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-primary)' }}
                  />
                </div>
              </>
            )}

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.4rem', fontWeight: 600 }}>
                EMAIL ADDRESS
              </label>
              <input
                type="email"
                required
                placeholder="developer@company.com"
                value={authEmail}
                onChange={(e) => setAuthEmail(e.target.value)}
                style={{ width: '100%', padding: '0.75rem', backgroundColor: 'var(--bg-primary)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-primary)' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.4rem', fontWeight: 600 }}>
                PASSWORD
              </label>
              <input
                type="password"
                required
                placeholder="••••••••"
                value={authPassword}
                onChange={(e) => setAuthPassword(e.target.value)}
                style={{ width: '100%', padding: '0.75rem', backgroundColor: 'var(--bg-primary)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-primary)' }}
              />
            </div>

            <button type="submit" className="btn-primary" style={{ padding: '0.85rem', width: '100%', marginTop: '0.5rem', fontSize: '0.95rem' }}>
              {authMode === 'login' ? 'Sign In to Dashboard' : 'Create Account'}
            </button>
          </form>

          <div style={{ marginTop: '1.5rem', textAlign: 'center', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            {authMode === 'login' ? (
              <span>
                Don't have an account?{' '}
                <a href="#register" onClick={() => setAuthMode('register')} style={{ color: 'var(--color-primary)', fontWeight: 600 }}>
                  Create Organization
                </a>
              </span>
            ) : (
              <span>
                Already have an account?{' '}
                <a href="#login" onClick={() => setAuthMode('login')} style={{ color: 'var(--color-primary)', fontWeight: 600 }}>
                  Sign In
                </a>
              </span>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="app-container">
      {/* Header Navbar */}
      <header className="navbar">
        <div className="brand">
          <div className="brand-icon">EV</div>
          <div>
            <span style={{ fontWeight: 700, fontSize: '1.1rem' }}>Errivanta</span>
            <div style={{ fontSize: '0.75rem', color: 'var(--color-healthy)' }}>
              🏢 {currentUser?.organization_name || 'Demo Organization'}
            </div>
          </div>
        </div>

        <nav className="nav-links">
          <button
            className={`nav-btn ${activeTab === 'overview' && !selectedServiceId ? 'active' : ''}`}
            onClick={() => {
              setActiveTab('overview');
              setSelectedServiceId(null);
            }}
          >
            📊 Microservices
          </button>
          <button
            className={`nav-btn ${activeTab === 'incidents' ? 'active' : ''}`}
            onClick={() => {
              setActiveTab('incidents');
              setSelectedServiceId(null);
            }}
          >
            🚨 Incidents {overview?.open_incidents > 0 && <span className="badge badge-critical" style={{ marginLeft: 6 }}>{overview.open_incidents}</span>}
          </button>
          <button
            className={`nav-btn ${activeTab === 'apikeys' ? 'active' : ''}`}
            onClick={() => {
              setActiveTab('apikeys');
              setSelectedServiceId(null);
            }}
          >
            🔑 API Keys & Provisioning
          </button>
        </nav>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
          <div className="live-indicator">
            <div className="pulsing-dot" />
            <span>Live</span>
            <span style={{ fontSize: '0.75rem', marginLeft: 8 }}>{lastUpdated.toLocaleTimeString()}</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              {currentUser?.email}
            </span>
            <button
              onClick={handleLogout}
              className="btn-secondary"
              style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem', borderRadius: '4px' }}
            >
              Sign Out
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="main-content">
        {selectedServiceId ? (
          /* Service Detail View */
          <ServiceDetailView
            service={serviceDetail}
            events={serviceEvents}
            onBack={() => setSelectedServiceId(null)}
          />
        ) : activeTab === 'overview' ? (
          /* Overview View */
          <>
            {/* Top Metric Cards */}
            <div className="overview-grid">
              <div className="summary-card">
                <span className="summary-title">Total Microservices</span>
                <span className="summary-value">{overview?.total_services ?? 0}</span>
              </div>
              <div className="summary-card healthy">
                <span className="summary-title">Healthy</span>
                <span className="summary-value">{overview?.healthy_services ?? 0}</span>
              </div>
              <div className="summary-card warning">
                <span className="summary-title">Warning</span>
                <span className="summary-value">{overview?.warning_services ?? 0}</span>
              </div>
              <div className="summary-card critical">
                <span className="summary-title">Critical</span>
                <span className="summary-value">{overview?.critical_services ?? 0}</span>
              </div>
              <div className="summary-card incidents">
                <span className="summary-title">Open Incidents</span>
                <span className="summary-value">{overview?.open_incidents ?? 0}</span>
              </div>
            </div>

            {/* Monitored Microservices Table */}
            <div className="table-container">
              <div className="table-header">
                <h3 className="table-title">Monitored Microservices</h3>
                <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                  Rolling 5-minute telemetry ({currentUser?.organization_name})
                </span>
              </div>
              <table>
                <thead>
                  <tr>
                    <th>Service Name</th>
                    <th>Status</th>
                    <th>Requests (5m)</th>
                    <th>Errors (5m)</th>
                    <th>Error Rate</th>
                    <th>Avg Latency</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {services.map((svc) => (
                    <tr key={svc.id}>
                      <td style={{ fontWeight: 600 }}>{svc.name}</td>
                      <td>
                        <span className={`badge badge-${svc.health.toLowerCase()}`}>
                          {svc.health === 'HEALTHY' && '🟢'}
                          {svc.health === 'WARNING' && '🟡'}
                          {svc.health === 'CRITICAL' && '🔴'}
                          {' '}{svc.health}
                        </span>
                      </td>
                      <td className="mono">{svc.total_requests_last_5m.toLocaleString()}</td>
                      <td className="mono">{svc.total_errors_last_5m.toLocaleString()}</td>
                      <td className="mono" style={{ color: svc.error_rate > 10 ? 'var(--color-critical)' : svc.error_rate > 5 ? 'var(--color-warning)' : 'inherit' }}>
                        {svc.error_rate}%
                      </td>
                      <td className="mono">{svc.avg_response_time_ms} ms</td>
                      <td>
                        <button
                          className="btn-primary"
                          style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem' }}
                          onClick={() => setSelectedServiceId(svc.id)}
                        >
                          View Metrics →
                        </button>
                      </td>
                    </tr>
                  ))}
                  {services.length === 0 && (
                    <tr>
                      <td colSpan="7" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
                        No microservices registered yet for {currentUser?.organization_name}. Go to "API Keys & Provisioning" to add your first service!
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </>
        ) : activeTab === 'incidents' ? (
          /* Incidents View */
          <IncidentsView
            incidents={incidents}
            filter={incidentFilter}
            setFilter={setIncidentFilter}
            onResolve={handleResolveIncident}
          />
        ) : (
          /* API Keys View */
          <ApiKeysView
            services={services}
            newServiceName={newServiceName}
            setNewServiceName={setNewServiceName}
            newOrgName={newOrgName}
            setNewOrgName={setNewOrgName}
            onSubmit={handleRegisterService}
            newlyCreatedKey={newlyCreatedKey}
            copiedKey={copiedKey}
            setCopiedKey={setCopiedKey}
          />
        )}
      </main>
    </div>
  );
}

// -------------------------------------------------------------
// Component: Microservice Detail & Deep Metrics View
// -------------------------------------------------------------
function ServiceDetailView({ service, events, onBack }) {
  if (!service) {
    return <div style={{ padding: '2rem' }}>Loading service metrics...</div>;
  }

  const maxReqs = Math.max(...(service.time_series?.map((p) => p.requests) || [1]), 1);

  return (
    <div>
      {/* Back navigation header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <button onClick={onBack} className="btn-secondary" style={{ padding: '0.4rem 0.8rem' }}>
            ← Back to Overview
          </button>
          <h2>{service.service_name}</h2>
          <span className={`badge badge-${service.health.toLowerCase()}`}>
            {service.health === 'HEALTHY' && '🟢'}
            {service.health === 'WARNING' && '🟡'}
            {service.health === 'CRITICAL' && '🔴'}
            {' '}{service.health}
          </span>
        </div>
        <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
          Window: Last {service.window_minutes} Minutes
        </span>
      </div>

      {/* Metrics Row */}
      <div className="overview-grid" style={{ marginBottom: '2rem' }}>
        <div className="summary-card">
          <span className="summary-title">Total Requests</span>
          <span className="summary-value">{service.total_requests.toLocaleString()}</span>
        </div>
        <div className="summary-card">
          <span className="summary-title">Total Errors</span>
          <span className="summary-value" style={{ color: service.total_errors > 0 ? 'var(--color-critical)' : 'inherit' }}>
            {service.total_errors.toLocaleString()}
          </span>
        </div>
        <div className="summary-card">
          <span className="summary-title">Error Rate</span>
          <span className="summary-value" style={{ color: service.error_rate > 10 ? 'var(--color-critical)' : 'inherit' }}>
            {service.error_rate}%
          </span>
        </div>
        <div className="summary-card">
          <span className="summary-title">Avg Latency</span>
          <span className="summary-value">{service.avg_response_time_ms} ms</span>
        </div>
        <div className="summary-card">
          <span className="summary-title">P95 Latency</span>
          <span className="summary-value">{service.p95_response_time_ms} ms</span>
        </div>
      </div>

      {/* Time Series Visualization */}
      <div className="table-container" style={{ padding: '1.5rem', marginBottom: '2rem' }}>
        <h3 style={{ marginBottom: '1rem' }}>Throughput & Error Trends (Last 15 Minutes)</h3>
        <div style={{ display: 'flex', alignItems: 'flex-end', height: '140px', gap: '8px', borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
          {service.time_series?.map((pt, idx) => {
            const heightPercent = Math.max((pt.requests / maxReqs) * 100, 4);
            const hasErrors = pt.errors > 0;
            return (
              <div key={idx} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', height: '100%', justifyContent: 'flex-end' }}>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                  {pt.requests}
                </span>
                <div
                  style={{
                    width: '100%',
                    height: `${heightPercent}%`,
                    backgroundColor: hasErrors ? 'var(--color-critical)' : 'var(--color-primary)',
                    borderRadius: '4px 4px 0 0',
                    transition: 'all 0.3s ease',
                  }}
                  title={`${pt.minute}: ${pt.requests} reqs, ${pt.errors} errors, ${pt.error_rate}% error rate, avg ${pt.avg_response_time_ms}ms`}
                />
                <span style={{ fontSize: '0.65rem', color: 'var(--text-secondary)', marginTop: '6px' }}>
                  {pt.minute.slice(-2)}m
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Live Recent Telemetry Events */}
      <div className="table-container">
        <div className="table-header">
          <h3 className="table-title">Recent Telemetry Stream</h3>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Real-time event log</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Method</th>
              <th>Endpoint</th>
              <th>Status</th>
              <th>Latency</th>
              <th>Error Details</th>
            </tr>
          </thead>
          <tbody>
            {events.map((evt) => (
              <tr key={evt.id}>
                <td className="mono" style={{ fontSize: '0.8rem' }}>{new Date(evt.timestamp).toLocaleTimeString()}</td>
                <td><span className="mono" style={{ fontWeight: 600 }}>{evt.method}</span></td>
                <td className="mono">{evt.endpoint}</td>
                <td>
                  <span className={`badge badge-${evt.status_code >= 500 ? 'critical' : evt.status_code >= 400 ? 'warning' : 'healthy'}`}>
                    {evt.status_code}
                  </span>
                </td>
                <td className="mono">{evt.response_time_ms} ms</td>
                <td style={{ color: 'var(--color-critical)', fontSize: '0.85rem' }}>{evt.error || '-'}</td>
              </tr>
            ))}
            {events.length === 0 && (
              <tr>
                <td colSpan="6" style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-secondary)' }}>
                  No telemetry events recorded yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// -------------------------------------------------------------
// Component: Incidents View
// -------------------------------------------------------------
function IncidentsView({ incidents, filter, setFilter, onResolve }) {
  const filtered = incidents.filter((inc) => {
    if (filter === 'ALL') return true;
    return inc.status === filter;
  });

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
        <h2>Active & Resolved Incidents</h2>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          {['ALL', 'OPEN', 'RESOLVED'].map((f) => (
            <button
              key={f}
              className={filter === f ? 'btn-primary' : 'btn-secondary'}
              style={{ padding: '0.4rem 0.85rem', fontSize: '0.85rem' }}
              onClick={() => setFilter(f)}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Service</th>
              <th>Severity</th>
              <th>Status</th>
              <th>Error Rate</th>
              <th>Condition</th>
              <th>Started At</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((inc) => (
              <tr key={inc.id}>
                <td className="mono">#{inc.id}</td>
                <td style={{ fontWeight: 600 }}>{inc.service_name}</td>
                <td>
                  <span className={`badge badge-${inc.severity.toLowerCase()}`}>
                    {inc.severity}
                  </span>
                </td>
                <td>
                  <span className={`badge badge-${inc.status === 'OPEN' ? 'critical' : 'healthy'}`}>
                    {inc.status}
                  </span>
                </td>
                <td className="mono" style={{ color: 'var(--color-critical)', fontWeight: 600 }}>
                  {inc.error_rate}%
                </td>
                <td>{inc.trigger_condition}</td>
                <td className="mono" style={{ fontSize: '0.8rem' }}>
                  {new Date(inc.started_at).toLocaleString()}
                </td>
                <td>
                  {inc.status === 'OPEN' ? (
                    <button
                      className="btn-primary"
                      style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem', backgroundColor: 'var(--color-healthy)' }}
                      onClick={() => onResolve(inc.id)}
                    >
                      ✓ Resolve Incident
                    </button>
                  ) : (
                    <span style={{ color: 'var(--color-healthy)', fontSize: '0.85rem' }}>
                      Resolved
                    </span>
                  )}
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan="8" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
                  No incidents found matching current filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// -------------------------------------------------------------
// Component: API Keys & Microservice Provisioning View
// -------------------------------------------------------------
function ApiKeysView({
  services,
  newServiceName,
  setNewServiceName,
  newOrgName,
  setNewOrgName,
  onSubmit,
  newlyCreatedKey,
  copiedKey,
  setCopiedKey,
}) {
  return (
    <div>
      <h2 style={{ marginBottom: '0.5rem' }}>API Keys & Microservice Provisioning</h2>
      <p style={{ color: 'var(--text-secondary)', marginBottom: '2rem' }}>
        Manage API keys for your company's backend microservices and integrate new services with the ServiceWatch SDK.
      </p>

      {/* Register New Service Form */}
      <div className="table-container" style={{ padding: '1.75rem', marginBottom: '2rem' }}>
        <h3 style={{ marginBottom: '0.5rem' }}>Provision an API Key for a New Microservice</h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1.25rem' }}>
          Create an API key when adding a new backend microservice (e.g. <code>user-service</code>, <code>inventory-service</code>).
        </p>

        <form onSubmit={onSubmit} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: '1rem', alignItems: 'flex-end' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.4rem', fontWeight: 600 }}>
              ORGANIZATION NAME
            </label>
            <input
              type="text"
              required
              value={newOrgName}
              onChange={(e) => setNewOrgName(e.target.value)}
              style={{
                width: '100%',
                padding: '0.65rem 0.85rem',
                backgroundColor: 'var(--bg-primary)',
                border: '1px solid var(--border-color)',
                borderRadius: '6px',
                color: 'var(--text-primary)'
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.4rem', fontWeight: 600 }}>
              MICROSERVICE NAME
            </label>
            <input
              type="text"
              required
              placeholder="e.g. user-service"
              value={newServiceName}
              onChange={(e) => setNewServiceName(e.target.value)}
              style={{
                width: '100%',
                padding: '0.65rem 0.85rem',
                backgroundColor: 'var(--bg-primary)',
                border: '1px solid var(--border-color)',
                borderRadius: '6px',
                color: 'var(--text-primary)'
              }}
            />
          </div>

          <button type="submit" className="btn-primary" style={{ padding: '0.65rem 1.25rem' }}>
            Generate API Key
          </button>
        </form>

        {/* Generated Key Result Banner */}
        {newlyCreatedKey && (
          <div style={{
            marginTop: '1.5rem',
            padding: '1.25rem',
            backgroundColor: 'rgba(16, 185, 129, 0.1)',
            border: '1px solid rgba(16, 185, 129, 0.3)',
            borderRadius: '8px'
          }}>
            <h4 style={{ color: 'var(--color-healthy)', marginBottom: '0.35rem' }}>
              ✓ API Key Generated for <code>{newlyCreatedKey.service_name}</code>
            </h4>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', marginTop: '0.5rem' }}>
              <code style={{ fontFamily: 'var(--font-mono)', fontSize: '1rem', color: '#60a5fa' }}>
                {newlyCreatedKey.api_key}
              </code>
              <button
                className="btn-primary"
                style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem' }}
                onClick={() => {
                  navigator.clipboard.writeText(newlyCreatedKey.api_key);
                  setCopiedKey(true);
                  setTimeout(() => setCopiedKey(false), 2000);
                }}
              >
                {copiedKey ? '✓ Copied' : 'Copy Key'}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Integration Code Guide */}
      <div className="table-container" style={{ padding: '1.75rem' }}>
        <h3 style={{ marginBottom: '0.5rem' }}>SDK Quickstart Guide</h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1rem' }}>
          Add these 3 lines to any FastAPI microservice in your company:
        </p>

        <pre style={{
          padding: '1.25rem',
          backgroundColor: 'var(--bg-primary)',
          border: '1px solid var(--border-color)',
          borderRadius: '8px',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.85rem',
          overflowX: 'auto',
          lineHeight: 1.6
        }}>
{`from fastapi import FastAPI
from servicewatch import ServiceWatch

app = FastAPI(title="My Service")

# 1. Initialize Errivanta Monitoring
monitor = ServiceWatch(
    service_name="my-microservice",
    api_key="${newlyCreatedKey?.api_key || 'sw_live_YOUR_API_KEY'}",
    monitoring_url="${BACKEND_URL}/api/v1/telemetry"
)
monitor.init_app(app)`}
        </pre>
      </div>
    </div>
  );
}
