import { useEffect, useState } from 'react';
import { Settings } from 'lucide-react';

export default function Rules() {
  const [rules, setRules] = useState<any[]>([]);
  const [showForm, setShowForm] = useState(false);
  
  // form state
  const [processStep, setProcessStep] = useState('ROUTE_STEP');
  const [assemblyLevel, setAssemblyLevel] = useState('MAIN_ASSEMBLY');
  const [resultType, setResultType] = useState('PASS');
  const [mandatoryFields, setMandatoryFields] = useState('');
  const [forbiddenFields, setForbiddenFields] = useState('');

  const fetchRules = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/v1/rules');
      if (res.ok) setRules((await res.json()).data);
    } catch (e) {
      console.error(e);
    }
  };

  const toggleRule = async (ruleId: string, currentEnabled: boolean) => {
    try {
      await fetch(`http://127.0.0.1:8000/api/v1/rules/${ruleId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !currentEnabled })
      });
      fetchRules();
    } catch (e) { alert("Error toggling"); }
  };

  const saveRule = async () => {
    const payload = {
      processStep,
      assemblyLevel,
      resultType,
      mandatoryFields: mandatoryFields.split(',').map(s=>s.trim()).filter(Boolean),
      forbiddenFields: forbiddenFields.split(',').map(s=>s.trim()).filter(Boolean),
      enabled: true
    };
    try {
      await fetch('http://127.0.0.1:8000/api/v1/rules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      setShowForm(false);
      fetchRules();
    } catch (e) { alert("Error saving rule"); }
  };

  useEffect(() => {
    fetchRules();
  }, []);

  return (
    <div className="glass-card animate-fade-in" style={{ overflowX: 'auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 className="section-header">
          <Settings size={20} /> Validation Rules Management
        </h2>
        <button className="btn-sm" onClick={() => setShowForm(!showForm)} style={{ background: 'var(--accent-blue)', color:'white' }}>
          {showForm ? 'Close Form' : 'Create / Edit Rule'}
        </button>
      </div>

      {showForm && (
        <div style={{ margin: '1rem 0', padding: '1rem', background: 'rgba(0,0,0,0.3)', borderRadius: '8px', display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <div style={{display:'flex', flexDirection:'column', gap: '0.2rem'}}>
            <label style={{fontSize: '0.8rem'}}>Process Step</label>
            <select value={processStep} onChange={e=>setProcessStep(e.target.value)} style={{padding:'0.4rem', borderRadius:'4px', background:'var(--bg-card)', color:'white'}}>
              <option value="ROUTE_STEP">ROUTE_STEP</option>
              <option value="PART_VERIFICATION">PART_VERIFICATION</option>
              <option value="DC_TOOL_STEP">DC_TOOL_STEP</option>
              <option value="FLUID_FILL_STEP">FLUID_FILL_STEP</option>
              <option value="FF_STEP">FF_STEP</option>
              <option value="DECKING_VISION">DECKING_VISION</option>
            </select>
          </div>
          <div style={{display:'flex', flexDirection:'column', gap: '0.2rem'}}>
            <label style={{fontSize: '0.8rem'}}>Assembly Level</label>
            <select value={assemblyLevel} onChange={e=>setAssemblyLevel(e.target.value)} style={{padding:'0.4rem', borderRadius:'4px', background:'var(--bg-card)', color:'white'}}>
              <option value="MAIN_ASSEMBLY">MAIN_ASSEMBLY</option>
              <option value="SUB_ASSEMBLY">SUB_ASSEMBLY</option>
            </select>
          </div>
          <div style={{display:'flex', flexDirection:'column', gap: '0.2rem'}}>
            <label style={{fontSize: '0.8rem'}}>Result Type</label>
            <select value={resultType} onChange={e=>setResultType(e.target.value)} style={{padding:'0.4rem', borderRadius:'4px', background:'var(--bg-card)', color:'white'}}>
              <option value="PASS">PASS</option>
              <option value="FAIL">FAIL</option>
              <option value="OVERRIDE_PASS">OVERRIDE_PASS</option>
              <option value="OVERRIDE_FAIL">OVERRIDE_FAIL</option>
            </select>
          </div>
          <div style={{display:'flex', flexDirection:'column', gap: '0.2rem'}}>
            <label style={{fontSize: '0.8rem'}}>Mandatory Fields (comma sep)</label>
            <input value={mandatoryFields} onChange={e=>setMandatoryFields(e.target.value)} placeholder="e.g. eventId, defectCode" style={{padding:'0.4rem', borderRadius:'4px', background:'transparent', border: '1px solid gray', color:'white'}} />
          </div>
          <div style={{display:'flex', flexDirection:'column', gap: '0.2rem'}}>
            <label style={{fontSize: '0.8rem'}}>Forbidden Fields (comma sep)</label>
            <input value={forbiddenFields} onChange={e=>setForbiddenFields(e.target.value)} placeholder="e.g. defectCode" style={{padding:'0.4rem', borderRadius:'4px', background:'transparent', border: '1px solid gray', color:'white'}} />
          </div>
          <div style={{display:'flex', alignItems: 'flex-end'}}>
            <button onClick={saveRule} style={{padding:'0.4rem 1rem', background:'var(--accent-green)', color:'black', borderRadius:'4px', cursor:'pointer', fontWeight:'bold', border:'none'}}>Save Rule</button>
          </div>
        </div>
      )}

      <table className="data-table">
        <thead>
          <tr>
            <th>Rule ID</th>
            <th>Step</th>
            <th>Type</th>
            <th>Mandatory Fields</th>
            <th>Forbidden Fields</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {rules.map(rule => (
            <tr key={rule.rule_id} style={{ opacity: rule.enabled ? 1 : 0.5 }}>
              <td style={{ fontSize: '0.8rem', fontWeight: 'bold' }}>{rule.rule_id}</td>
              <td style={{ fontSize: '0.85rem' }}>{rule.process_step} <br/> ({rule.assembly_level})</td>
              <td><span className={`badge ${rule.result_type === 'PASS' ? 'pass' : 'fail'}`}>{rule.result_type}</span></td>
              <td style={{ fontSize: '0.75rem', maxWidth: '200px' }}>{rule.mandatory_fields_json}</td>
              <td style={{ fontSize: '0.75rem', maxWidth: '200px' }}>{rule.forbidden_fields_json}</td>
              <td>
                <span className={`badge ${rule.enabled ? 'pass' : 'fail'}`}>
                  {rule.enabled ? 'ENABLED' : 'DISABLED'}
                </span>
              </td>
              <td>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button onClick={() => toggleRule(rule.rule_id, rule.enabled)} className="btn-sm" style={{background: 'var(--bg-card)', border: '1px solid var(--text-muted)'}}>
                    {rule.enabled ? 'Disable' : 'Enable'}
                  </button>
                  <button onClick={() => {
                    setProcessStep(rule.process_step);
                    setAssemblyLevel(rule.assembly_level);
                    setResultType(rule.result_type);
                    setMandatoryFields(JSON.parse(rule.mandatory_fields_json).join(', '));
                    setForbiddenFields(JSON.parse(rule.forbidden_fields_json).join(', '));
                    setShowForm(true);
                  }} className="btn-sm" style={{background: 'var(--accent-blue)', color: 'white', border: 'none'}}>
                    Edit
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
