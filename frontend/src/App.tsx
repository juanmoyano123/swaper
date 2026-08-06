function App() {
  return (
    <div
      style={{
        minHeight: '100svh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexDirection: 'column',
        gap: '8px',
      }}
    >
      <span style={{ fontSize: '17px', fontWeight: 700, letterSpacing: '-0.01em' }}>
        10-Swaper
      </span>
      <span className="mono" style={{ fontSize: '11px', color: 'var(--dim)' }}>
        frontend inicializado — rutas y cliente HTTP: F-003
      </span>
    </div>
  )
}

export default App
