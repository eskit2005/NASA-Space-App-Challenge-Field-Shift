import { useState } from 'react';
import type { FarmerProfile, LandType } from '../types/api';
import { formatUSD, formatNumber } from '../utils/helpers';

interface ReviewScreenProps {
  profile: FarmerProfile;
  onEdit: () => void;
  onSubmit: () => void;
  onUpdateProfile?: (updated: FarmerProfile) => void;
}

const LAND_TYPE_OPTIONS: { value: LandType; label: string; desc: string }[] = [
  { value: 'HL', label: 'Highland (HL)', desc: 'Above normal monsoon flood (0 cm)' },
  { value: 'MHL', label: 'Medium Highland (MHL)', desc: 'Flooded 30–90 cm during monsoon' },
  { value: 'MLL', label: 'Medium Lowland (MLL)', desc: 'Flooded 90–180 cm during monsoon' },
  { value: 'LL', label: 'Lowland (LL)', desc: 'Flooded 180–300 cm during monsoon' },
  { value: 'VLL', label: 'Very Lowland (VLL)', desc: 'Deep water flooding (> 300 cm)' },
];

const IRRIGATION_METHOD_OPTIONS = [
  { value: 'tube_well', label: '💧 Groundwater Tube Well', desc: 'Standard diesel or electric deep/shallow tube well' },
  { value: 'canal', label: '🌊 Canal / Surface Water Scheme', desc: 'River or canal gravity / pump lift supply' },
  { value: 'pond', label: '🏞️ Farm Pond / Reservoir', desc: 'On-farm rainwater or seepage collection pond' },
  { value: 'rainfed', label: '🌧️ Rainfed Only', desc: 'Monsoon rainfall dependent, no active irrigation pump' },
  { value: 'drip', label: '💧 Drip Irrigation', desc: 'High-efficiency piped micro-irrigation' },
  { value: 'sprinkler', label: '💦 Sprinkler Irrigation', desc: 'Pressurized overhead spray distribution' },
];

export default function ReviewScreen({ profile, onEdit, onSubmit, onUpdateProfile }: ReviewScreenProps) {
  const pct = (v: number | undefined) => {
    if (v === undefined || v === null || isNaN(v)) return '0%';
    return `${Math.round(v * 100)}%`;
  };

  const attrs = profile.attributes ?? {};
  const priorities = {
    gross_margin: profile.priorities?.gross_margin ?? 0.5,
    water_m3: profile.priorities?.water_m3 ?? 0.3,
    soil_score: profile.priorities?.soil_score ?? 0.2,
  };

  // Inline editing states
  const [editingField, setEditingField] = useState<string | null>(null);
  const [tempPh, setTempPh] = useState<string>(profile.soil_overrides?.ph?.toString() ?? '6.5');
  const [tempMethod, setTempMethod] = useState<string>(
    attrs.irrigation_method ? String(attrs.irrigation_method) : 'tube_well'
  );
  const [tempArea, setTempArea] = useState<string>(profile.area_ha?.toString() ?? '10');
  const [tempBudget, setTempBudget] = useState<string>(profile.budget_usd?.toString() ?? '5000');
  const [tempWater, setTempWater] = useState<string>(profile.irrigation_quota_m3?.toString() ?? '45000');
  const [tempLandType, setTempLandType] = useState<LandType>(profile.land_type ?? 'MHL');

  function saveSoilPh(newPh: number | null) {
    if (!onUpdateProfile) return;
    const soil = { ...(profile.soil_overrides || {}) };
    if (newPh === null || isNaN(newPh)) {
      delete soil.ph;
    } else {
      soil.ph = newPh;
    }
    onUpdateProfile({
      ...profile,
      soil_overrides: soil,
    });
    setEditingField(null);
  }

  function saveIrrigationMethod(method: string) {
    if (!onUpdateProfile) return;
    onUpdateProfile({
      ...profile,
      attributes: {
        ...(profile.attributes || {}),
        irrigation_method: method,
      },
    });
    setEditingField(null);
  }

  function saveArea() {
    const val = parseFloat(tempArea);
    if (!isNaN(val) && val > 0 && onUpdateProfile) {
      onUpdateProfile({ ...profile, area_ha: val });
    }
    setEditingField(null);
  }

  function saveBudget() {
    const val = parseFloat(tempBudget);
    if (!isNaN(val) && val >= 0 && onUpdateProfile) {
      onUpdateProfile({ ...profile, budget_usd: val });
    }
    setEditingField(null);
  }

  function saveWater() {
    const val = parseFloat(tempWater);
    if (!isNaN(val) && val >= 0 && onUpdateProfile) {
      onUpdateProfile({ ...profile, irrigation_quota_m3: val });
    }
    setEditingField(null);
  }

  function saveLandType(type: LandType) {
    if (onUpdateProfile) {
      onUpdateProfile({ ...profile, land_type: type });
    }
    setEditingField(null);
  }

  function formatMethodLabel(raw: unknown) {
    if (!raw) return 'Standard Groundwater Tube Well (Default)';
    const found = IRRIGATION_METHOD_OPTIONS.find(o => o.value === raw);
    if (found) return found.label;
    return String(raw).replace(/_/g, ' ');
  }

  return (
    <div className="container" style={{ maxWidth: 640, paddingTop: 32 }}>
      <div className="fade-in">
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div style={{ fontSize: 48, marginBottom: 8 }}>📋</div>
          <h1 style={{ fontSize: '1.5rem', marginBottom: 6 }}>Review Your Farm Details</h1>
          <p style={{ color: 'var(--stone-500)', fontSize: '0.9rem' }}>
            Check everything or adjust details before calculating optimal crop rotations.
          </p>
        </div>

        {/* 🌾 Farm Information Card */}
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h3 style={{ color: 'var(--green-800)' }}>🌾 Farm Information</h3>
            <button className="btn-ghost" onClick={onEdit} style={{ fontSize: '0.8rem' }}>💬 Open Chat Assistant</button>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--stone-100)' }}>
            <span style={{ fontSize: '0.875rem', color: 'var(--stone-500)', fontWeight: 500, minWidth: 140 }}>Farm ID</span>
            <span style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--stone-900)' }}>{profile.farm_id}</span>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--stone-100)' }}>
            <span style={{ fontSize: '0.875rem', color: 'var(--stone-500)', fontWeight: 500, minWidth: 140 }}>Location</span>
            <span style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--stone-900)' }}>
              {attrs.upazila ? `${attrs.upazila}, ${attrs.district || ''} (${profile.location.latitude.toFixed(4)}°N, ${profile.location.longitude.toFixed(4)}°E)` : `${profile.location.latitude.toFixed(4)}°N, ${profile.location.longitude.toFixed(4)}°E`}
            </span>
          </div>

          {/* Farm Size row with inline edit */}
          <div style={{ padding: '10px 0', borderBottom: '1px solid var(--stone-100)' }}>
            {editingField === 'area_ha' ? (
              <div style={{ background: 'var(--stone-50)', padding: 12, borderRadius: 8 }}>
                <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--stone-700)', display: 'block', marginBottom: 4 }}>
                  Farm Size in Hectares:
                </label>
                <div style={{ display: 'flex', gap: 8 }}>
                  <input
                    type="number"
                    step="0.1"
                    min="0.1"
                    value={tempArea}
                    onChange={e => setTempArea(e.target.value)}
                    style={{ flex: 1, padding: '6px 10px', fontSize: '0.9rem' }}
                  />
                  <button className="btn-primary" onClick={saveArea} style={{ padding: '6px 14px', fontSize: '0.85rem' }}>✓ Save</button>
                  <button className="btn-ghost" onClick={() => setEditingField(null)} style={{ padding: '6px 10px', fontSize: '0.85rem' }}>Cancel</button>
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.875rem', color: 'var(--stone-500)', fontWeight: 500, minWidth: 140 }}>Farm Size</span>
                <span style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--stone-900)', flex: 1 }}>{formatNumber(profile.area_ha, 1)} hectares</span>
                {onUpdateProfile && (
                  <button className="btn-ghost" onClick={() => { setTempArea(profile.area_ha.toString()); setEditingField('area_ha'); }} style={{ padding: '2px 8px', fontSize: '0.8rem' }}>Edit</button>
                )}
              </div>
            )}
          </div>

          {/* Land Type row with inline edit */}
          <div style={{ padding: '10px 0', borderBottom: '1px solid var(--stone-100)' }}>
            {editingField === 'land_type' ? (
              <div style={{ background: 'var(--stone-50)', padding: 12, borderRadius: 8 }}>
                <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--stone-700)', display: 'block', marginBottom: 6 }}>
                  Monsoon Flood Depth (Land Type):
                </label>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 8 }}>
                  {LAND_TYPE_OPTIONS.map(opt => (
                    <label key={opt.value} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.85rem', cursor: 'pointer' }}>
                      <input
                        type="radio"
                        name="land_type"
                        value={opt.value}
                        checked={tempLandType === opt.value}
                        onChange={() => setTempLandType(opt.value)}
                      />
                      <span style={{ fontWeight: 600 }}>{opt.label}</span>
                      <span style={{ color: 'var(--stone-500)', fontSize: '0.78rem' }}>({opt.desc})</span>
                    </label>
                  ))}
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button className="btn-primary" onClick={() => saveLandType(tempLandType)} style={{ padding: '6px 14px', fontSize: '0.85rem' }}>✓ Save</button>
                  <button className="btn-ghost" onClick={() => setEditingField(null)} style={{ padding: '6px 10px', fontSize: '0.85rem' }}>Cancel</button>
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.875rem', color: 'var(--stone-500)', fontWeight: 500, minWidth: 140 }}>Land Type</span>
                <span style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--stone-900)', flex: 1 }}>
                  {profile.land_type ? `${profile.land_type} (${profile.land_type === 'HL' ? 'Highland' : profile.land_type === 'MHL' ? 'Medium Highland' : profile.land_type === 'MLL' ? 'Medium Lowland' : profile.land_type === 'LL' ? 'Lowland' : 'Very Lowland'})` : 'Medium Highland (MHL)'}
                </span>
                {onUpdateProfile && (
                  <button className="btn-ghost" onClick={() => { setTempLandType(profile.land_type ?? 'MHL'); setEditingField('land_type'); }} style={{ padding: '2px 8px', fontSize: '0.8rem' }}>Edit</button>
                )}
              </div>
            )}
          </div>

          {/* Season Budget row with inline edit */}
          <div style={{ padding: '10px 0', borderBottom: '1px solid var(--stone-100)' }}>
            {editingField === 'budget_usd' ? (
              <div style={{ background: 'var(--stone-50)', padding: 12, borderRadius: 8 }}>
                <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--stone-700)', display: 'block', marginBottom: 4 }}>
                  Season Budget (USD):
                </label>
                <div style={{ display: 'flex', gap: 8 }}>
                  <input
                    type="number"
                    step="100"
                    min="0"
                    value={tempBudget}
                    onChange={e => setTempBudget(e.target.value)}
                    style={{ flex: 1, padding: '6px 10px', fontSize: '0.9rem' }}
                  />
                  <button className="btn-primary" onClick={saveBudget} style={{ padding: '6px 14px', fontSize: '0.85rem' }}>✓ Save</button>
                  <button className="btn-ghost" onClick={() => setEditingField(null)} style={{ padding: '6px 10px', fontSize: '0.85rem' }}>Cancel</button>
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.875rem', color: 'var(--stone-500)', fontWeight: 500, minWidth: 140 }}>Season Budget</span>
                <span style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--stone-900)', flex: 1 }}>{formatUSD(profile.budget_usd)}</span>
                {onUpdateProfile && (
                  <button className="btn-ghost" onClick={() => { setTempBudget(profile.budget_usd.toString()); setEditingField('budget_usd'); }} style={{ padding: '2px 8px', fontSize: '0.8rem' }}>Edit</button>
                )}
              </div>
            )}
          </div>

          {/* Water Quota row with inline edit */}
          <div style={{ padding: '10px 0' }}>
            {editingField === 'irrigation_quota_m3' ? (
              <div style={{ background: 'var(--stone-50)', padding: 12, borderRadius: 8 }}>
                <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--stone-700)', display: 'block', marginBottom: 4 }}>
                  Irrigation Quota (m³ / season):
                </label>
                <div style={{ display: 'flex', gap: 8 }}>
                  <input
                    type="number"
                    step="1000"
                    min="0"
                    value={tempWater}
                    onChange={e => setTempWater(e.target.value)}
                    style={{ flex: 1, padding: '6px 10px', fontSize: '0.9rem' }}
                  />
                  <button className="btn-primary" onClick={saveWater} style={{ padding: '6px 14px', fontSize: '0.85rem' }}>✓ Save</button>
                  <button className="btn-ghost" onClick={() => setEditingField(null)} style={{ padding: '6px 10px', fontSize: '0.85rem' }}>Cancel</button>
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.875rem', color: 'var(--stone-500)', fontWeight: 500, minWidth: 140 }}>Water Quota</span>
                <span style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--stone-900)', flex: 1 }}>{formatNumber(profile.irrigation_quota_m3)} m³ / season</span>
                {onUpdateProfile && (
                  <button className="btn-ghost" onClick={() => { setTempWater(profile.irrigation_quota_m3.toString()); setEditingField('irrigation_quota_m3'); }} style={{ padding: '2px 8px', fontSize: '0.8rem' }}>Edit</button>
                )}
              </div>
            )}
          </div>
        </div>

        {/* 🎯 Priorities Card */}
        {priorities && (
          <div className="card" style={{ marginBottom: 16 }}>
            <h3 style={{ color: 'var(--green-800)', marginBottom: 12 }}>🎯 Your Priorities</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[
                { label: '💵 Earning Potential', value: priorities.gross_margin },
                { label: '💧 Water Saving', value: priorities.water_m3 },
                { label: '🌱 Soil Health', value: priorities.soil_score },
              ].map(({ label, value }) => (
                <div key={label}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontSize: '0.875rem', fontWeight: 600 }}>{label}</span>
                    <span style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--green-700)' }}>{pct(value)}</span>
                  </div>
                  <div style={{ background: 'var(--stone-200)', borderRadius: 999, height: 6 }}>
                    <div style={{
                      height: '100%',
                      background: 'var(--green-500)',
                      borderRadius: 999,
                      width: pct(value),
                      transition: 'width 0.3s',
                    }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 🧪 Soil Data & Lab Test Card with Inline Quick Editor */}
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h3 style={{ color: 'var(--green-800)' }}>🧪 Soil Data Source & pH</h3>
            {profile.soil_overrides?.ph !== undefined ? (
              <span className="badge badge-green">Lab Verified</span>
            ) : (
              <span className="badge badge-stone">Satellite Baseline</span>
            )}
          </div>

          {editingField === 'soil_ph' ? (
            <div style={{ background: 'var(--stone-50)', padding: 14, borderRadius: 8, border: '1px solid var(--stone-200)' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--stone-800)', display: 'block', marginBottom: 6 }}>
                Field Lab-Measured Soil pH (0 – 14):
              </label>
              <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
                <input
                  type="number"
                  step="0.1"
                  min="3.0"
                  max="10.0"
                  placeholder="e.g. 6.5"
                  value={tempPh}
                  onChange={e => setTempPh(e.target.value)}
                  style={{ flex: 1, padding: '8px 12px', fontSize: '0.95rem' }}
                />
                <button
                  className="btn-primary"
                  onClick={() => saveSoilPh(parseFloat(tempPh))}
                  style={{ padding: '8px 16px', fontSize: '0.85rem' }}
                >
                  ✓ Save pH
                </button>
                <button
                  className="btn-ghost"
                  onClick={() => setEditingField(null)}
                  style={{ padding: '8px 12px', fontSize: '0.85rem' }}
                >
                  Cancel
                </button>
              </div>

              {/* Quick pH preset pills */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center', marginBottom: 10 }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--stone-500)', fontWeight: 600 }}>Quick presets:</span>
                {[
                  { label: '5.5 (Acidic)', val: '5.5' },
                  { label: '6.2 (Mild Acidic)', val: '6.2' },
                  { label: '6.5 (Neutral Optimal)', val: '6.5' },
                  { label: '7.0 (Neutral)', val: '7.0' },
                  { label: '7.5 (Slightly Alkaline)', val: '7.5' },
                ].map(p => (
                  <button
                    key={p.val}
                    type="button"
                    className="btn-ghost"
                    onClick={() => setTempPh(p.val)}
                    style={{
                      border: '1px solid var(--stone-300)',
                      background: 'white',
                      padding: '2px 8px',
                      borderRadius: 999,
                      fontSize: '0.75rem',
                    }}
                  >
                    {p.label}
                  </button>
                ))}
              </div>

              {profile.soil_overrides?.ph !== undefined && (
                <button
                  type="button"
                  className="btn-ghost"
                  onClick={() => saveSoilPh(null)}
                  style={{
                    color: 'var(--amber-700)',
                    fontSize: '0.78rem',
                    padding: '4px 8px',
                    border: '1px dashed var(--amber-400)',
                    borderRadius: 6,
                  }}
                >
                  🔄 Reset to Automated Satellite Baseline (Remove Lab Override)
                </button>
              )}
            </div>
          ) : (
            <div>
              {profile.soil_overrides?.ph !== undefined ? (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--stone-100)' }}>
                    <span style={{ fontSize: '0.875rem', color: 'var(--stone-500)', fontWeight: 500, minWidth: 140 }}>Soil pH</span>
                    <span style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--green-800)', flex: 1 }}>
                      {profile.soil_overrides.ph} (Field-Tested Lab Override)
                    </span>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button
                        className="btn-ghost"
                        onClick={() => {
                          setTempPh(profile.soil_overrides?.ph?.toString() ?? '6.5');
                          setEditingField('soil_ph');
                        }}
                        style={{ padding: '2px 8px', fontSize: '0.8rem' }}
                      >
                        ✏️ Edit pH
                      </button>
                      <button
                        className="btn-ghost"
                        onClick={() => saveSoilPh(null)}
                        style={{ padding: '2px 8px', fontSize: '0.78rem', color: 'var(--stone-500)' }}
                      >
                        🔄 Reset
                      </button>
                    </div>
                  </div>
                  <p style={{ fontSize: '0.78rem', color: 'var(--stone-500)', marginTop: 8 }}>
                    Your verified lab pH overrides the satellite baseline for higher precision in crop soil compatibility scoring.
                  </p>
                </div>
              ) : (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--stone-100)' }}>
                    <span style={{ fontSize: '0.875rem', color: 'var(--stone-500)', fontWeight: 500, minWidth: 140 }}>Measurement Source</span>
                    <span style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--stone-800)', flex: 1 }}>
                      Automated Satellite Baseline (ISRIC SoilGrids 250m)
                    </span>
                    <button
                      className="btn-ghost"
                      onClick={() => {
                        setTempPh('6.5');
                        setEditingField('soil_ph');
                      }}
                      style={{ padding: '2px 10px', fontSize: '0.8rem', border: '1px solid var(--green-600)', color: 'var(--green-800)', background: 'var(--green-50)' }}
                    >
                      ✏️ Add Lab Test pH
                    </button>
                  </div>
                  <p style={{ fontSize: '0.78rem', color: 'var(--stone-500)', marginTop: 8 }}>
                    No manual soil lab test provided. The optimizer will automatically use satellite SoilGrids observations for pH, clay content, and organic carbon.
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* 📝 Additional Details Card (District & Irrigation Method) with Inline Quick Editor */}
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h3 style={{ color: 'var(--green-800)' }}>📝 Additional Details</h3>
          </div>

          {attrs.district && (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--stone-100)' }}>
              <span style={{ fontSize: '0.875rem', color: 'var(--stone-500)', fontWeight: 500, minWidth: 140 }}>District</span>
              <span style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--stone-900)' }}>{String(attrs.district)}</span>
            </div>
          )}

          {/* Irrigation Method with inline editor */}
          <div style={{ padding: '10px 0' }}>
            {editingField === 'irrigation_method' ? (
              <div style={{ background: 'var(--stone-50)', padding: 14, borderRadius: 8, border: '1px solid var(--stone-200)' }}>
                <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--stone-800)', display: 'block', marginBottom: 8 }}>
                  Select Farm Irrigation Method:
                </label>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 12 }}>
                  {IRRIGATION_METHOD_OPTIONS.map(opt => (
                    <label
                      key={opt.value}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 10,
                        padding: '6px 10px',
                        background: tempMethod === opt.value ? 'var(--green-50)' : 'white',
                        border: `1px solid ${tempMethod === opt.value ? 'var(--green-600)' : 'var(--stone-200)'}`,
                        borderRadius: 6,
                        cursor: 'pointer',
                        fontSize: '0.85rem',
                      }}
                    >
                      <input
                        type="radio"
                        name="irrigation_method"
                        value={opt.value}
                        checked={tempMethod === opt.value}
                        onChange={() => setTempMethod(opt.value)}
                      />
                      <div>
                        <div style={{ fontWeight: 600, color: 'var(--stone-800)' }}>{opt.label}</div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--stone-500)' }}>{opt.desc}</div>
                      </div>
                    </label>
                  ))}
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    className="btn-primary"
                    onClick={() => saveIrrigationMethod(tempMethod)}
                    style={{ padding: '6px 16px', fontSize: '0.85rem' }}
                  >
                    ✓ Save Method
                  </button>
                  <button
                    className="btn-ghost"
                    onClick={() => setEditingField(null)}
                    style={{ padding: '6px 12px', fontSize: '0.85rem' }}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.875rem', color: 'var(--stone-500)', fontWeight: 500, minWidth: 140 }}>Irrigation Method</span>
                <span style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--stone-900)', flex: 1 }}>
                  {formatMethodLabel(attrs.irrigation_method)}
                </span>
                <button
                  className="btn-ghost"
                  onClick={() => {
                    setTempMethod(attrs.irrigation_method ? String(attrs.irrigation_method) : 'tube_well');
                    setEditingField('irrigation_method');
                  }}
                  style={{ padding: '2px 8px', fontSize: '0.8rem' }}
                >
                  ✏️ Edit Method
                </button>
              </div>
            )}
          </div>
        </div>

        {/* What will be sent JSON preview */}
        <details style={{ marginBottom: 20 }}>
          <summary style={{
            cursor: 'pointer',
            fontSize: '0.8rem',
            color: 'var(--stone-400)',
            fontFamily: 'monospace',
            userSelect: 'none',
            padding: '8px 0',
          }}>
            View raw JSON that will be sent to optimizer →
          </summary>
          <pre style={{
            background: 'var(--stone-900)',
            color: '#86efac',
            padding: 16,
            borderRadius: 10,
            fontSize: '0.75rem',
            lineHeight: 1.6,
            overflow: 'auto',
            marginTop: 8,
          }}>
            {JSON.stringify(profile, null, 2)}
          </pre>
        </details>

        <div className="btn-responsive-group" style={{ display: 'flex', gap: 12 }}>
          <button className="btn-secondary" onClick={onEdit} style={{ flex: 1, justifyContent: 'center' }}>
            💬 Return to Chat Assistant
          </button>
          <button className="btn-primary" onClick={onSubmit} style={{ flex: 2, justifyContent: 'center' }}>
            🚀 Get My Recommendations
          </button>
        </div>
      </div>
    </div>
  );
}
