import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Send, TerminalSquare, LogOut, Loader2, Bot, Settings as SettingsIcon, MessageSquare, Mic, MicOff, Volume2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// If served over HTTPS, assume a reverse proxy (Nginx/Cloudflare) routes /api to the backend.
// Otherwise, explicitly point to the local port 8000.
const API_URL = window.location.protocol === 'https:' 
  ? '/api' 
  : `http://${window.location.hostname}:8000/api`;

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
          {loading ? <Loader2 className="spin" size={18} /> : 'Authenticate'}
        </button>
      </form>
    </div>
  );
}

function SettingsPanel({ token }) {
  const [curPass, setCurPass] = useState('');
  const [newPass, setNewPass] = useState('');
  const [passMsg, setPassMsg] = useState('');
  
  const [newUsername, setNewUsername] = useState('');
  const [newUserPass, setNewUserPass] = useState('');
  const [userMsg, setUserMsg] = useState('');

  const handleChangePassword = async (e) => {
    e.preventDefault();
    setPassMsg('Updating...');
    try {
      const res = await axios.post(`${API_URL}/settings/change_password`, 
        { current_password: curPass, new_password: newPass },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setPassMsg('✅ ' + res.data.message);
      setCurPass(''); setNewPass('');
    } catch (err) {
      setPassMsg('❌ ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleAddUser = async (e) => {
    e.preventDefault();
    setUserMsg('Adding...');
    try {
      const res = await axios.post(`${API_URL}/settings/add_user`, 
        { username: newUsername, password: newUserPass },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setUserMsg('✅ ' + res.data.message);
      setNewUsername(''); setNewUserPass('');
    } catch (err) {
      setUserMsg('❌ ' + (err.response?.data?.detail || err.message));
    }
  };

  return (
    <div className="glass-panel" style={{ padding: '30px', margin: '20px auto', maxWidth: '600px', width: '100%' }}>
      <h2 style={{ marginBottom: '20px' }}>Settings</h2>
      
      <div style={{ marginBottom: '40px' }}>
        <h3 style={{ marginBottom: '15px', color: 'var(--accent-color)' }}>Change Password</h3>
        <form onSubmit={handleChangePassword} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
          <div className="input-group">
            <label>Current Password</label>
            <input type="password" value={curPass} onChange={e=>setCurPass(e.target.value)} required />
          </div>
          <div className="input-group">
            <label>New Password</label>
            <input type="password" value={newPass} onChange={e=>setNewPass(e.target.value)} required />
          </div>
          <button type="submit" style={{ alignSelf: 'flex-start' }}>Update Password</button>
          {passMsg && <div style={{ fontSize: '14px', marginTop: '5px' }}>{passMsg}</div>}
        </form>
      </div>

      <div>
        <h3 style={{ marginBottom: '15px', color: 'var(--accent-color)' }}>Add New User</h3>
        <form onSubmit={handleAddUser} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
          <div className="input-group">
            <label>New Username</label>
            <input type="text" value={newUsername} onChange={e=>setNewUsername(e.target.value)} required />
          </div>
          <div className="input-group">
            <label>Password</label>
            <input type="password" value={newUserPass} onChange={e=>setNewUserPass(e.target.value)} required />
          </div>
          <button type="submit" style={{ alignSelf: 'flex-start' }}>Create User</button>
          {userMsg && <div style={{ fontSize: '14px', marginTop: '5px' }}>{userMsg}</div>}
        </form>
      </div>
    </div>
  );
}

function Workspace({ token, onLogout }) {
  const [view, setView] = useState('chat'); // 'chat' or 'settings'
  const [messages, setMessages] = useState([
    { id: 1, role: 'agent', content: 'Agentic Environment initialized. Awaiting directives.', timestamp: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);
  
  const [audioLanguage, setAudioLanguage] = useState('en');

  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  const toggleRecording = async () => {
    if (isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    } else {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorderRef.current = new MediaRecorder(stream);
        audioChunksRef.current = [];
        
        mediaRecorderRef.current.ondataavailable = e => {
          if (e.data.size > 0) audioChunksRef.current.push(e.data);
        };
        
        mediaRecorderRef.current.onstop = async () => {
          const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
          const formData = new FormData();
          formData.append('file', audioBlob, 'voice.webm');
          formData.append('language', audioLanguage);
          
          try {
            setLoading(true);
            const res = await axios.post(`${API_URL}/transcribe`, formData, {
              headers: { Authorization: `Bearer ${token}` }
            });
            setInput(prev => prev + (prev ? ' ' : '') + res.data.text);
          } catch (err) {
            console.error('Transcription failed:', err);
          } finally {
            setLoading(false);
          }
          // Cleanup microphone usage
          stream.getTracks().forEach(track => track.stop());
        };
        
        mediaRecorderRef.current.start();
        setIsRecording(true);
      } catch (err) {
        console.error("Mic access denied:", err);
      }
    }
  };

  const playTTS = async (text) => {
    try {
      const res = await axios.post(`${API_URL}/synthesize`, { text, language: 'en' }, {
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob'
      });
      const url = URL.createObjectURL(res.data);
      const audio = new Audio(url);
      audio.play();
    } catch (err) {
      console.error("TTS failed:", err);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (view === 'chat') {
      scrollToBottom();
    }
  }, [messages, view]);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const response = await axios.get(`${API_URL}/history`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (response.data && Array.isArray(response.data) && response.data.length > 0) {
          setMessages(prev => {
            return [prev[0], ...response.data];
          });
        } else if (typeof response.data === 'string') {
          console.error("Received string/HTML instead of JSON. Check reverse proxy API routing.");
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
        <div style={{ display: 'flex', gap: '10px' }}>
          <button onClick={() => setView(view === 'chat' ? 'settings' : 'chat')} style={{ background: 'transparent', border: '1px solid var(--panel-border)', padding: '8px 16px' }}>
            {view === 'chat' ? <><SettingsIcon size={16} /> <span style={{ marginLeft: '8px' }}>Settings</span></> : <><MessageSquare size={16} /> <span style={{ marginLeft: '8px' }}>Workspace</span></>}
          </button>
          <button onClick={onLogout} style={{ background: 'transparent', border: '1px solid var(--panel-border)', padding: '8px 16px' }}>
            <LogOut size={16} /> <span style={{ marginLeft: '8px' }}>Disconnect</span>
          </button>
        </div>
      </header>
      
      {view === 'settings' ? (
        <SettingsPanel token={token} />
      ) : (
        <main className="glass-panel chat-container">
          <div className="chat-history">
            {messages.map(msg => (
              <div key={msg.id} className={`message ${msg.role}`}>
                <div className="message-meta" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  {msg.role === 'agent' ? <Bot size={14} /> : null}
                  <span>{msg.role === 'agent' ? 'System' : 'You'}</span>
                  {msg.role === 'agent' && (
                    <button onClick={() => playTTS(msg.content)} style={{ background: 'none', border: 'none', padding: '0', cursor: 'pointer', marginLeft: '4px' }} title="Read Out Loud">
                      <Volume2 size={14} color="var(--accent-color)" />
                    </button>
                  )}
                  <span style={{ marginLeft: 'auto', fontSize: '11px', opacity: 0.85 }}>{msg.timestamp}</span>
                </div>
                <div className="markdown-body" style={{ whiteSpace: 'pre-wrap', fontSize: '14px', lineHeight: '1.6' }}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                </div>
              </div>
            ))}
            {loading && (
              <div className="message agent pulse" style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <Loader2 className="spin" size={16} /> Orchestrating...
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
          
          <div style={{ display: 'flex', gap: '15px', padding: '0 20px', marginBottom: '8px', justifyContent: 'flex-end', fontSize: '13px', color: 'var(--text-muted)' }}>
            <span>Audio Input Language:</span>
            <label style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
              <input type="radio" name="lang" value="en" checked={audioLanguage === 'en'} onChange={(e) => setAudioLanguage(e.target.value)} /> EN
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
              <input type="radio" name="lang" value="ro" checked={audioLanguage === 'ro'} onChange={(e) => setAudioLanguage(e.target.value)} /> RO
            </label>
          </div>
          
          <form onSubmit={handleSend} className="chat-input-area">
            <button type="button" onClick={toggleRecording} style={{ background: isRecording ? '#ef4444' : 'transparent', color: isRecording ? '#fff' : 'var(--text-color)', border: '1px solid var(--panel-border)', display: 'flex', alignItems: 'center', justifyContent: 'center', minWidth: '40px' }} title="Hold to speak">
              {isRecording ? <MicOff size={18} /> : <Mic size={18} />}
            </button>
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
      )}
    </div>
  );
}

export default App;
