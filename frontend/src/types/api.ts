// ============================================================
// TypeScript types — mirrors the API contract exactly.
// Unknown fields must be preserved (use [key: string]: unknown).
// ============================================================

export type LandType = 'HL' | 'MHL' | 'MLL' | 'LL' | 'VLL' | 'ML';

export interface Location {
  latitude: number;
  longitude: number;
}

export interface Priorities {
  gross_margin: number;
  water_m3: number;
  soil_score: number;
  [key: string]: number;
}

/** The body sent to POST /api/v1/recommendations/optimize */
export interface FarmerProfile {
  farm_id: string;
  location: Location;
  area_ha: number;
  budget_usd: number;
  irrigation_quota_m3: number;
  land_type?: LandType;
  priorities?: Priorities;
  soil_overrides?: Record<string, number>;
  attributes?: Record<string, string | number>;
  [key: string]: unknown;
}

// ---- Conversational Intake Chat (POST /api/v1/intake/message) ----

export interface IntakeMessage {
  role: 'farmer' | 'assistant';
  content: string;
}

export interface FarmerDraft {
  location?: Location | null;
  area_ha?: number | null;
  budget_usd?: number | null;
  irrigation_quota_m3?: number | null;
  land_type?: LandType | null;
  priorities?: Record<string, number>;
  soil_overrides?: Record<string, number>;
  attributes?: Record<string, string | number>;
  [key: string]: unknown;
}

export interface IntakeTurn {
  messages: IntakeMessage[];
  draft: FarmerDraft;
  farm_id?: string | null;
}

export interface IntakeReply {
  reply: string;
  draft: FarmerDraft;
  missing_fields: string[];
  is_complete: boolean;
  profile?: FarmerProfile | null;
  warnings?: string[];
  source?: string;
  [key: string]: unknown;
}

// ---- Reference Data Types (/crops, /objectives, /seasons) ----

export interface CropReference {
  crop_id: string;
  name: string;
  family: string;
}

export interface ObjectiveReference {
  key: string;
  label: string;
  unit: string;
}

export interface SeasonReference {
  name: string;
  start_month: number;
  end_month: number;
}

// ---- Upazila place for search / geocoding ----

export interface UpazilaPlace {
  code: string;
  upazila: string;
  district: string;
  division: string;
  latitude: number;
  longitude: number;
}

// ---- Response types for /recommendations/optimize ----

export interface SoilData {
  ph?: number;
  organic_carbon_g_kg?: number;
  texture?: string;
  is_field_tested?: boolean;
  attributes?: Record<string, unknown>;
  warnings?: string[];
  source?: string;
  [key: string]: unknown;
}

export interface SeasonData {
  season: string;
  mean_temp_c?: number;
  precipitation_mm?: number;
  et0_mm?: number;
  attributes?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface Environment {
  soil?: SoilData;
  seasons?: SeasonData[];
  warnings?: string[];
  source?: string;
  [key: string]: unknown;
}

export interface SequenceMetrics {
  gross_margin?: number;
  water_m3?: number;
  soil_score?: number;
  [key: string]: number | undefined;
}

export interface EvaluatedSequence {
  sequence_id: string;
  crop_ids: string[];
  metrics: SequenceMetrics;
  is_pareto_optimal: boolean;
  notes?: Record<string, string>;
  [key: string]: unknown;
}

export interface Evaluated {
  sequences?: EvaluatedSequence[];
  warnings?: string[];
  source?: string;
  [key: string]: unknown;
}

export interface EvidenceReference {
  source_id: string;
  title: string;
  url: string | null;
  claim: string;
  [key: string]: unknown;
}

export interface Explanation {
  summary?: string;
  sections?: Record<string, string>;
  evidence?: EvidenceReference[];
  generated_by?: 'template' | 'llm' | string;
  warnings?: string[];
  source?: string;
  [key: string]: unknown;
}

/** The full response from POST /api/v1/recommendations/optimize */
export interface FinalResponse {
  farmer?: FarmerProfile;
  environment?: Environment;
  evaluated?: Evaluated;
  explanation?: Explanation;
  warnings?: string[];
  source?: string;
  recommended_sequence_id?: string;
  [key: string]: unknown;
}

// ---- Error shapes ----

export interface ValidationErrorDetail {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export type ApiErrorBody =
  | { detail: string }
  | { detail: ValidationErrorDetail[] };
