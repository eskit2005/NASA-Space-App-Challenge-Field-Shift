import type {
  FarmerProfile,
  FinalResponse,
  IntakeTurn,
  IntakeReply,
  CropReference,
  ObjectiveReference,
  SeasonReference,
} from '../types/api';
import { DEFAULT_MOCK_API, API_BASE_URL } from '../config';
import { MOCK_RESPONSE } from '../mock/mockData';

/** Simulate network delay */
function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
    public readonly raw?: unknown
  ) {
    super(detail);
    this.name = 'ApiError';
  }
}

/** Extract a human-readable message from an error response body */
function extractDetail(body: unknown): string {
  if (typeof body !== 'object' || body === null) return 'An unexpected error occurred.';
  const b = body as Record<string, unknown>;
  if (typeof b.detail === 'string') return b.detail;
  if (Array.isArray(b.detail)) {
    return b.detail
      .map((d: unknown) => {
        if (typeof d === 'object' && d !== null) {
          const e = d as Record<string, unknown>;
          return `${Array.isArray(e.loc) ? e.loc.join(' → ') : ''}: ${e.msg ?? ''}`.trim();
        }
        return String(d);
      })
      .join('\n');
  }
  return JSON.stringify(body);
}

// -------------------------------------------------------------
// POST /api/v1/recommendations/optimize
// -------------------------------------------------------------
export async function fetchRecommendations(
  profile: FarmerProfile,
  isMock: boolean = DEFAULT_MOCK_API
): Promise<FinalResponse> {
  if (isMock) {
    await sleep(2000);
    return { ...MOCK_RESPONSE, farmer: profile };
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/recommendations/optimize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(profile),
  });

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (!response.ok) {
    const detail = extractDetail(body);
    throw new ApiError(response.status, detail, body);
  }

  return body as FinalResponse;
}

// -------------------------------------------------------------
// GET /health
// -------------------------------------------------------------
export async function checkHealth(): Promise<boolean> {
  try {
    const r = await fetch(`${API_BASE_URL}/health`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
      signal: AbortSignal.timeout(3000),
    });
    return r.ok;
  } catch {
    return false;
  }
}

// -------------------------------------------------------------
// POST /api/v1/intake/message (Conversational Intake)
// -------------------------------------------------------------
export async function sendIntakeMessage(
  turn: IntakeTurn,
  isMock: boolean = DEFAULT_MOCK_API
): Promise<IntakeReply> {
  if (isMock) {
    await sleep(800);
    // Simple mock simulation of chat intake
    const lastMsg = turn.messages[turn.messages.length - 1]?.content.toLowerCase() || '';
    const draft = { ...turn.draft };

    if (!draft.location && (lastMsg.includes('raninagar') || lastMsg.includes('dhaka') || lastMsg.includes('farm'))) {
      draft.location = { latitude: 24.7145, longitude: 88.9974 };
      draft.attributes = { ...draft.attributes, district: 'Naogaon', upazila: 'Raninagar' };
    }
    if (!draft.area_ha && (lastMsg.includes('ha') || lastMsg.includes('hectare'))) {
      const match = lastMsg.match(/(\d+(?:\.\d+)?)\s*(?:ha|hectare)/i);
      if (match) draft.area_ha = parseFloat(match[1]);
    }
    if (!draft.budget_usd && (lastMsg.includes('dollar') || lastMsg.includes('usd') || lastMsg.includes('budget') || lastMsg.includes('$'))) {
      const match = lastMsg.match(/(?:\$|budget\s*(?:is|of)?\s*\$?|\b)(\d+)\s*(?:usd|dollars)?/i) 
        || lastMsg.match(/\$(\d+)/i);
      // More specific pattern if general fails
      const specificBudget = lastMsg.match(/\$(\d+)/) || lastMsg.match(/budget[^\d]*(\d+)/i);
      if (specificBudget) {
        draft.budget_usd = parseFloat(specificBudget[1]);
      } else if (match) {
        draft.budget_usd = parseFloat(match[1]);
      }
    }
    if (!draft.irrigation_quota_m3 && (lastMsg.includes('water') || lastMsg.includes('m3') || lastMsg.includes('m³') || lastMsg.includes('quota'))) {
      const match = lastMsg.match(/(\d+)\s*(?:m3|m³)/i) || lastMsg.match(/(\d+)\s*(?:cubic|litres|liters|water)/i) || lastMsg.match(/water[^\d]*(\d+)/i);
      if (match) draft.irrigation_quota_m3 = parseFloat(match[1]);
    }
    if (!draft.land_type) {
      if (lastMsg.includes('mhl') || lastMsg.includes('medium high') || lastMsg.includes('medium-high')) draft.land_type = 'MHL';
      else if (lastMsg.includes('mll') || lastMsg.includes('medium low') || lastMsg.includes('medium-low')) draft.land_type = 'MLL';
      else if (lastMsg.includes('vll') || lastMsg.includes('very low')) draft.land_type = 'VLL';
      else if (lastMsg.includes('ll') || lastMsg.includes('lowland') || lastMsg.includes('low land')) draft.land_type = 'LL';
      else if (lastMsg.includes('hl') || lastMsg.includes('highland') || lastMsg.includes('high land')) draft.land_type = 'HL';
    }

    if (lastMsg.includes('ph')) {
      const match = lastMsg.match(/ph\s*(?:is|:|=|of)?\s*(\d+(?:\.\d+)?)/i);
      if (match) {
        draft.soil_overrides = { ...(draft.soil_overrides || {}), ph: parseFloat(match[1]) };
      }
    }
    if (lastMsg.includes('irrigation') || lastMsg.includes('tube') || lastMsg.includes('canal') || lastMsg.includes('rainfed')) {
      if (lastMsg.includes('canal')) draft.attributes = { ...(draft.attributes || {}), irrigation_method: 'canal' };
      else if (lastMsg.includes('rainfed') || lastMsg.includes('rain-fed')) draft.attributes = { ...(draft.attributes || {}), irrigation_method: 'rainfed' };
      else if (lastMsg.includes('pond')) draft.attributes = { ...(draft.attributes || {}), irrigation_method: 'pond' };
      else if (lastMsg.includes('tube')) draft.attributes = { ...(draft.attributes || {}), irrigation_method: 'tube_well' };
    }

    const missing: string[] = [];
    if (!draft.location) missing.push('location');
    if (!draft.area_ha) missing.push('area_ha');
    if (!draft.budget_usd) missing.push('budget_usd');
    if (!draft.irrigation_quota_m3) missing.push('irrigation_quota_m3');
    if (!draft.land_type) missing.push('land_type');

    if (missing.length === 0) {
      const irrigationSpecified = !!draft.attributes?.irrigation_method;
      const reply = irrigationSpecified
        ? "Thanks! I have all your farm details. Ready to generate recommendations."
        : "Thanks! I have your core farm details. (Optional: What irrigation method do you use — e.g. tube well, canal, pond, or rain-fed? Or proceed directly to review).";

      return {
        reply,
        draft,
        missing_fields: [],
        is_complete: true,
        profile: {
          farm_id: turn.farm_id || 'farm-001',
          location: draft.location!,
          area_ha: draft.area_ha!,
          budget_usd: draft.budget_usd!,
          irrigation_quota_m3: draft.irrigation_quota_m3!,
          land_type: draft.land_type || 'MHL',
          priorities: { gross_margin: 0.5, water_m3: 0.3, soil_score: 0.2 },
          soil_overrides: draft.soil_overrides,
          attributes: draft.attributes,
        },
      };
    }

    const prompts: Record<string, string> = {
      location: "Where is your farm located (district or upazila)?",
      area_ha: "What is your farm size in hectares?",
      budget_usd: "What is your seasonal budget in USD?",
      irrigation_quota_m3: "How much irrigation water can you use this season in m³?",
      land_type: "What is your monsoon land elevation type (HL, MHL, MLL, or LL)?",
    };

    return {
      reply: prompts[missing[0]] || "Could you share more details about your farm?",
      draft,
      missing_fields: missing,
      is_complete: false,
      profile: null,
    };
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/intake/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(turn),
  });

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (!response.ok) {
    const detail = extractDetail(body);
    throw new ApiError(response.status, detail, body);
  }

  return body as IntakeReply;
}

// -------------------------------------------------------------
// Reference endpoints: GET /crops, /objectives, /seasons
// -------------------------------------------------------------

export async function fetchCrops(): Promise<CropReference[]> {
  try {
    const r = await fetch(`${API_BASE_URL}/api/v1/crops`, { signal: AbortSignal.timeout(3000) });
    if (r.ok) return await r.json();
  } catch {
    // fallback
  }
  return [];
}

export async function fetchObjectives(): Promise<ObjectiveReference[]> {
  try {
    const r = await fetch(`${API_BASE_URL}/api/v1/objectives`, { signal: AbortSignal.timeout(3000) });
    if (r.ok) return await r.json();
  } catch {
    // fallback
  }
  return [
    { key: "gross_margin", label: "Expected margin", unit: "USD" },
    { key: "water_m3", label: "Water needed", unit: "m3" },
    { key: "soil_score", label: "Soil health", unit: "0-1" },
  ];
}

export async function fetchSeasons(): Promise<SeasonReference[]> {
  try {
    const r = await fetch(`${API_BASE_URL}/api/v1/seasons`, { signal: AbortSignal.timeout(3000) });
    if (r.ok) return await r.json();
  } catch {
    // fallback
  }
  return [
    { name: "Rabi", start_month: 11, end_month: 2 },
    { name: "Kharif-1", start_month: 3, end_month: 6 },
    { name: "Kharif-2", start_month: 7, end_month: 10 },
  ];
}
