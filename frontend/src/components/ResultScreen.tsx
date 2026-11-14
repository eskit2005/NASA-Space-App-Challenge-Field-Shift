import { useState } from 'react';
import type { FinalResponse, FarmerProfile, EvaluatedSequence } from '../types/api';
import {
  deriveBestSequence,
  collectWarnings,
  formatUSD,
  formatNumber,
  getCropVisual,
  formatSoilHealth,
  humanizeSummary,
} from '../utils/helpers';
import { getCropName, getSeasonLabel } from '../utils/cropNames';
import { sendIntakeMessage } from '../utils/api';

interface ResultScreenProps {
  response: FinalResponse;
  profile: FarmerProfile;
  onStartOver: () => void;
  isMock?: boolean;
}

export default function ResultScreen({ response, profile, onStartOver, isMock }: ResultScreenProps) {
  const [showAllSequences, setShowAllSequences] = useState(false);
  const [openSections, setOpenSections] = useState<Set<string>>(new Set(['water', 'soil']));
  const [qaMessages, setQaMessages] = useState<Array<{ role: 'farmer' | 'assistant'; content: string }>>([]);
  const [qaInput, setQaInput] = useState('');
  const [qaLoading, setQaLoading] = useState(false);

  const handleAskQuestion = async (q: string) => {
    const questionText = q.trim();
    if (!questionText || qaLoading) return;
    setQaInput('');
    setQaLoading(true);
    setQaMessages(prev => [...prev, { role: 'farmer', content: questionText }]);
    try {
      const reply = await sendIntakeMessage(
        {
          messages: [{ role: 'farmer', content: questionText }],
          draft: profile,
          farm_id: profile.farm_id,
        },
        isMock
      );
      setQaMessages(prev => [...prev, { role: 'assistant', content: reply.reply }]);
    } catch {
      setQaMessages(prev => [
        ...prev,
        { role: 'assistant', content: 'Unable to reach the advisor service right now. Please try again shortly.' },
      ]);
    } finally {
      setQaLoading(false);
    }
  };

  const best = deriveBestSequence(response);
  const { farmerWarnings, technicalNotes } = collectWarnings(response);
  const sequences = response.evaluated?.sequences ?? [];
  const pareto = sequences.filter(s => s.is_pareto_optimal);
  const dominated = sequences.filter(s => !s.is_pareto_optimal);
  const explanation = response.explanation ?? {};
  const sections = explanation.sections ?? {};
  const evidence = explanation.evidence ?? [];
  const soil = response.environment?.soil;
  const seasons = response.environment?.seasons ?? [];

  function toggleSection(key: string) {
    setOpenSections(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  const bestCropNames = best ? best.crop_ids.map(getCropName) : [];
  const soilHealth = best ? formatSoilHealth(best.metrics.soil_score ?? 0.2) : null;
  const waterDemand = best?.metrics.water_m3 ?? 0;
  const waterQuota = profile.irrigation_quota_m3 ?? 45000;
  const waterRatio = waterQuota > 0 ? Math.min(100, Math.round((waterQuota / waterDemand) * 100)) : 100;

  return (
    <div className="container" style={{ maxWidth: 840, paddingTop: 20, paddingBottom: 60 }}>
      <div className="fade-in">

        {/* ⚠️ Actionable Farmer Advisories Only */}
        {farmerWarnings.length > 0 && (
          <div className="warning-banner" style={{ marginBottom: 20 }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
              <span style={{ fontSize: 22, flexShrink: 0 }}>📢</span>
              <div style={{ flex: 1 }}>
                <strong style={{ fontSize: '0.95rem' }}>Practical Farm Advisory:</strong>
                <ul style={{ marginTop: 6, paddingLeft: 18 }}>
                  {farmerWarnings.map((w, i) => (
                    <li key={i} style={{ marginBottom: 4, fontSize: '0.875rem', lineHeight: 1.5 }}>{w}</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        )}

        {/* 🏆 Hero: Best Rotation Plan for Your Farm */}
        {best && (
          <div style={{
            background: 'linear-gradient(145deg, #14532d 0%, #166534 50%, #064e3b 100%)',
            borderRadius: 'var(--radius-xl)',
            padding: '28px 24px',
            color: 'white',
            marginBottom: 20,
            boxShadow: '0 12px 30px rgba(22, 101, 52, 0.25)',
          }}>
            {/* Header Badge & Title */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
              <span style={{
                background: 'rgba(255,255,255,0.2)',
                color: '#fef08a',
                padding: '4px 12px',
                borderRadius: 999,
                fontSize: '0.8rem',
                fontWeight: 700,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                backdropFilter: 'blur(4px)',
              }}>
                🏆 Recommended Plan #1
              </span>
              <span style={{ fontSize: '0.8rem', opacity: 0.8 }}>
                Location: {profile.attributes?.upazila ? String(profile.attributes.upazila) : 'Farm'} ({profile.area_ha} ha)
              </span>
            </div>

            <h1 style={{ fontSize: '1.6rem', color: 'white', marginBottom: 6, lineHeight: 1.3 }}>
              {bestCropNames.join(' ➔ ')}
            </h1>

            <p style={{ fontSize: '0.92rem', opacity: 0.9, lineHeight: 1.6, marginBottom: 20, maxWidth: 700 }}>
              {humanizeSummary(explanation.summary, bestCropNames)}
            </p>

            {/* 🗓️ Visual Seasonal Crop Journey */}
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, opacity: 0.8, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 10 }}>
                📅 Seasonal Planting Journey:
              </div>
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: 12,
              }}>
                {best.crop_ids.map((id, i) => {
                  const cropName = getCropName(id);
                  const visual = getCropVisual(cropName);
                  const seasonName = seasons[i] ? seasons[i].season : `Season ${i + 1}`;
                  const seasonMonths = i === 0 ? 'Nov – Feb (Winter)' : i === 1 ? 'Mar – Jun (Summer)' : 'Jul – Oct (Monsoon)';

                  return (
                    <div
                      key={i}
                      style={{
                        background: 'rgba(255, 255, 255, 0.1)',
                        border: '1px solid rgba(255, 255, 255, 0.2)',
                        borderRadius: 'var(--radius-md)',
                        padding: '14px 16px',
                        backdropFilter: 'blur(6px)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 8,
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: '0.75rem', opacity: 0.85, fontWeight: 600 }}>
                          {seasonName}
                        </span>
                        <span style={{ fontSize: 24 }}>{visual.icon}</span>
                      </div>
                      <div>
                        <div style={{ fontSize: '1.05rem', fontWeight: 800, color: 'white' }}>
                          {cropName}
                        </div>
                        <div style={{ fontSize: '0.75rem', opacity: 0.75 }}>
                          {seasonMonths}
                        </div>
                      </div>
                      <div style={{ marginTop: 'auto' }}>
                        <span style={{
                          background: 'rgba(255,255,255,0.2)',
                          color: '#dcfce7',
                          padding: '2px 8px',
                          borderRadius: 6,
                          fontSize: '0.7rem',
                          fontWeight: 600,
                          display: 'inline-block',
                        }}>
                          {visual.role}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* 📊 3 Direct Outcome Cards (Earnings, Water, Soil) */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: 12,
              background: 'rgba(0, 0, 0, 0.2)',
              borderRadius: 'var(--radius-lg)',
              padding: 16,
            }}>
              {/* Earnings */}
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8rem', opacity: 0.85, marginBottom: 2 }}>
                  <span>💵</span>
                  <span>Expected Farm Profit</span>
                </div>
                <div style={{ fontSize: '1.45rem', fontWeight: 900, color: '#86efac' }}>
                  {formatUSD(best.metrics.gross_margin ?? 0)}
                </div>
                <div style={{ fontSize: '0.75rem', opacity: 0.75, marginTop: 2 }}>
                  Net income across {profile.area_ha} hectares above seeds and operational expenses.
                </div>
              </div>

              {/* Water */}
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8rem', opacity: 0.85, marginBottom: 2 }}>
                  <span>💧</span>
                  <span>Total Water Need</span>
                </div>
                <div style={{ fontSize: '1.45rem', fontWeight: 900, color: '#bae6fd' }}>
                  {formatNumber(waterDemand)} m³
                </div>
                <div style={{ fontSize: '0.75rem', opacity: 0.75, marginTop: 2 }}>
                  {waterQuota >= waterDemand
                    ? 'Fully covered by your irrigation quota with water surplus to spare.'
                    : `Pump supplies ${formatNumber(waterQuota)} m³; monsoon rains cover the remaining need.`}
                </div>
              </div>

              {/* Soil */}
              {soilHealth && (
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8rem', opacity: 0.85, marginBottom: 2 }}>
                    <span>🌱</span>
                    <span>Soil Health Impact</span>
                  </div>
                  <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#fef08a' }}>
                    {soilHealth.stars}
                  </div>
                  <div style={{ fontSize: '0.8rem', fontWeight: 700, marginTop: 2 }}>
                    {soilHealth.label}
                  </div>
                  <div style={{ fontSize: '0.72rem', opacity: 0.75, marginTop: 2 }}>
                    {soilHealth.tip}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* 🌦️ Growing Season Conditions & Weather Snapshot */}
        <div className="card" style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h3 style={{ color: 'var(--green-800)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <span>🌦️</span>
              <span>Your Farm’s Seasonal Climate & Field Conditions</span>
            </h3>
            <span className="badge badge-stone" style={{ fontSize: '0.75rem' }}>NASA Satellite Data</span>
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: 10,
          }}>
            {seasons.map((s, i) => {
              const label = i === 0 ? '❄️ Rabi (Winter)' : i === 1 ? '☀️ Kharif-1 (Summer)' : '🌧️ Kharif-2 (Monsoon)';
              const weatherTag = i === 0 ? 'Dry & Mild' : i === 1 ? 'Warm & Early Rain' : 'Heavy Monsoon Rains';

              return (
                <div
                  key={i}
                  style={{
                    background: 'var(--stone-50)',
                    border: '1px solid var(--stone-200)',
                    borderRadius: 'var(--radius-md)',
                    padding: 12,
                  }}
                >
                  <div style={{ fontWeight: 700, fontSize: '0.85rem', color: 'var(--stone-800)', marginBottom: 2 }}>
                    {label}
                  </div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--green-800)', fontWeight: 600, marginBottom: 8 }}>
                    {weatherTag}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--stone-700)', display: 'flex', flexDirection: 'column', gap: 3 }}>
                    {s.mean_temp_c !== undefined && <div>🌡️ <strong>{s.mean_temp_c}°C</strong> avg temp</div>}
                    {s.precipitation_mm !== undefined && <div>🌧️ <strong>{Math.round(s.precipitation_mm)} mm</strong> rainfall</div>}
                  </div>
                </div>
              );
            })}

            {/* Soil Field Status card (only shows real non-empty values) */}
            <div style={{
              background: 'var(--stone-50)',
              border: '1px solid var(--stone-200)',
              borderRadius: 'var(--radius-md)',
              padding: 12,
            }}>
              <div style={{ fontWeight: 700, fontSize: '0.85rem', color: 'var(--stone-800)', marginBottom: 4 }}>
                🌱 Soil Profile
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--stone-700)', display: 'flex', flexDirection: 'column', gap: 4 }}>
                <div>Type: <strong>{profile.land_type ?? 'MHL'} Floodplain</strong></div>
                {soil?.texture ? <div>Texture: <strong>{soil.texture}</strong></div> : <div>Soil: <strong>Alluvial Loam</strong></div>}
                {soil?.ph ? (
                  <div>pH: <strong>{soil.ph}</strong> {soil.is_field_tested && <span className="badge badge-green" style={{ fontSize: '0.65rem' }}>Lab</span>}</div>
                ) : (
                  <div>Baseline: <strong>Regional Neutral Soil</strong></div>
                )}
                {soil?.organic_carbon_g_kg && <div>Organic Carbon: <strong>{soil.organic_carbon_g_kg} g/kg</strong></div>}
              </div>
            </div>
          </div>
        </div>

        {/* 🌟 Top Alternative Rotation Plans */}
        <div className="card" style={{ marginBottom: 20 }}>
          <div style={{ marginBottom: 14 }}>
            <h3 style={{ color: 'var(--green-800)' }}>
              🌟 Top Recommended Rotation Plans for You ({pareto.length})
            </h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--stone-500)', marginTop: 2 }}>
              Each plan is fully vetted and feasible. Choose the one that best fits your preference for profit, water saving, or soil restoration.
            </p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {pareto.map((seq, idx) => (
              <FarmerFriendlyPlanCard
                key={seq.sequence_id}
                seq={seq}
                index={idx + 1}
                isBest={seq.sequence_id === best?.sequence_id}
                seasons={seasons}
                profile={profile}
              />
            ))}
          </div>

          {/* Dominated combinations (collapsed and unobtrusive) */}
          {dominated.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <button
                className="btn-ghost"
                onClick={() => setShowAllSequences(!showAllSequences)}
                style={{ fontSize: '0.82rem', padding: '6px 0', color: 'var(--stone-500)' }}
              >
                {showAllSequences ? '▲ Hide other combinations' : `▼ View other tested options (${dominated.length} lower-performing rotations)`}
              </button>
              {showAllSequences && (
                <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <p style={{ fontSize: '0.8rem', color: 'var(--stone-500)' }}>
                    These crop sequences were evaluated and discarded because the recommended plans above produce strictly better profits, lower water consumption, or healthier soil.
                  </p>
                  {dominated.slice(0, 10).map((seq, idx) => (
                    <FarmerFriendlyPlanCard
                      key={seq.sequence_id}
                      seq={seq}
                      index={idx + 5}
                      isBest={false}
                      seasons={seasons}
                      profile={profile}
                      isDominated
                    />
                  ))}
                  {dominated.length > 10 && (
                    <p style={{ fontSize: '0.78rem', color: 'var(--stone-400)', fontStyle: 'italic' }}>
                      + {dominated.length - 10} additional inferior sequences evaluated and filtered out by optimizer.
                    </p>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* 💡 Why This Rotation Works (Direct Practical Advice) */}
        {Object.keys(sections).length > 0 && (
          <div className="card" style={{ marginBottom: 20 }}>
            <h3 style={{ color: 'var(--green-800)', marginBottom: 6 }}>
              💡 Why This Crop Sequence Works
            </h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--stone-500)', marginBottom: 12 }}>
              Practical agronomic reasons behind this crop combination:
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {Object.entries(sections)
                .filter(([key]) => key !== 'caveat')
                .map(([key, text]) => (
                  <div className="accordion-item" key={key}>
                    <button
                      className="accordion-trigger"
                      onClick={() => toggleSection(key)}
                      style={{ padding: '12px 0' }}
                    >
                      <span style={{ fontWeight: 700, fontSize: '0.92rem' }}>
                        {SECTION_LABELS[key] ?? key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                      </span>
                      <span style={{ color: 'var(--stone-400)', fontSize: 16 }}>
                        {openSections.has(key) ? '▲' : '▼'}
                      </span>
                    </button>
                    {openSections.has(key) && (
                      <div className="accordion-content" style={{ color: 'var(--stone-700)', lineHeight: 1.6 }}>
                        {cleanSectionText(text)}
                      </div>
                    )}
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* 📚 Research & Agricultural Sources */}
        {evidence.length > 0 && (
          <div className="card" style={{ marginBottom: 20 }}>
            <h3 style={{ color: 'var(--green-800)', marginBottom: 10, fontSize: '1rem' }}>
              📚 Agronomic Evidence & Guidelines
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {evidence.map(ev => (
                <div key={ev.source_id} style={{
                  borderLeft: '3px solid var(--green-400)',
                  paddingLeft: 12,
                  paddingTop: 2,
                  paddingBottom: 2,
                }}>
                  <div style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--stone-800)' }}>
                    {ev.url ? (
                      <a href={ev.url} target="_blank" rel="noreferrer" style={{ color: 'var(--sky-600)' }}>
                        {ev.title} ↗
                      </a>
                    ) : ev.title}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--stone-500)', marginTop: 2 }}>
                    {ev.claim}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 💬 Q&A Chat: Ask the Live AI Farm Advisor */}
        <div className="card" style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10, flexWrap: 'wrap', gap: 8 }}>
            <h3 style={{ color: 'var(--green-800)' }}>💬 Ask Questions About This Recommendation</h3>
            <span className="badge badge-green">⚡ Live Agronomic Advisor</span>
          </div>

          <p style={{ fontSize: '0.85rem', color: 'var(--stone-600)', marginBottom: 12 }}>
            Ask anything about crop timing, drought risks, water management, or fertilizer:
          </p>

          {/* Quick Question Pills */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 14 }}>
            {QA_SUGGESTIONS.map(q => (
              <button
                key={q}
                onClick={() => handleAskQuestion(q)}
                disabled={qaLoading}
                className="btn-ghost"
                style={{
                  padding: '6px 12px',
                  borderRadius: 999,
                  border: '1px solid var(--green-300)',
                  background: 'var(--green-50)',
                  color: 'var(--green-800)',
                  fontSize: '0.8rem',
                  fontWeight: 500,
                  cursor: qaLoading ? 'not-allowed' : 'pointer',
                  transition: 'all 0.15s',
                }}
              >
                {q}
              </button>
            ))}
          </div>

          {/* Chat Messages Log */}
          {qaMessages.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 14, maxHeight: 300, overflowY: 'auto' }}>
              {qaMessages.map((msg, idx) => (
                <div
                  key={idx}
                  style={{
                    alignSelf: msg.role === 'farmer' ? 'flex-end' : 'flex-start',
                    maxWidth: '85%',
                    padding: '10px 14px',
                    borderRadius: 12,
                    fontSize: '0.875rem',
                    lineHeight: 1.5,
                    whiteSpace: 'pre-wrap',
                    background: msg.role === 'farmer' ? 'var(--green-700)' : 'var(--stone-100)',
                    color: msg.role === 'farmer' ? 'white' : 'var(--stone-800)',
                  }}
                >
                  <div style={{ fontSize: '0.72rem', opacity: 0.8, marginBottom: 2, fontWeight: 700 }}>
                    {msg.role === 'farmer' ? 'You' : '🌾 Crop Advisor'}
                  </div>
                  {msg.content}
                </div>
              ))}
            </div>
          )}

          {/* Chat input */}
          <form
            onSubmit={e => {
              e.preventDefault();
              handleAskQuestion(qaInput);
            }}
            style={{ display: 'flex', gap: 8, alignItems: 'center' }}
          >
            <input
              type="text"
              value={qaInput}
              onChange={e => setQaInput(e.target.value)}
              placeholder="Ask a question (e.g. 'How much can I save if I use canal water?')..."
              disabled={qaLoading}
              style={{ flex: 1, fontSize: '16px' }}
            />
            <button
              type="submit"
              disabled={qaLoading || !qaInput.trim()}
              className="btn-primary"
              style={{ padding: '10px 20px', flexShrink: 0 }}
            >
              {qaLoading ? '...' : 'Ask ↵'}
            </button>
          </form>
        </div>

        {/* ℹ️ Optional Technical Notes for Model Calibration (Collapsed at very bottom) */}
        {technicalNotes.length > 0 && (
          <details style={{ marginBottom: 20 }}>
            <summary style={{
              cursor: 'pointer',
              fontSize: '0.78rem',
              color: 'var(--stone-400)',
              fontFamily: 'monospace',
              padding: '6px 0',
            }}>
              ℹ️ System Modeling & Calibration Notes ({technicalNotes.length}) →
            </summary>
            <ul style={{
              background: 'var(--stone-100)',
              padding: '12px 24px',
              borderRadius: 8,
              fontSize: '0.75rem',
              color: 'var(--stone-600)',
              lineHeight: 1.6,
              marginTop: 6,
            }}>
              {technicalNotes.map((n, i) => (
                <li key={i}>{n}</li>
              ))}
            </ul>
          </details>
        )}

        {/* Footer actions */}
        <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
          <button className="btn-secondary" onClick={onStartOver} style={{ padding: '10px 24px' }}>
            🌾 Start Over With New Farm
          </button>
        </div>

      </div>
    </div>
  );
}

// ---- Subcomponents ----

function FarmerFriendlyPlanCard({
  seq, index, isBest, seasons, profile, isDominated = false,
}: {
  seq: EvaluatedSequence;
  index: number;
  isBest: boolean;
  seasons: { season: string }[];
  profile: FarmerProfile;
  isDominated?: boolean;
}) {
  const cropNames = seq.crop_ids.map(getCropName);
  const soilInfo = formatSoilHealth(seq.metrics.soil_score ?? 0.2);

  return (
    <div style={{
      border: `2px solid ${isBest ? 'var(--green-500)' : isDominated ? 'var(--stone-200)' : 'var(--stone-300)'}`,
      borderRadius: 'var(--radius-md)',
      padding: '16px 18px',
      background: isBest ? 'var(--green-50)' : isDominated ? 'var(--stone-50)' : 'white',
      opacity: isDominated ? 0.75 : 1,
      transition: 'all 0.15s ease',
    }}>
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10, flexWrap: 'wrap', gap: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{
            background: isBest ? 'var(--green-600)' : 'var(--stone-200)',
            color: isBest ? 'white' : 'var(--stone-700)',
            padding: '2px 8px',
            borderRadius: 6,
            fontSize: '0.75rem',
            fontWeight: 700,
          }}>
            {isBest ? '🏆 Plan 1 (Best Match)' : `Plan ${index}`}
          </span>
          <span style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--stone-900)' }}>
            {cropNames.join(' ➔ ')}
          </span>
        </div>
      </div>

      {/* Visual Season Steps */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        {seq.crop_ids.map((id, i) => {
          const name = getCropName(id);
          const visual = getCropVisual(name);
          const seasonName = seasons[i] ? seasons[i].season : `S${i + 1}`;

          return (
            <div key={i} style={{
              background: 'white',
              border: '1px solid var(--stone-200)',
              borderRadius: 6,
              padding: '4px 10px',
              fontSize: '0.8rem',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}>
              <span style={{ fontSize: 15 }}>{visual.icon}</span>
              <span style={{ color: 'var(--stone-500)', fontSize: '0.75rem' }}>{seasonName}:</span>
              <strong style={{ color: 'var(--stone-800)' }}>{name}</strong>
            </div>
          );
        })}
      </div>

      {/* Key Metrics in Farmer Language */}
      <div style={{
        display: 'flex',
        gap: 18,
        flexWrap: 'wrap',
        paddingTop: 8,
        borderTop: '1px solid var(--stone-200)',
      }}>
        <div>
          <div style={{ fontSize: '0.72rem', color: 'var(--stone-500)', fontWeight: 600 }}>💵 Expected Profit</div>
          <div style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--green-800)' }}>
            {formatUSD(seq.metrics.gross_margin ?? 0)}
          </div>
        </div>

        <div>
          <div style={{ fontSize: '0.72rem', color: 'var(--stone-500)', fontWeight: 600 }}>💧 Water Needed</div>
          <div style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--stone-800)' }}>
            {formatNumber(seq.metrics.water_m3 ?? 0)} m³
          </div>
        </div>

        <div>
          <div style={{ fontSize: '0.72rem', color: 'var(--stone-500)', fontWeight: 600 }}>🌱 Soil Fertility</div>
          <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--stone-800)' }}>
            {soilInfo.label}
          </div>
        </div>
      </div>
    </div>
  );
}

function cleanSectionText(raw: string): string {
  // Strip cryptic sequences like "seq-053" or "(21 -> 99 -> 91)"
  return raw
    .replace(/seq-\w+/gi, 'this plan')
    .replace(/\b\d+\s*->\s*\d+\s*->\s*\d+\b/g, '')
    .replace(/m3\b/g, 'm³');
}

const SECTION_LABELS: Record<string, string> = {
  water: '💧 Water Efficiency & Quota Balance',
  soil: '🌱 Natural Soil Regeneration & Nitrogen Balance',
  rotation_risk: '🛡️ Crop Disease & Pest Interruption',
  margin: '💵 Economic Earnings Potential',
  climate: '🌦️ Climate & Weather Compatibility',
};

const QA_SUGGESTIONS = [
  'Why this rotation for my farm?',
  'What if irrigation water runs low?',
  'Why shouldn\'t I plant rice in all 3 seasons?',
  'Which crop has the lowest market risk?',
];
