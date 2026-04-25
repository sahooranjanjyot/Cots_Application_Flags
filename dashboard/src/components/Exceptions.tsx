import { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle } from 'lucide-react';

export default function Exceptions() {
  const [exceptions, setExceptions] = useState<any[]>([]);

  const fetchData = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/v1/events/exceptions');
      if (res.ok) setExceptions((await res.json()).data);
    } catch (err) {
      console.error(err);
    }
  };

  const resolveException = async (id: string) => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/v1/exceptions/${id}/resolve`, { method: 'POST' });
      if (res.ok) { alert("Resolved!"); fetchData(); }
    } catch (e) { alert("Network error"); }
  };

  useEffect(() => {
    fetchData();
  }, []);

  return (
    <div className="glass-card animate-fade-in" style={{ overflowX: 'auto' }}>
      <h2 className="section-header">
        <AlertTriangle size={20} /> Exception Queue
      </h2>
      <table className="data-table">
        <thead>
          <tr>
            <th>Time (UTC)</th>
            <th>Event ID</th>
            <th>Type</th>
            <th>Reason</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {exceptions.map((exc) => (
            <tr key={exc.id}>
              <td style={{ fontSize: '0.85rem' }}>{new Date(exc.created_at).toLocaleString()}</td>
              <td style={{ fontSize: '0.85rem' }}>{exc.event_id}</td>
              <td><span className="badge fail">{exc.exception_type}</span></td>
              <td style={{ fontSize: '0.8rem', color: 'var(--accent-red)' }}>{exc.exception_reason}</td>
              <td>
                {exc.resolved ? (
                  <span className="badge pass"><CheckCircle size={10} style={{marginRight:4}}/> Resolved ({exc.resolved_by})</span>
                ) : (
                  <span className="badge" style={{background: 'rgba(255,165,0,0.2)', color: 'orange'}}>Pending</span>
                )}
              </td>
              <td>
                {!exc.resolved && (
                  <button onClick={() => resolveException(exc.id)} className="btn-sm"><CheckCircle size={12}/> Mark Resolvd</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
