import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Send, TerminalSquare, LogOut, Loader2, Bot } from 'lucide-react';

const API_URL = `http://${window.location.hostname}:8000/api`;

function App() {
  const [token, setToken] = useState(localStorage.getItem('token'));
  
  if (!token) {
    return <Login onLogin={setToken} />;
  }

  return <Workspace token={token} onLogout={() => { setToken(null); localStorage.removeItem('token'); }} />;
}

function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    
    try {
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);
      
      const response = await axios.post(`${API_URL}/login`, formData);
      const { access_token } = response.data;
      localStorage.setItem('token', access_token);
      onLogin(access_token);
    } catch (err) {
      setError('Invalid username or password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="glass-panel auth-container">
      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '8px' }}>
        <TerminalSquare size={48} color="var(--accent-color)" />
      </div>
      <h1 className="auth-title">Agentic Workspace</h1>
      <p style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '14px', marginTop: '-16px' }}>
        Log in to access your AI environment
      </p>
      
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <div className="input-group">
          <label>Username</label>
          <input type="text" value={username} onChange={e => setUsername(e.target.value)} required placeholder="e.g., admin" />
        </div>
        <div className="input-group">
          <label>Password</label>
          <input type="password" value={password} onChange={e => setPassword(e.target.value)} required />
        </div>
        
        {error && <div className="error-text">{error}</div>}
        
        <button type="submit" disabled={loading}>
          {loading ? <Loader2 className="pulse" size={18} /> : 'Authenticate'}
        </button>
      </form>
    </div>
  );
}

function Workspace({ token, onLogout }) {
  const [messages, setMessages] = useState([
    { id: 1, role: 'agent', content: 'Agentic Environment initialized. Awaiting directives.', timestamp: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const response = await axios.get(`${API_URL}/history`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (response.data && response.data.length > 0) {
          setMessages(prev => {
            // Merge initial greeting with fetched history
            return [prev[0], ...response.data];
          });
        }
      } catch (err) {
        console.error("Failed to load history", err);
      }
    };
    fetchHistory();
  }, [token]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage = { id: Date.now(), role: 'user', content: input, timestamp: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await axios.post(`${API_URL}/command`, 
        { command: userMessage.content },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      // Parse the backend JSON response to display properly
      const data = response.data;
      let displayContent = data.message || JSON.stringify(data);
      if (data.status === 'executing') {
        displayContent += `\n\n[Details]: ${data.details}\n[Staged Command]: ${data.command_staged}`;
      }

      const agentMessage = {
        id: Date.now() + 1,
        role: 'agent',
        content: displayContent,
        timestamp: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})
      };
      
      setMessages(prev => [...prev, agentMessage]);
      
    } catch (err) {
      if (err.response?.status === 401) onLogout();
      setMessages(prev => [...prev, { id: Date.now()+1, role: 'agent', content: `Error: ${err.message}`, timestamp: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-layout">
      <header className="glass-panel header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <TerminalSquare color="var(--accent-color)" />
          <h2 style={{ fontSize: '18px', fontWeight: 600 }}>Antigravity Interface</h2>
        </div>
        <button onClick={onLogout} style={{ background: 'transparent', border: '1px solid var(--panel-border)', padding: '8px 16px' }}>
          <LogOut size={16} /> <span style={{ marginLeft: '8px' }}>Disconnect</span>
        </button>
      </header>
      
      <main className="glass-panel chat-container">
        <div className="chat-history">
          {messages.map(msg => (
            <div key={msg.id} className={`message ${msg.role}`}>
              <div className="message-meta" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                {msg.role === 'agent' ? <Bot size={14} /> : null}
                <span>{msg.role === 'agent' ? 'System' : 'You'}</span>
                <span style={{ marginLeft: 'auto', fontSize: '11px', opacity: 0.85 }}>{msg.timestamp}</span>
              </div>
              <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
            </div>
          ))}
          {loading && (
            <div className="message agent pulse" style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <Loader2 className="pulse" size={16} /> Orchestrating...
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
        
        <form onSubmit={handleSend} className="chat-input-area">
          <input 
            type="text" 
            value={input} 
            onChange={e => setInput(e.target.value)} 
            placeholder="Issue a command to the environment..."
            autoFocus
          />
          <button type="submit" disabled={loading || !input.trim()}>
            <Send size={18} />
          </button>
        </form>
      </main>
    </div>
  );
}

export default App;
