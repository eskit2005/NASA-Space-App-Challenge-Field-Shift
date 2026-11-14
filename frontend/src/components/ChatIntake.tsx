import { useState } from 'react';
import type { FarmerProfile, LandType, Priorities, UpazilaPlace } from '../types/api';
import UpazilaPicker from './UpazilaPicker';
import ConversationalChat from './ConversationalChat';

interface ChatIntakeProps {
  initialProfile: FarmerProfile | null;
  isMockMode: boolean;
  onComplete: (profile: FarmerProfile) => void;
}

interface FormState {
  latitude: string;
  longitude: string;
  upazila: string;
  district: string;
  area_ha: string;
  land_type: LandType;
  budget_usd: string;
  irrigation_quota_m3: string;
  priority_gross_margin: number;
  priority_water: number;
  priority_soil: number;
  has_soil_test: boolean | null;
  soil_ph: string;
  irrigation_method: string;
}

type StepId = 1 | 2 | 3 | 4 | 5 | 6 | 7;

const TOTAL_STEPS = 7;

function normalise(gm: number, w: number, s: number): Priorities {
  const sum = gm + w + s;
  if (sum === 0) return { gross_margin: 1 / 3, water_m3: 1 / 3, soil_score: 1 / 3 };
  return {
    gross_margin: +(gm / sum).toFixed(4),
    water_m3: +(w / sum).toFixed(4),
    soil_score: +(s / sum).toFixed(4),
  };
}

function generateFarmId(): string {
  return `farm-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
}

const IRRIGATION_METHODS = [
  'tube_well', 'canal', 'drip', 'sprinkler', 'flood', 'rainfed', 'other',
];

const LAND_TYPE_OPTIONS: { value: LandType; label: string; desc: string }[] = [
  { value: 'HL', label: 'Highland (HL)', desc: 'Above normal monsoon flood level (0 cm depth)' },
  { value: 'MHL', label: 'Medium Highland (MHL) — Recommended', desc: 'Flooded up to 30–90 cm during monsoon' },
  { value: 'MLL', label: 'Medium Lowland (MLL)', desc: 'Flooded 90–180 cm during monsoon' },
  { value: 'LL', label: 'Lowland (LL)', desc: 'Flooded 180–300 cm during monsoon' },
  { value: 'VLL', label: 'Very Lowland (VLL)', desc: 'Deep water flooding (> 300 cm)' },
];

export default function ChatIntake({ initialProfile, isMockMode, onComplete }: ChatIntakeProps) {
  const [mode, setMode] = useState<'form' | 'chat'>('form');
  const [step, setStep] = useState<StepId>(1);
  const [farmId] = useState<string>(initialProfile?.farm_id ?? generateFarmId());
  const [errors, setErrors] = useState<Record<string, string>>({});

  const [form, setForm] = useState<FormState>(() => ({
    latitude: initialProfile?.location.latitude?.toString() ?? '24.7145',
    longitude: initialProfile?.location.longitude?.toString() ?? '88.9974',
    upazila: (initialProfile?.attributes?.upazila as string) ?? 'Raninagar',
    district: (initialProfile?.attributes?.district as string) ?? 'Naogaon',
    area_ha: initialProfile?.area_ha?.toString() ?? '',
    land_type: (initialProfile?.land_type as LandType) ?? 'MHL',
    budget_usd: initialProfile?.budget_usd?.toString() ?? '',
    irrigation_quota_m3: initialProfile?.irrigation_quota_m3?.toString() ?? '',
    priority_gross_margin: initialProfile?.priorities?.gross_margin ?? 0.5,
    priority_water: initialProfile?.priorities?.water_m3 ?? 0.3,
    priority_soil: initialProfile?.priorities?.soil_score ?? 0.2,
    has_soil_test: initialProfile?.soil_overrides ? true : null,
    soil_ph: initialProfile?.soil_overrides?.ph?.toString() ?? '',
    irrigation_method: (initialProfile?.attributes?.irrigation_method as string) ?? '',
  }));

  function set(field: keyof FormState, value: FormState[keyof FormState]) {
    setForm(f => ({ ...f, [field]: value }));
    setErrors(e => { const n = { ...e }; delete n[field as string]; return n; });
  }

  function validateStep(s: StepId): Record<string, string> {
    const e: Record<string, string> = {};
    if (s === 1) {
      const lat = parseFloat(form.latitude);
      const lon = parseFloat(form.longitude);
      if (!form.latitude || isNaN(lat) || lat < -90 || lat > 90) e.latitude = 'Please select a valid upazila or coordinates (−90 to 90)';
      if (!form.longitude || isNaN(lon) || lon < -180 || lon > 180) e.longitude = 'Enter a valid longitude (−180 to 180)';
    }
    if (s === 2) {
      const a = parseFloat(form.area_ha);
      if (!form.area_ha || isNaN(a) || a <= 0) e.area_ha = 'Enter your farm size in hectares (must be > 0)';
    }
    if (s === 3) {
      const b = parseFloat(form.budget_usd);
      if (!form.budget_usd || isNaN(b) || b < 0) e.budget_usd = 'Enter your seasonal budget in USD (0 or more)';
    }
    if (s === 4) {
      const q = parseFloat(form.irrigation_quota_m3);
      if (!form.irrigation_quota_m3 || isNaN(q) || q < 0) e.irrigation_quota_m3 = 'Enter your water quota in m³ (0 or more)';
    }
    if (s === 6 && form.has_soil_test === true) {
      const ph = parseFloat(form.soil_ph);
      if (!form.soil_ph || isNaN(ph) || ph < 0 || ph > 14) e.soil_ph = 'Enter a valid pH (0 to 14)';
    }
    return e;
  }

  function handleNext() {
    const e = validateStep(step);
    if (Object.keys(e).length > 0) { setErrors(e); return; }

    if (step < TOTAL_STEPS) {
      setStep((step + 1) as StepId);
    } else {
      buildAndSubmit();
    }
  }

  function handleSkip() {
    if (step < TOTAL_STEPS) setStep((step + 1) as StepId);
    else buildAndSubmit();
  }

  function handleBack() {
    if (step > 1) setStep((step - 1) as StepId);
  }

  function buildAndSubmit() {
    const priorities = normalise(
      form.priority_gross_margin,
      form.priority_water,
      form.priority_soil,
    );

    const profile: FarmerProfile = {
      farm_id: farmId,
      location: { latitude: parseFloat(form.latitude), longitude: parseFloat(form.longitude) },
      area_ha: parseFloat(form.area_ha),
      budget_usd: parseFloat(form.budget_usd),
      irrigation_quota_m3: parseFloat(form.irrigation_quota_m3),
      land_type: form.land_type,
      priorities,
    };

    if (form.has_soil_test && form.soil_ph) {
      profile.soil_overrides = { ph: parseFloat(form.soil_ph) };
    }

    const attrs: Record<string, string> = {};
    if (form.upazila.trim()) attrs.upazila = form.upazila.trim();
    if (form.district.trim()) attrs.district = form.district.trim();
    if (form.irrigation_method.trim()) attrs.irrigation_method = form.irrigation_method.trim();
    if (Object.keys(attrs).length > 0) profile.attributes = attrs;

    onComplete(profile);
  }

  const skippable = step >= 6;
  const isLastStep = step === TOTAL_STEPS;
  const priorityTotal = form.priority_gross_margin + form.priority_water + form.priority_soil;

  return (
    <div className="container" style={{ maxWidth: 640, paddingTop: 20 }}>
      {/* Mode Switch Tabs */}
      <div style={{
        display: 'flex',
        background: 'var(--stone-200)',
        borderRadius: 'var(--radius-md)',
        padding: 4,
        marginBottom: 24,
      }}>
        <button
          onClick={() => setMode('form')}
          style={{
            flex: 1,
            padding: '8px 10px',
            borderRadius: 8,
            border: 'none',
            background: mode === 'form' ? 'white' : 'transparent',
            color: mode === 'form' ? 'var(--green-800)' : 'var(--stone-600)',
            fontWeight: 700,
            fontSize: 'clamp(0.78rem, 2.5vw, 0.9rem)',
            cursor: 'pointer',
            boxShadow: mode === 'form' ? 'var(--shadow-sm)' : 'none',
            transition: 'all 0.15s',
            whiteSpace: 'nowrap',
          }}
        >
          📋 Guided Form Wizard
        </button>
        <button
          onClick={() => setMode('chat')}
          style={{
            flex: 1,
            padding: '8px 10px',
            borderRadius: 8,
            border: 'none',
            background: mode === 'chat' ? 'white' : 'transparent',
            color: mode === 'chat' ? 'var(--green-800)' : 'var(--stone-600)',
            fontWeight: 700,
            fontSize: 'clamp(0.78rem, 2.5vw, 0.9rem)',
            cursor: 'pointer',
            boxShadow: mode === 'chat' ? 'var(--shadow-sm)' : 'none',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 6,
            transition: 'all 0.15s',
            whiteSpace: 'nowrap',
          }}
        >
          <span>💬 Conversational AI Chat</span>
          <span className="badge badge-sky" style={{ fontSize: '0.65rem', padding: '2px 6px' }}>S0 AI</span>
        </button>
      </div>

      {mode === 'chat' ? (
        <div className="card slide-up">
          <div style={{ marginBottom: 16 }}>
            <h2 style={{ fontSize: '1.2rem', marginBottom: 4, color: 'var(--green-800)' }}>
              💬 AI Farm Intake Assistant
            </h2>
            <p style={{ color: 'var(--stone-500)', fontSize: '0.85rem' }}>
              Talk naturally about your location, size, budget, or water supply. Our S0 intake AI extracts your profile automatically!
            </p>
          </div>
          <ConversationalChat
            farmId={farmId}
            isMockMode={isMockMode}
            onComplete={onComplete}
          />
        </div>
      ) : (
        <>
          {/* Progress bar */}
          <div style={{ marginBottom: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--stone-500)', fontWeight: 500 }}>
                Step {step} of {TOTAL_STEPS}
              </span>
              <span style={{ fontSize: '0.8rem', color: 'var(--green-700)', fontWeight: 600 }}>
                {Math.round((step / TOTAL_STEPS) * 100)}%
              </span>
            </div>
            <div style={{ background: 'var(--stone-200)', borderRadius: 999, height: 6, overflow: 'hidden' }}>
              <div style={{
                height: '100%',
                background: 'linear-gradient(90deg, var(--green-500), var(--green-700))',
                borderRadius: 999,
                width: `${(step / TOTAL_STEPS) * 100}%`,
                transition: 'width 0.3s ease',
              }} />
            </div>
          </div>

          {/* Step card */}
          <div className="card slide-up" key={step}>
            {/* Avatar / emoji */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 20 }}>
              <div style={{
                width: 48, height: 48,
                background: 'var(--green-50)',
                borderRadius: '50%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 24, flexShrink: 0,
                border: '2px solid var(--green-200)',
              }}>
                {STEP_ICONS[step]}
              </div>
              <div>
                <h2 style={{ fontSize: '1.1rem', marginBottom: 2 }}>{STEP_TITLES[step]}</h2>
                <p style={{ color: 'var(--stone-500)', fontSize: '0.875rem' }}>{STEP_SUBTITLES[step]}</p>
              </div>
            </div>

            {/* Step content */}
            <div style={{ marginBottom: 24 }}>
              {step === 1 && (
                <Step1
                  form={form}
                  errors={errors}
                  onSelectPlace={(place: UpazilaPlace) => {
                    set('upazila', place.upazila);
                    set('district', place.district);
                    set('latitude', place.latitude.toString());
                    set('longitude', place.longitude.toString());
                  }}
                  onChangeManualCoords={(lat, lon) => {
                    set('latitude', lat);
                    set('longitude', lon);
                  }}
                />
              )}
              {step === 2 && (
                <Step2
                  form={form}
                  errors={errors}
                  onChange={(field, val) => set(field as keyof FormState, val)}
                />
              )}
              {step === 3 && (
                <Step3
                  form={form}
                  errors={errors}
                  onChange={(field, val) => set(field as keyof FormState, val)}
                />
              )}
              {step === 4 && (
                <Step4
                  form={form}
                  errors={errors}
                  onChange={(field, val) => set(field as keyof FormState, val)}
                />
              )}
              {step === 5 && (
                <Step5
                  form={form}
                  total={priorityTotal}
                  onChange={(field, val) => set(field as keyof FormState, val)}
                />
              )}
              {step === 6 && (
                <Step6
                  form={form}
                  errors={errors}
                  onChange={(field, val) => set(field as keyof FormState, val)}
                />
              )}
              {step === 7 && (
                <Step7
                  form={form}
                  irrigationMethods={IRRIGATION_METHODS}
                  onChange={(field, val) => set(field as keyof FormState, val)}
                />
              )}
            </div>

            {/* Navigation */}
            <div style={{ display: 'flex', gap: 10, justifyContent: 'space-between', alignItems: 'center' }}>
              <button className="btn-ghost" onClick={handleBack} disabled={step === 1}>
                ← Back
              </button>
              <div style={{ display: 'flex', gap: 10 }}>
                {skippable && (
                  <button className="btn-ghost" onClick={handleSkip}>
                    Skip
                  </button>
                )}
                <button className="btn-primary" onClick={handleNext}>
                  {isLastStep ? '✓ Review & Submit' : 'Next →'}
                </button>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Farm ID hint */}
      <p style={{ textAlign: 'center', marginTop: 12, fontSize: '0.75rem', color: 'var(--stone-400)' }}>
        Farm ID: <code style={{ fontFamily: 'monospace', background: 'var(--stone-100)', padding: '1px 6px', borderRadius: 4 }}>{farmId}</code>
      </p>
    </div>
  );
}

// ---- Step icons & labels ----
const STEP_ICONS: Record<StepId, string> = {
  1: '📍', 2: '📐', 3: '💰', 4: '💧', 5: '🎯', 6: '🧪', 7: '📝',
};
const STEP_TITLES: Record<StepId, string> = {
  1: 'Where is your farm located?',
  2: 'Farm size & monsoon land type',
  3: 'What is your season budget?',
  4: 'How much water can you use?',
  5: 'What matters most to you?',
  6: 'Did you test your soil?',
  7: 'Additional details (optional)',
};
const STEP_SUBTITLES: Record<StepId, string> = {
  1: 'Select from 505 Bangladesh Upazilas or enter custom coordinates.',
  2: 'Total hectares and monsoon flooding depth.',
  3: 'Total money available for seeds, fertiliser, and labour.',
  4: 'Cubic metres of irrigation water available this season.',
  5: 'Drag the sliders to balance your goals.',
  6: 'Lab test results override satellite soil estimates.',
  7: 'Irrigation method and other local specifics.',
};

// ---- Step sub-components ----

function FieldLabel({ children, error }: { children: React.ReactNode; error?: string }) {
  return (
    <div style={{ marginBottom: 16 }}>
      {children}
      {error && <p style={{ color: 'var(--red-700)', fontSize: '0.8rem', marginTop: 4 }}>{error}</p>}
    </div>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return <label style={{ display: 'block', fontWeight: 600, fontSize: '0.875rem', marginBottom: 6, color: 'var(--stone-700)' }}>{children}</label>;
}

function Step1({
  form,
  errors,
  onSelectPlace,
  onChangeManualCoords,
}: {
  form: FormState;
  errors: Record<string, string>;
  onSelectPlace: (place: UpazilaPlace) => void;
  onChangeManualCoords: (lat: string, lon: string) => void;
}) {
  return (
    <div>
      <FieldLabel error={errors.latitude || errors.longitude}>
        <UpazilaPicker
          selectedUpazila={form.upazila}
          selectedDistrict={form.district}
          latitude={form.latitude}
          longitude={form.longitude}
          onSelectPlace={onSelectPlace}
          onChangeManualCoords={onChangeManualCoords}
        />
      </FieldLabel>
    </div>
  );
}

function Step2({
  form,
  errors,
  onChange,
}: {
  form: FormState;
  errors: Record<string, string>;
  onChange: (f: string, v: string) => void;
}) {
  return (
    <div>
      <FieldLabel error={errors.area_ha}>
        <Label>Farm size (hectares)</Label>
        <input
          type="number"
          className={errors.area_ha ? 'error' : ''}
          value={form.area_ha}
          onChange={e => onChange('area_ha', e.target.value)}
          placeholder="e.g. 12.5"
          min="0.01"
          step="0.1"
        />
        <p style={{ fontSize: '0.8rem', color: 'var(--stone-500)', marginTop: 4 }}>
          1 hectare ≈ 2.47 acres · 1 bigha ≈ 0.13 hectares
        </p>
      </FieldLabel>

      <div style={{ marginTop: 16 }}>
        <Label>Monsoon Flood Depth (Land Type)</Label>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {LAND_TYPE_OPTIONS.map(opt => (
            <div
              key={opt.value}
              onClick={() => onChange('land_type', opt.value)}
              style={{
                padding: '10px 14px',
                borderRadius: 'var(--radius-md)',
                border: `1.5px solid ${form.land_type === opt.value ? 'var(--green-600)' : 'var(--stone-200)'}`,
                background: form.land_type === opt.value ? 'var(--green-50)' : 'white',
                cursor: 'pointer',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                transition: 'all 0.15s',
              }}
            >
              <div>
                <div style={{ fontWeight: 600, fontSize: '0.875rem', color: form.land_type === opt.value ? 'var(--green-800)' : 'var(--stone-800)' }}>
                  {opt.label}
                </div>
                <div style={{ fontSize: '0.78rem', color: 'var(--stone-500)' }}>
                  {opt.desc}
                </div>
              </div>
              <input
                type="radio"
                name="land_type"
                checked={form.land_type === opt.value}
                onChange={() => onChange('land_type', opt.value)}
                style={{ accentColor: 'var(--green-600)' }}
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Step3({ form, errors, onChange }: { form: FormState; errors: Record<string, string>; onChange: (f: string, v: string) => void }) {
  return (
    <FieldLabel error={errors.budget_usd}>
      <Label>Seasonal budget (USD)</Label>
      <input
        type="number"
        className={errors.budget_usd ? 'error' : ''}
        value={form.budget_usd}
        onChange={e => onChange('budget_usd', e.target.value)}
        placeholder="e.g. 8000"
        min="0"
        step="100"
      />
      <p style={{ fontSize: '0.8rem', color: 'var(--stone-500)', marginTop: 6 }}>
        Total budget for inputs, fertilizers, seeds, and labour across all 3 seasons.
      </p>
    </FieldLabel>
  );
}

function Step4({ form, errors, onChange }: { form: FormState; errors: Record<string, string>; onChange: (f: string, v: string) => void }) {
  return (
    <FieldLabel error={errors.irrigation_quota_m3}>
      <Label>Water quota per season (m³)</Label>
      <input
        type="number"
        className={errors.irrigation_quota_m3 ? 'error' : ''}
        value={form.irrigation_quota_m3}
        onChange={e => onChange('irrigation_quota_m3', e.target.value)}
        placeholder="e.g. 45000"
        min="0"
        step="500"
      />
      <p style={{ fontSize: '0.8rem', color: 'var(--stone-500)', marginTop: 6 }}>
        1 m³ = 1,000 litres. Example: 45,000 m³ for a medium farm.
      </p>
    </FieldLabel>
  );
}

function Step5({ form, total, onChange }: {
  form: FormState;
  total: number;
  onChange: (f: string, v: number) => void;
}) {
  const norm = normalise(form.priority_gross_margin, form.priority_water, form.priority_soil);

  function PrioritySlider({
    label, field, value, description, emoji,
  }: {
    label: string; field: string; value: number; description: string; emoji: string;
  }) {
    return (
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
          <label style={{ fontWeight: 600, fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: 6 }}>
            {emoji} {label}
          </label>
          <span style={{ fontWeight: 700, color: 'var(--green-700)', fontSize: '0.9rem', minWidth: 36, textAlign: 'right' }}>
            {Math.round(value * 10)}
          </span>
        </div>
        <input
          type="range"
          min="0"
          max="10"
          step="1"
          value={Math.round(value * 10)}
          onChange={e => onChange(field, parseInt(e.target.value) / 10)}
          style={{ accentColor: 'var(--green-600)' }}
        />
        <p style={{ fontSize: '0.78rem', color: 'var(--stone-500)', marginTop: 3 }}>{description}</p>
      </div>
    );
  }

  const pct = (v: number) => total === 0 ? '33%' : `${Math.round((v / total) * 100)}%`;

  return (
    <div>
      <PrioritySlider
        label="Earning Potential"
        field="priority_gross_margin"
        value={form.priority_gross_margin}
        description="How much profit the rotation generates above costs."
        emoji="💵"
      />
      <PrioritySlider
        label="Water Saving"
        field="priority_water"
        value={form.priority_water}
        description="How little water the rotation needs. Higher = prefer drought-tolerant crops."
        emoji="💧"
      />
      <PrioritySlider
        label="Soil Health"
        field="priority_soil"
        value={form.priority_soil}
        description="Long-term soil improvement through legumes and crop diversity."
        emoji="🌱"
      />

      <div style={{
        background: 'var(--green-50)',
        border: '1px solid var(--green-100)',
        borderRadius: 10,
        padding: '12px 16px',
        marginTop: 8,
      }}>
        <p style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--green-800)', marginBottom: 10 }}>
          How the system will balance your priorities:
        </p>
        <div style={{ display: 'flex', gap: 4, height: 20, borderRadius: 6, overflow: 'hidden' }}>
          <div style={{ flex: norm.gross_margin, background: 'var(--green-500)', transition: 'flex 0.3s' }} />
          <div style={{ flex: norm.water_m3, background: 'var(--sky-600)', transition: 'flex 0.3s' }} />
          <div style={{ flex: norm.soil_score, background: 'var(--amber-500)', transition: 'flex 0.3s' }} />
        </div>
        <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: '0.75rem', color: 'var(--stone-600)' }}>
          <span>🟢 Profit {pct(form.priority_gross_margin)}</span>
          <span>🔵 Water {pct(form.priority_water)}</span>
          <span>🟡 Soil {pct(form.priority_soil)}</span>
        </div>
      </div>
    </div>
  );
}

function Step6({ form, errors, onChange }: { form: FormState; errors: Record<string, string>; onChange: (f: string, v: boolean | null | string) => void }) {
  return (
    <div>
      <Label>Have you done a soil lab test recently?</Label>
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, marginTop: 8 }}>
        {[{ label: '✅ Yes, I have results', value: true }, { label: '❌ No, not yet', value: false }].map(({ label, value }) => (
          <button
            key={String(value)}
            onClick={() => onChange('has_soil_test', value)}
            style={{
              flex: 1,
              padding: '12px 16px',
              borderRadius: 'var(--radius-md)',
              border: `2px solid ${form.has_soil_test === value ? 'var(--green-600)' : 'var(--stone-200)'}`,
              background: form.has_soil_test === value ? 'var(--green-50)' : 'white',
              color: form.has_soil_test === value ? 'var(--green-800)' : 'var(--stone-600)',
              fontWeight: 600,
              fontSize: '0.9rem',
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {form.has_soil_test === true && (
        <div style={{ animation: 'fadeIn 0.2s ease' }}>
          <FieldLabel error={errors.soil_ph}>
            <Label>Soil pH (from lab report)</Label>
            <input
              type="number"
              className={errors.soil_ph ? 'error' : ''}
              value={form.soil_ph}
              onChange={e => onChange('soil_ph', e.target.value)}
              placeholder="e.g. 6.4"
              min="0"
              max="14"
              step="0.1"
            />
            <p style={{ fontSize: '0.78rem', color: 'var(--stone-500)', marginTop: 4 }}>
              Typical range: 5.5–7.5. Neutral is 7.0.
            </p>
          </FieldLabel>
        </div>
      )}

      {form.has_soil_test === false && (
        <div style={{
          background: 'var(--sky-50)',
          border: '1px solid var(--sky-100)',
          borderRadius: 8,
          padding: '10px 14px',
          fontSize: '0.8rem',
          color: 'var(--sky-600)',
          animation: 'fadeIn 0.2s ease',
        }}>
          No problem — we will use satellite soil data from SoilGrids for your location.
        </div>
      )}
    </div>
  );
}

function Step7({ form, irrigationMethods, onChange }: { form: FormState; irrigationMethods: string[]; onChange: (f: string, v: string) => void }) {
  return (
    <div>
      <div style={{ marginBottom: 20 }}>
        <Label>Irrigation method <span style={{ fontWeight: 400, color: 'var(--stone-400)' }}>(optional)</span></Label>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
          {irrigationMethods.map(method => (
            <button
              key={method}
              onClick={() => onChange('irrigation_method', form.irrigation_method === method ? '' : method)}
              style={{
                padding: '7px 14px',
                borderRadius: 999,
                border: `1.5px solid ${form.irrigation_method === method ? 'var(--green-600)' : 'var(--stone-300)'}`,
                background: form.irrigation_method === method ? 'var(--green-50)' : 'white',
                color: form.irrigation_method === method ? 'var(--green-800)' : 'var(--stone-600)',
                fontSize: '0.85rem',
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              {method.replace(/_/g, ' ')}
            </button>
          ))}
        </div>
      </div>

      <div style={{
        marginTop: 20,
        background: 'var(--amber-50)',
        border: '1px solid var(--amber-200)',
        borderRadius: 8,
        padding: '10px 14px',
        fontSize: '0.8rem',
        color: 'var(--amber-800)',
      }}>
        Ready to optimize! Next screen lets you review before generating recommendations.
      </div>
    </div>
  );
}
