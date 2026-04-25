import React, { useEffect, useState } from 'react';
import { ShieldCheck, ServerCrash, Activity, Database, RefreshCw, Filter } from 'lucide-react';
import './index.css';

interface StatData {
  total_passed: number;
  total_failed: number;
  total_retry: number;
  total_processed: number;
}

interface QualityEvent {
  id: string;
  product_id: string;
  serial_number: string;
  step: string;
  result: string;
  defect_code: string;
  defect_description: string;
  validation_status: string;
  transmission_status: string;
  error_message: string;
  created_at: string;
}

function App() {
  const [stats, setStats] = useState<StatData>({ total_passed: 0, total_failed: 0, total_retry: 0, total_processed: 0 });
  const [events, setEvents] = useState<QualityEvent[]>([]);
  
  // Filters
  const [filterStep, setFilterStep] = useState('');
  const [filterResult, setFilterResult] = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  const fetchData = async () => {
    try {
      const [statsRes, eventsRes] = await Promise.all([
        fetch('http://127.0.0.1:8000/api/v1/dashboard/stats'),
        fetch('http://127.0.0.1:8000/api/v1/dashboard/events')
      ]);

      setStats(await statsRes.json());
      setEvents((await eventsRes.json()).data);
    } catch (err) {
      console.error("Failed to fetch dashboard data:", err);
    }
  };

  const retryEvent = async (id: string) => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/v1/dashboard/retry/${id}`, {
        method: 'POST'
      });
      if (res.ok) {
        alert("Retry attempted successfully! Check logs for new result.");
        fetchData();
      } else {
        const err = await res.json();
        alert("Retry Failed: " + err.detail);
      }
    } catch (e) {
      alert("Network error during retry");
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, []);

  const filteredEvents = events.filter(e => {
    if (filterStep && e.step !== filterStep) return false;
    if (filterResult && e.result !== filterResult) return false;
    if (filterStatus && e.transmission_status !== filterStatus && e.validation_status !== filterStatus) return false;
    return true;
  });

  return (
    <div className="dashboard-container">
      <header className="animate-fade-in">
        <div className="brand">
          <div className="brand-icon">
            <Activity color="white" size={24} />
          </div>
          <div>
            <h1 className="title">QDVI Engine Dashboard</h1>
            <p className="subtitle">Quality Data Validation & Integration • Live Database View</p>
          </div>
        </div>
      </header>

      <div className="stats-grid animate-fade-in delay-1">
        <div className="glass-card stat-item">
          <div className="stat-label">Total Processed</div>
          <div className="stat-value">{stats.total_processed}</div>
        </div>
        <div className="glass-card stat-item">
          <div className="stat-label">Success</div>
          <div className="stat-value success">{stats.total_passed}</div>
        </div>
        <div className="glass-card stat-item">
          <div className="stat-label">Failed (DLQ + Retry)</div>
          <div className="stat-value error">{stats.total_failed + stats.total_retry}</div>
        </div>
      </div>

      <div className="glass-card animate-fade-in delay-2" style={{ marginBottom: '2rem' }}>
        <div className="section-header">
          <Filter size={20} /> Event Filters
        </div>
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <select value={filterStep} onChange={(e) => setFilterStep(e.target.value)} style={{ padding: '0.5rem', borderRadius: '8px', background: 'var(--bg-card)', color: 'white', border: '1px solid var(--bg-border)' }}>
            <option value="">All Steps</option>
            <option value="ROUTE">ROUTE</option>
            <option value="DC_TOOL">DC_TOOL</option>
            <option value="FLUID_FILL">FLUID_FILL</option>
            <option value="DECKING_VISION">DECKING_VISION</option>
          </select>
          <select value={filterResult} onChange={(e) => setFilterResult(e.target.value)} style={{ padding: '0.5rem', borderRadius: '8px', background: 'var(--bg-card)', color: 'white', border: '1px solid var(--bg-border)' }}>
            <option value="">All Results</option>
            <option value="PASS">PASS</option>
            <option value="FAIL">FAIL</option>
          </select>
          <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} style={{ padding: '0.5rem', borderRadius: '8px', background: 'var(--bg-card)', color: 'white', border: '1px solid var(--bg-border)' }}>
            <option value="">All Statuses</option>
            <option value="SUCCESS">SUCCESS</option>
            <option value="FAILED">FAILED</option>
          </select>
          <button onClick={() => { setFilterStep(''); setFilterResult(''); setFilterStatus(''); }} style={{ padding: '0.5rem 1rem', borderRadius: '8px', background: 'transparent', color: 'var(--text-muted)', border: '1px solid var(--text-muted)', cursor: 'pointer' }}>
            Clear Filters
          </button>
        </div>
      </div>

      <div className="glass-card animate-fade-in delay-3" style={{ overflowX: 'auto' }}>
        <h2 className="section-header">
          <Database size={20} /> Event Audit Log (Database)
        </h2>
        {filteredEvents.length === 0 ? (
          <p style={{ color: 'var(--text-muted)' }}>No events match your criteria.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Time (UTC)</th>
                <th>Product</th>
                <th>Serial</th>
                <th>Step / Result</th>
                <th>Defect Details</th>
                <th>Validation</th>
                <th>Transmission</th>
                <th>Retry</th>
              </tr>
            </thead>
            <tbody>
              {filteredEvents.map((event) => (
                <tr key={event.id}>
                  <td style={{ fontSize: '0.85rem' }}>{new Date(event.created_at).toLocaleString()}</td>
                  <td>{event.product_id || '-'}</td>
                  <td>{event.serial_number || '-'}</td>
                  <td>
                    {event.step || '-'} <br/>
                    <span style={{ fontSize: '0.8rem', color: event.result === 'PASS' ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                      {event.result || '-'}
                    </span>
                  </td>
                  <td style={{ fontSize: '0.8rem', maxWidth: '150px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {event.defect_code ? `${event.defect_code}: ${event.defect_description}` : '-'}
                  </td>
                  <td>
                    <span className={`badge ${event.validation_status === 'PASSED' ? 'pass' : 'fail'}`}>
                      {event.validation_status}
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${event.transmission_status === 'SUCCESS' ? 'pass' : 'fail'}`}>
                      {event.transmission_status}
                    </span>
                    {event.error_message && (
                      <div style={{ fontSize: '0.75rem', color: 'var(--accent-red)', marginTop: '4px' }}>
                        {event.error_message}
                      </div>
                    )}
                  </td>
                  <td>
                    {(event.validation_status === 'FAILED' || event.transmission_status === 'FAILED') && (
                      <button 
                        onClick={() => retryEvent(event.id)}
                        style={{
                          display: 'flex', alignItems: 'center', gap: '0.25rem',
                          padding: '0.25rem 0.5rem', borderRadius: '6px', 
                          background: 'rgba(59,130,246,0.15)', color: 'var(--accent-blue)', 
                          border: '1px solid rgba(59,130,246,0.3)', cursor: 'pointer',
                          fontSize: '0.75rem', fontWeight: 'bold'
                        }}
                      >
                        <RefreshCw size={12} /> Retry
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export default App;
