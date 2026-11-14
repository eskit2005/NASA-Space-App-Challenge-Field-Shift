import { useState } from 'react';
import type { FarmerProfile, IntakeMessage, FarmerDraft, IntakeTurn } from '../types/api';
import { sendIntakeMessage, ApiError } from '../utils/api';

interface ConversationalChatProps {
  farmId: string;
  isMockMode: boolean;
  onComplete: (profile: FarmerProfile) => void;
}

const INITIAL_MESSAGES: IntakeMessage[] = [
  {
    role: 'assistant',
    content: "Welcome to FieldShift! 🌱 Tell me about your farm in your own words. For example:\n\"My farm is in Raninagar, Naogaon. It is 12.5 hectares, my budget is $8000, and I have 45000 m³ of water.\"",
  },
];

type ActiveField = 'location' | 'area_ha' | 'budget_usd' | 'irrigation_quota_m3' | 'land_type' | 'irrigation_method';

interface SuggestionChip {
  label: string;
  value: string;
}

const SUGGESTIONS_BY_FIELD: Record<ActiveField, { title: string; chips: SuggestionChip[] }> = {
  location: {
    title: 'Quick locations:',
    chips: [
      { label: '📍 Raninagar, Naogaon', value: 'My farm is in Raninagar, Naogaon' },
      { label: '📍 Adamdighi, Bogura', value: 'My farm is in Adamdighi, Bogura' },
      { label: '📍 Gazipur Sadar', value: 'My farm is in Gazipur Sadar' },
      { label: '📍 Dinajpur Sadar', value: 'My farm is in Dinajpur Sadar' },
    ],
  },
  area_ha: {
    title: 'Quick farm size:',
    chips: [
      { label: '📐 1.0 ha', value: 'My farm size is 1.0 hectare' },
      { label: '📐 2.5 ha', value: 'My farm size is 2.5 hectares' },
      { label: '📐 5.0 ha', value: 'My farm size is 5.0 hectares' },
      { label: '📐 12.5 ha', value: 'My farm size is 12.5 hectares' },
    ],
  },
  budget_usd: {
    title: 'Quick budget:',
    chips: [
      { label: '💰 $1,000', value: 'My budget is $1000' },
      { label: '💰 $3,000', value: 'My budget is $3000' },
      { label: '💰 $5,000', value: 'My budget is $5000' },
      { label: '💰 $8,000', value: 'My budget is $8000' },
    ],
  },
  irrigation_quota_m3: {
    title: 'Quick water quota:',
    chips: [
      { label: '💧 15,000 m³', value: 'My irrigation quota is 15000 m3' },
      { label: '💧 30,000 m³', value: 'My irrigation quota is 30000 m3' },
      { label: '💧 45,000 m³', value: 'My irrigation quota is 45000 m3' },
      { label: '💧 60,000 m³', value: 'My irrigation quota is 60000 m3' },
    ],
  },
  land_type: {
    title: 'Quick select land type:',
    chips: [
      { label: '🌾 Highland (HL)', value: 'My land type is HL' },
      { label: '🌾 Medium Highland (MHL)', value: 'My land type is MHL' },
      { label: '🌾 Medium Lowland (MLL)', value: 'My land type is MLL' },
      { label: '🌾 Lowland (LL)', value: 'My land type is LL' },
      { label: '🌾 Very Lowland (VLL)', value: 'My land type is VLL' },
    ],
  },
  irrigation_method: {
    title: 'Optional: Select irrigation source:',
    chips: [
      { label: '💧 Groundwater Tube Well (Default)', value: 'My irrigation method is tube well' },
      { label: '🌊 Canal / Surface Water', value: 'My irrigation method is canal' },
      { label: '🏞️ Farm Pond / Reservoir', value: 'My irrigation method is pond' },
      { label: '🌧️ Rain-fed (No Pump)', value: 'My irrigation is rainfed' },
    ],
  },
};

export default function ConversationalChat({
  farmId,
  isMockMode,
  onComplete,
}: ConversationalChatProps) {
  const [messages, setMessages] = useState<IntakeMessage[]>(INITIAL_MESSAGES);
  const [draft, setDraft] = useState<FarmerDraft>({});
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [completedProfile, setCompletedProfile] = useState<FarmerProfile | null>(null);
  const [currentMissingField, setCurrentMissingField] = useState<string | null>(null);

  // Compute active field for contextual suggestion buttons
  const activeField: ActiveField = (() => {
    if (completedProfile) return 'irrigation_method';
    if (currentMissingField && currentMissingField in SUGGESTIONS_BY_FIELD) {
      return currentMissingField as ActiveField;
    }
    // Fallback to checking unfilled fields in logical order
    if (!draft.location) return 'location';
    if (!draft.area_ha) return 'area_ha';
    if (!draft.budget_usd) return 'budget_usd';
    if (!draft.irrigation_quota_m3) return 'irrigation_quota_m3';
    if (!draft.land_type) return 'land_type';
    return 'irrigation_method';
  })();

  const suggestions = SUGGESTIONS_BY_FIELD[activeField];

  async function sendMessageWithText(text: string) {
    if (!text.trim() || isLoading) return;

    const userText = text.trim();
    setInputText('');
    setErrorMsg('');

    const newMessages: IntakeMessage[] = [
      ...messages,
      { role: 'farmer', content: userText },
    ];
    setMessages(newMessages);
    setIsLoading(true);

    const turn: IntakeTurn = {
      messages: newMessages,
      draft,
      farm_id: farmId,
    };

    try {
      const reply = await sendIntakeMessage(turn, isMockMode);
      setDraft(reply.draft);

      setMessages([
        ...newMessages,
        { role: 'assistant', content: reply.reply },
      ]);

      if (reply.missing_fields && reply.missing_fields.length > 0) {
        setCurrentMissingField(reply.missing_fields[0]);
      } else {
        setCurrentMissingField(null);
      }

      if (reply.is_complete && reply.profile) {
        const sanitizedProfile: FarmerProfile = {
          ...reply.profile,
          priorities: {
            gross_margin: reply.profile.priorities?.gross_margin ?? 0.5,
            water_m3: reply.profile.priorities?.water_m3 ?? 0.3,
            soil_score: reply.profile.priorities?.soil_score ?? 0.2,
          },
        };
        setCompletedProfile(sanitizedProfile);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMsg(err.detail);
      } else {
        setErrorMsg('Network error communicating with the chat intake service.');
      }
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Detected fields badge bar - wraps cleanly on mobile */}
      <div style={{
        background: 'var(--stone-100)',
        borderRadius: 'var(--radius-md)',
        padding: '10px 14px',
        display: 'flex',
        flexWrap: 'wrap',
        gap: 6,
        alignItems: 'center',
        fontSize: '0.78rem',
      }}>
        <span style={{ fontWeight: 700, color: 'var(--stone-700)', marginRight: 2 }}>Identified:</span>
        <span className={`badge ${draft.location ? 'badge-green' : 'badge-stone'}`}>
          📍 {draft.attributes?.upazila ? String(draft.attributes.upazila) : draft.location ? `${draft.location.latitude.toFixed(2)}°N` : 'Location pending'}
        </span>
        <span className={`badge ${draft.area_ha ? 'badge-green' : 'badge-stone'}`}>
          📐 {draft.area_ha ? `${draft.area_ha} ha` : 'Area pending'}
        </span>
        <span className={`badge ${draft.budget_usd ? 'badge-green' : 'badge-stone'}`}>
          💰 {draft.budget_usd ? `$${draft.budget_usd}` : 'Budget pending'}
        </span>
        <span className={`badge ${draft.irrigation_quota_m3 ? 'badge-green' : 'badge-stone'}`}>
          💧 {draft.irrigation_quota_m3 ? `${draft.irrigation_quota_m3} m³` : 'Water pending'}
        </span>
        <span className={`badge ${draft.land_type ? 'badge-green' : 'badge-stone'}`}>
          🌾 {draft.land_type ? `Land: ${draft.land_type}` : 'Land pending'}
        </span>
        {draft.attributes?.irrigation_method && (
          <span className="badge badge-green">
            💧 {String(draft.attributes.irrigation_method).replace(/_/g, ' ')}
          </span>
        )}
      </div>

      {/* Chat Messages Log */}
      <div
        style={{
          background: 'white',
          border: '1px solid var(--stone-200)',
          borderRadius: 'var(--radius-lg)',
          padding: 14,
          height: 300,
          maxHeight: '45vh',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}
      >
        {messages.map((m, idx) => {
          const isFarmer = m.role === 'farmer';
          return (
            <div
              key={idx}
              style={{
                alignSelf: isFarmer ? 'flex-end' : 'flex-start',
                maxWidth: '88%',
                display: 'flex',
                gap: 8,
                flexDirection: isFarmer ? 'row-reverse' : 'row',
                animation: 'fadeIn 0.2s',
              }}
            >
              <div style={{
                width: 30, height: 30,
                borderRadius: '50%',
                background: isFarmer ? 'var(--green-700)' : 'var(--stone-200)',
                color: isFarmer ? 'white' : 'var(--stone-800)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 13, flexShrink: 0,
              }}>
                {isFarmer ? '👨‍🌾' : '🤖'}
              </div>
              <div style={{
                background: isFarmer ? 'var(--green-700)' : 'var(--stone-50)',
                color: isFarmer ? 'white' : 'var(--stone-900)',
                borderRadius: 'var(--radius-md)',
                padding: '9px 13px',
                fontSize: '0.875rem',
                lineHeight: 1.5,
                border: isFarmer ? 'none' : '1px solid var(--stone-200)',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}>
                {m.content}
              </div>
            </div>
          );
        })}

        {isLoading && (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', color: 'var(--stone-500)', fontSize: '0.85rem' }}>
            <span style={{ fontSize: 16 }}>🤖</span>
            <div className="dot-pulse"><span /><span /><span /></div>
          </div>
        )}
      </div>

      {/* Contextual Suggestion Chips: Strictly 1 neat line matching active question */}
      {suggestions && suggestions.chips.length > 0 && (
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 6,
          alignItems: 'center',
          padding: '8px 12px',
          background: 'var(--stone-50)',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--stone-200)',
          animation: 'fadeIn 0.2s',
          overflowX: 'auto',
          WebkitOverflowScrolling: 'touch',
        }}>
          <span style={{ fontSize: '0.78rem', color: 'var(--stone-600)', fontWeight: 600, marginRight: 2, whiteSpace: 'nowrap' }}>
            {suggestions.title}
          </span>
          {suggestions.chips.map(chip => (
            <button
              key={chip.label}
              type="button"
              className="btn-ghost"
              onClick={() => sendMessageWithText(chip.value)}
              disabled={isLoading}
              style={{
                border: '1px solid var(--stone-300)',
                color: 'var(--stone-800)',
                background: 'white',
                padding: '4px 11px',
                borderRadius: 999,
                fontSize: '0.78rem',
                fontWeight: 500,
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                transition: 'all 0.15s ease-in-out',
                boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--green-600)';
                e.currentTarget.style.color = 'var(--green-800)';
                e.currentTarget.style.background = 'var(--green-50)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--stone-300)';
                e.currentTarget.style.color = 'var(--stone-800)';
                e.currentTarget.style.background = 'white';
              }}
            >
              {chip.label}
            </button>
          ))}
          {/* If on irrigation step and completedProfile exists, offer direct Proceed shortcut chip */}
          {completedProfile && (
            <button
              type="button"
              className="btn-ghost"
              onClick={() => onComplete(completedProfile)}
              disabled={isLoading}
              style={{
                border: '1px solid var(--green-600)',
                color: 'var(--green-800)',
                background: 'var(--green-50)',
                padding: '4px 12px',
                borderRadius: 999,
                fontSize: '0.78rem',
                fontWeight: 600,
                cursor: 'pointer',
                whiteSpace: 'nowrap',
              }}
            >
              ✓ Proceed to Review →
            </button>
          )}
        </div>
      )}

      {errorMsg && (
        <div style={{ color: 'var(--red-700)', fontSize: '0.85rem' }}>
          ⚠️ {errorMsg}
        </div>
      )}

      {/* Completion alert card */}
      {completedProfile && (
        <div
          style={{
            background: 'var(--green-50)',
            border: '2px solid var(--green-500)',
            borderRadius: 'var(--radius-md)',
            padding: 14,
            textAlign: 'center',
            animation: 'fadeIn 0.3s',
          }}
        >
          <div style={{ fontWeight: 700, color: 'var(--green-800)', marginBottom: 4, fontSize: '0.95rem' }}>
            🎉 All required farm details collected!
          </div>
          <p style={{ fontSize: '0.82rem', color: 'var(--stone-600)', marginBottom: 10 }}>
            Your farm profile is ready. You can specify an irrigation method above or review and calculate optimal rotations.
          </p>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, justifyContent: 'center', marginBottom: 12 }}>
            <span className="badge badge-stone" style={{ fontSize: '0.78rem' }}>
              💧 Irrigation: {completedProfile.attributes?.irrigation_method ? String(completedProfile.attributes.irrigation_method).replace(/_/g, ' ') : 'Tube well (Default)'}
            </span>
            {completedProfile.soil_overrides?.ph !== undefined && (
              <span className="badge badge-stone" style={{ fontSize: '0.78rem' }}>
                🧪 Soil: Lab pH {completedProfile.soil_overrides.ph}
              </span>
            )}
          </div>

          <button
            className="btn-primary"
            onClick={() => onComplete(completedProfile)}
            style={{ width: '100%', justifyContent: 'center', fontSize: '0.95rem', padding: '10px 16px' }}
          >
            ✓ Proceed to Review Farm Profile →
          </button>
        </div>
      )}

      {/* Input box — always available so farmer can ask questions or add specifics */}
      <form
        onSubmit={e => {
          e.preventDefault();
          sendMessageWithText(inputText);
        }}
        style={{ display: 'flex', gap: 8, alignItems: 'center' }}
      >
        <input
          type="text"
          placeholder={completedProfile ? "Ask a question about your farm or recommendations..." : "Type your message (e.g. 'I farm in Raninagar with 10 ha, land is MHL')..."}
          value={inputText}
          onChange={e => setInputText(e.target.value)}
          disabled={isLoading}
          style={{ flex: 1, fontSize: '16px' }}
        />
        <button
          type="submit"
          className="btn-primary"
          disabled={!inputText.trim() || isLoading}
          style={{ padding: '10px 18px', flexShrink: 0 }}
        >
          Send ↵
        </button>
      </form>
    </div>
  );
}
