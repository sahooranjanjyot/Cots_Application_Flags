import { useEffect, useState } from 'react';
import { Route, Edit2 } from 'lucide-react';

export default function Mappings() {
  const [mappings, setMappings] = useState<Record<string, string>>({});
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string>('');

  const fetchMappings = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/v1/mappings');
      if (res.ok) setMappings((await res.json()).data);
    } catch (e) {
      console.error(e);
    }
  };

  const updateMapping = async (key: string) => {
    try {
      await fetch(`http://127.0.0.1:8000/api/v1/mappings/${key}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ targetField: editValue })
      });
      setEditingKey(null);
      fetchMappings();
    } catch (e) {
      alert("Error updating mapping");
    }
  };

  useEffect(() => {
    fetchMappings();
  }, []);

  return (
    <div className="glass-card animate-fade-in" style={{ overflowX: 'auto', maxWidth: '800px', margin: '0 auto' }}>
      <h2 className="section-header">
        <Route size={20} /> Field Mapping Management
      </h2>
      <p style={{marginBottom: '1rem', color: 'var(--text-muted)', fontSize: '0.9rem'}}>Maps Source MES Payload Field Names to Final Canonical Configuration.</p>
      <table className="data-table">
        <thead>
          <tr>
            <th>Source Field (MES)</th>
            <th>Target Field (FLAGS)</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(mappings).map(([key, val]) => (
            <tr key={key}>
              <td style={{ fontWeight: 'bold', color: 'var(--accent-blue)' }}>{key}</td>
              <td>
                {editingKey === key ? (
                  <input 
                    value={editValue} 
                    onChange={e => setEditValue(e.target.value)}
                    style={{ background: 'transparent', border: '1px solid var(--accent-blue)', color: 'white', padding: '0.2rem' }}
                  />
                ) : (
                  <span>{val}</span>
                )}
              </td>
              <td>
                {editingKey === key ? (
                  <div style={{display:'flex', gap:'0.5rem'}}>
                    <button onClick={() => updateMapping(key)} className="btn-sm" style={{background: 'var(--accent-green)', color:'black'}}>Save</button>
                    <button onClick={() => setEditingKey(null)} className="btn-sm">Cancel</button>
                  </div>
                ) : (
                  <button onClick={() => { setEditingKey(key); setEditValue(val); }} className="btn-sm"><Edit2 size={12}/> Edit</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
