import { useState, useEffect } from 'react';
import type { FarmerProfile, FinalResponse } from './types/api';
import { fetchRecommendations, checkHealth, fetchCrops, fetchSeasons, ApiError } from './utils/api';
import { registerCrops, registerSeasons } from './utils/cropNames';
import { DEFAULT_MOCK_API } from './config';

import ChatIntake from './components/ChatIntake';
import ReviewScreen from './components/ReviewScreen';
import LoadingScreen from './components/LoadingScreen';
import ResultScreen from './components/ResultScreen';
import Header from './components/Header';

export type Screen = 'chat' | 'review' | 'loading' | 'result' | 'error';

export default function App() {
  const [screen, setScreen] = useState<Screen>('chat');
  const [profile, setProfile] = useState<FarmerProfile | null>(null);
  const [result, setResult] = useState<FinalResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>('');
  const [errorStatus, setErrorStatus] = useState<number>(0);
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [isMockMode, setIsMockMode] = useState<boolean>(() => {
    const saved = localStorage.getItem('fieldshift_mock_mode');
    return saved !== null ? saved === 'true' : DEFAULT_MOCK_API;
  });

  // Check backend health on mount and periodically, and fetch reference data
  useEffect(() => {
    let mounted = true;
    const verifyHealth = () => {
      checkHealth().then(ok => {
        if (mounted) setBackendOnline(ok);
      });
    };
    verifyHealth();

    // Fetch dynamic reference data from backend
    fetchCrops().then(crops => {
      if (crops && crops.length > 0) registerCrops(crops);
    });
    fetchSeasons().then(seasons => {
      if (seasons && seasons.length > 0) registerSeasons(seasons);
    });

    const interval = setInterval(verifyHealth, 6000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  function handleToggleMockMode() {
    setIsMockMode(prev => {
      const next = !prev;
      localStorage.setItem('fieldshift_mock_mode', String(next));
      return next;
    });
  }

  async function handleSubmit(p: FarmerProfile) {
    setProfile(p);
    setScreen('loading');
    setErrorMsg('');
    try {
      const res = await fetchRecommendations(p, isMockMode);
      setResult(res);
      setScreen('result');
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMsg(err.detail);
        setErrorStatus(err.status);
      } else {
        const fallbackMsg = !backendOnline && !isMockMode
          ? 'Cannot connect to backend server at http://127.0.0.1:8000. Is the backend running? You can also toggle "Mock Mode" at the top to test offline.'
          : 'An unexpected network error occurred. Please check connection and try again.';
        setErrorMsg(fallbackMsg);
        setErrorStatus(0);
      }
      setScreen('error');
    }
  }

  function handleRetry() {
    if (profile) {
      handleSubmit(profile);
    } else {
      setScreen('chat');
    }
  }

  function handleStartOver() {
    setProfile(null);
    setResult(null);
    setErrorMsg('');
    setScreen('chat');
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Header
        backendOnline={backendOnline}
        isMockMode={isMockMode}
        onToggleMockMode={handleToggleMockMode}
        onStartOver={screen !== 'chat' ? handleStartOver : undefined}
      />

      <main style={{ flex: 1, paddingTop: 24, paddingBottom: 48 }}>
        {screen === 'chat' && (
          <ChatIntake
            initialProfile={profile}
            isMockMode={isMockMode}
            onComplete={(p) => { setProfile(p); setScreen('review'); }}
          />
        )}

        {screen === 'review' && profile && (
          <ReviewScreen
            profile={profile}
            onEdit={() => setScreen('chat')}
            onSubmit={() => handleSubmit(profile)}
            onUpdateProfile={(updated) => setProfile(updated)}
          />
        )}

        {screen === 'loading' && <LoadingScreen />}

        {screen === 'result' && result && profile && (
          <ResultScreen
            response={result}
            profile={profile}
            onStartOver={handleStartOver}
            isMock={isMockMode}
          />
        )}

        {screen === 'error' && (
          <div className="container" style={{ paddingTop: 40, maxWidth: 560 }}>
            <div className="card fade-in" style={{ textAlign: 'center', padding: 40 }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>
                {errorStatus === 504 ? '🌐' : errorStatus === 400 ? '⚠️' : '❌'}
              </div>
              <h2 style={{ marginBottom: 12, color: 'var(--red-700)' }}>
                {errorStatus === 504
                  ? 'Service Temporarily Unavailable'
                  : errorStatus === 400
                  ? 'No Feasible Rotation Found'
                  : 'Backend Connection Error'}
              </h2>
              <p style={{ color: 'var(--stone-600)', marginBottom: 24, lineHeight: 1.7 }}>
                {errorStatus === 504
                  ? 'Weather or soil data services are unavailable. Please retry in a minute — this is not your fault.'
                  : errorMsg || 'An unexpected error occurred.'}
              </p>
              <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
                {(errorStatus === 504 || errorStatus === 500 || errorStatus === 0) && (
                  <button className="btn-primary" onClick={handleRetry}>
                    🔄 Retry
                  </button>
                )}
                <button
                  className="btn-secondary"
                  onClick={() => {
                    handleToggleMockMode();
                    if (profile) handleSubmit(profile);
                  }}
                >
                  ⚡ Switch to {isMockMode ? 'Live Mode' : 'Mock Mode'}
                </button>
                <button className="btn-ghost" onClick={handleStartOver}>
                  Start Over
                </button>
              </div>
            </div>
          </div>
        )}
      </main>

      <footer style={{
        textAlign: 'center',
        padding: '16px 20px',
        fontSize: '0.8rem',
        color: 'var(--stone-500)',
        borderTop: '1px solid var(--stone-200)',
        background: 'white',
      }}>
        🌱 FieldShift — NASA Space Apps Challenge · Powered by cropseq
        <span style={{ marginLeft: 10, color: isMockMode ? 'var(--amber-600)' : 'var(--green-700)', fontWeight: 600 }}>
          [{isMockMode ? 'Mock Mode active' : 'Live Online Backend active'}]
        </span>
      </footer>
    </div>
  );
}
