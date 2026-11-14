import { useState, useEffect } from 'react';

const PIPELINE_STEPS = [
  { delay: 0,    label: '🛰️  Fetching satellite location data...' },
  { delay: 400,  label: '🌍  Downloading soil data from SoilGrids...' },
  { delay: 800,  label: '🌦️  Retrieving weather & climate data...' },
  { delay: 1200, label: '🌱  Building crop compatibility matrix...' },
  { delay: 1500, label: '⚖️  Scoring rotation sequences...' },
  { delay: 1750, label: '🏆  Selecting optimal rotations...' },
  { delay: 1900, label: '📝  Generating explanation...' },
];

export default function LoadingScreen() {
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    const timers: ReturnType<typeof setTimeout>[] = [];

    PIPELINE_STEPS.forEach((step, i) => {
      const t = setTimeout(() => {
        setCurrentStep(i);
      }, step.delay);
      timers.push(t);
    });

    return () => timers.forEach(clearTimeout);
  }, []);

  return (
    <div className="container" style={{ maxWidth: 520, paddingTop: 60, textAlign: 'center' }}>
      <div className="fade-in">
        {/* Animated wheat field */}
        <div style={{ fontSize: 64, marginBottom: 16, lineHeight: 1 }}>
          🌾
        </div>

        <h2 style={{ marginBottom: 8, color: 'var(--green-800)' }}>
          Analysing Your Farm
        </h2>
        <p style={{ color: 'var(--stone-500)', marginBottom: 36, fontSize: '0.9rem' }}>
          Our pipeline is running — this usually takes 10–30 seconds.
        </p>

        {/* Animated dots */}
        <div className="dot-pulse" style={{ justifyContent: 'center', marginBottom: 32 }}>
          <span /><span /><span />
        </div>

        {/* Pipeline steps */}
        <div className="card" style={{ textAlign: 'left', padding: '20px 24px' }}>
          {PIPELINE_STEPS.map((s, i) => {
            const done = i < currentStep;
            const active = i === currentStep;
            return (
              <div
                key={i}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: '8px 0',
                  borderBottom: i < PIPELINE_STEPS.length - 1 ? '1px solid var(--stone-100)' : 'none',
                  opacity: done ? 1 : active ? 1 : 0.35,
                  transition: 'opacity 0.3s',
                }}
              >
                <span style={{ fontSize: 16, width: 22, textAlign: 'center' }}>
                  {done ? '✅' : active ? '⏳' : '○'}
                </span>
                <span style={{
                  fontSize: '0.875rem',
                  fontWeight: active ? 600 : 400,
                  color: active ? 'var(--green-700)' : done ? 'var(--stone-700)' : 'var(--stone-400)',
                }}>
                  {s.label}
                </span>
              </div>
            );
          })}
        </div>

        <p style={{ marginTop: 20, fontSize: '0.78rem', color: 'var(--stone-400)' }}>
          Real data from NASA satellites, SoilGrids, and Open-Meteo
        </p>
      </div>
    </div>
  );
}
