import { useEffect, useState } from 'react';
import { Database, RefreshCw, Filter, PlayCircle } from 'lucide-react';

export default function Dashboard() {
  const [stats, setStats] = useState({ total_passed: 0, total_failed: 0, total_retry: 0, total_processed: 0 });
  const [events, setEvents] = useState<any[]>([]);
  
  const [filterStep, setFilterStep] = useState('');
  const [filterResult, setFilterResult] = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  const [selectedEvent, setSelectedEvent] = useState<any>(null);
  const [eventDetails, setEventDetails] = useState<any>(null);

  const fetchData = async () => {
    try {
      const [statsRes, eventsRes] = await Promise.all([
        fetch('http://127.0.0.1:8000/api/v1/dashboard/stats'),
        fetch('http://127.0.0.1:8000/api/v1/events')
      ]);
      setStats(await statsRes.json());
      setEvents((await eventsRes.json()).data);
    } catch (err) {
      console.error("Failed to fetch dashboard data:", err);
    }
  };

  const fetchDetails = async (eventId: string) => {
    const res = await fetch(`http://127.0.0.1:8000/api/v1/events/${eventId}`);
    if (res.ok) setEventDetails(await res.json());
  };

  const retryEvent = async (id: string, e: any) => {
    e.stopPropagation();
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/v1/events/${id}/retry`, { method: 'POST' });
      if (res.ok) { alert("Retry attempted successfully!"); fetchData(); }
      else alert("Retry Failed: " + (await res.json()).detail);
    } catch (e) { alert("Network error"); }
  };

  const replayEvent = async (id: string, e: any) => {
    e.stopPropagation();
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/v1/events/${id}/replay`, { method: 'POST' });
      if (res.ok) { alert("Replay successful!"); fetchData(); }
      else alert("Replay Failed: " + (await res.json()).detail);
    } catch (e) { alert("Network error"); }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const filteredEvents = events.filter((e: any) => {
    if (filterStep && e.step !== filterStep) return false;
    if (filterResult && e.result !== filterResult) return false;
    if (filterStatus && e.transmission_status !== filterStatus && e.validation_status !== filterStatus) return false;
    return true;
  });

  return (
    <>
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

      <div style={{ display: 'flex', gap: '1rem' }}>
        <div className="glass-card animate-fade-in delay-3" style={{ overflowX: 'auto', flex: selectedEvent ? 2 : 1 }}>
          <h2 className="section-header">
            <Database size={20} /> Event Log
          </h2>
          <table className="data-table">
            <thead>
              <tr>
                <th>Time (UTC)</th>
                <th>Product</th>
                <th>Step / Result</th>
                <th>Transmission</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredEvents.map((event: any) => (
                <tr key={event.id} onClick={() => { setSelectedEvent(event); fetchDetails(event.event_id); }} style={{ cursor: 'pointer' }}>
                  <td style={{ fontSize: '0.85rem' }}>{new Date(event.created_at).toLocaleString()}</td>
                  <td>{event.product_id || '-'}</td>
                  <td>
                    {event.step || '-'} <br/>
                    <span style={{ fontSize: '0.8rem', color: event.result === 'PASS' ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                      {event.result || '-'}
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${event.transmission_status === 'SUCCESS' ? 'pass' : 'fail'}`}>
                      {event.transmission_status}
                    </span>
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <button onClick={(e) => retryEvent(event.event_id, e)} className="btn-sm"><RefreshCw size={12}/> Retry</button>
                      <button onClick={(e) => replayEvent(event.event_id, e)} className="btn-sm"><PlayCircle size={12}/> Replay</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {selectedEvent && eventDetails && (
          <div className="glass-card animate-fade-in" style={{ flex: 1, height: '100%' }}>
            <h2>Details: {selectedEvent.event_id}</h2>
            <div style={{ marginTop: '1rem', fontSize: '0.9rem' }}>
              <p>Validation: <span className={`badge ${selectedEvent.validation_status==='PASSED'?'pass':'fail'}`}>{selectedEvent.validation_status}</span></p>
              <p>Transmission: <span className={`badge ${selectedEvent.transmission_status==='SUCCESS'?'pass':'fail'}`}>{selectedEvent.transmission_status}</span></p>
              <p style={{color: 'var(--accent-red)'}}>{selectedEvent.error_message}</p>
            </div>
            <h4 style={{ marginTop: '1rem' }}>Processing Attempts:</h4>
            <ul>
              {eventDetails.attempts.map((a: any) => (
                <li key={a.id} style={{fontSize: '0.8rem', marginTop: '0.5rem'}}>
                  #{a.attempt_number} [{a.attempt_type}] - {a.result_status}
                  {a.error_message && <div style={{color:'red'}}>{a.error_message}</div>}
                </li>
              ))}
            </ul>
            <h4 style={{ marginTop: '1rem' }}>Raw Payload:</h4>
            <pre style={{ background: 'black', padding: '1rem', borderRadius: '8px', fontSize: '0.75rem', overflowX: 'auto' }}>
              {JSON.stringify(JSON.parse(selectedEvent.payload || '{}'), null, 2)}
            </pre>
          </div>
        )}
      </div>
    </>
  );
}
