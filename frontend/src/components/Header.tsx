interface HeaderProps {
  backendOnline: boolean | null;
  isMockMode: boolean;
  onToggleMockMode: () => void;
  onStartOver?: () => void;
}

export default function Header({ backendOnline, isMockMode, onToggleMockMode, onStartOver }: HeaderProps) {
  return (
    <header style={{
      background: 'white',
      borderBottom: '1px solid var(--stone-200)',
      boxShadow: 'var(--shadow-sm)',
      position: 'sticky',
      top: 0,
      zIndex: 100,
    }}>
      <div className="container" style={{ maxWidth: 900, padding: '12px 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
        {/* Logo + title */}
        <div
          style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: onStartOver ? 'pointer' : 'default' }}
          onClick={onStartOver}
        >
          <div style={{
            width: 36, height: 36,
            background: 'linear-gradient(135deg, var(--green-600), var(--green-800))',
            borderRadius: 10,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 18,
          }}>
            🌾
          </div>
          <div>
            <div style={{ fontFamily: 'Nunito, sans-serif', fontWeight: 900, fontSize: '1.1rem', color: 'var(--green-800)', lineHeight: 1.1 }}>
              FieldShift
            </div>
            <div style={{ fontSize: '0.7rem', color: 'var(--stone-500)', lineHeight: 1 }}>
              Crop Rotation Advisor
            </div>
          </div>
        </div>

        {/* Status pills and mode switcher */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          {/* Mode toggle button */}
          <button
            onClick={onToggleMockMode}
            className={`badge ${isMockMode ? 'badge-amber' : 'badge-green'}`}
            style={{
              cursor: 'pointer',
              border: 'none',
              padding: '6px 12px',
              fontSize: '0.8rem',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
            }}
            title="Click to toggle between Live Backend and Mock Mode"
          >
            <span>{isMockMode ? '📋 Mock Mode' : '⚡ Live Backend'}</span>
            <span style={{ fontSize: '0.7rem', opacity: 0.7 }}>(Switch)</span>
          </button>

          {/* Backend Health Badge */}
          <span
            className={`badge ${backendOnline === null ? 'badge-stone' : backendOnline ? 'badge-green' : 'badge-amber'}`}
            title={backendOnline === null ? 'Checking...' : backendOnline ? 'Backend is reachable on port 8000' : 'Backend offline (port 8000 unreachable)'}
            style={{ padding: '6px 12px', fontSize: '0.8rem' }}
          >
            {backendOnline === null ? '⏳ Checking' : backendOnline ? '🟢 Backend Online' : '🔴 Backend Offline'}
          </span>

          {onStartOver && (
            <button className="btn-ghost" onClick={onStartOver} style={{ fontSize: '0.8rem', padding: '6px 10px' }}>
              New Farm
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
