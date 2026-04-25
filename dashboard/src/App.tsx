import { useState } from 'react';
import { Activity, Database, AlertTriangle, Settings, Route } from 'lucide-react';
import './index.css';

import Dashboard from './components/Dashboard';
import Exceptions from './components/Exceptions';
import Rules from './components/Rules';
import Mappings from './components/Mappings';

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');

  return (
    <div className="dashboard-container">
      <header className="animate-fade-in">
        <div className="brand">
          <div className="brand-icon">
            <Activity color="white" size={24} />
          </div>
          <div>
            <h1 className="title">QDVI Engine Command Center</h1>
            <p className="subtitle">Quality Data Validation & Integration • Phase 3 Orchestration</p>
          </div>
        </div>
        <div className="tabs" style={{ display: 'flex', gap: '1rem', marginTop: '1.5rem', borderBottom: '1px solid var(--bg-border)', paddingBottom: '0.5rem' }}>
          <button 
            onClick={() => setActiveTab('dashboard')} 
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'none', border: 'none', color: activeTab === 'dashboard' ? 'var(--accent-blue)' : 'var(--text-muted)', fontWeight: activeTab === 'dashboard' ? 'bold' : 'normal', cursor: 'pointer', borderBottom: activeTab === 'dashboard' ? '2px solid var(--accent-blue)' : 'none', paddingBottom: '0.5rem' }}
          >
            <Database size={16} /> Event Dashboard
          </button>
          <button 
            onClick={() => setActiveTab('exceptions')} 
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'none', border: 'none', color: activeTab === 'exceptions' ? 'var(--accent-red)' : 'var(--text-muted)', fontWeight: activeTab === 'exceptions' ? 'bold' : 'normal', cursor: 'pointer', borderBottom: activeTab === 'exceptions' ? '2px solid var(--accent-red)' : 'none', paddingBottom: '0.5rem' }}
          >
            <AlertTriangle size={16} /> Exceptions Queue
          </button>
          <button 
            onClick={() => setActiveTab('rules')} 
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'none', border: 'none', color: activeTab === 'rules' ? 'var(--accent-green)' : 'var(--text-muted)', fontWeight: activeTab === 'rules' ? 'bold' : 'normal', cursor: 'pointer', borderBottom: activeTab === 'rules' ? '2px solid var(--accent-green)' : 'none', paddingBottom: '0.5rem' }}
          >
            <Settings size={16} /> Rule Management
          </button>
          <button 
            onClick={() => setActiveTab('mappings')} 
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'none', border: 'none', color: activeTab === 'mappings' ? 'orange' : 'var(--text-muted)', fontWeight: activeTab === 'mappings' ? 'bold' : 'normal', cursor: 'pointer', borderBottom: activeTab === 'mappings' ? '2px solid orange' : 'none', paddingBottom: '0.5rem' }}
          >
            <Route size={16} /> Field Mapping
          </button>
        </div>
      </header>

      <div style={{ marginTop: '2rem' }}>
        {activeTab === 'dashboard' && <Dashboard />}
        {activeTab === 'exceptions' && <Exceptions />}
        {activeTab === 'rules' && <Rules />}
        {activeTab === 'mappings' && <Mappings />}
      </div>
    </div>
  );
}

export default App;
