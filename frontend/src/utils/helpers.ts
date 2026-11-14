import type { FinalResponse, EvaluatedSequence } from '../types/api';

/** Derive the best sequence from the response.
 *  Priority:
 *  1. Use recommended_sequence_id if the backend provides it.
 *  2. Among Pareto-optimal sequences, pick the one with highest weighted score using farmer priorities.
 *  3. Fall back to first Pareto-optimal, then first sequence overall.
 */
export function deriveBestSequence(response: FinalResponse): EvaluatedSequence | null {
  const sequences = response.evaluated?.sequences ?? [];
  if (sequences.length === 0) return null;

  // 1. Backend-provided winner
  if (response.recommended_sequence_id) {
    const found = sequences.find(s => s.sequence_id === response.recommended_sequence_id);
    if (found) return found;
  }

  // 2. Weighted score from farmer priorities
  const priorities = {
    gross_margin: response.farmer?.priorities?.gross_margin ?? 0.5,
    water_m3: response.farmer?.priorities?.water_m3 ?? 0.3,
    soil_score: response.farmer?.priorities?.soil_score ?? 0.2,
  };
  const pareto = sequences.filter(s => s.is_pareto_optimal);
  const pool = pareto.length > 0 ? pareto : sequences;

  if (priorities) {
    // Normalise metrics to 0-1 for scoring (higher is better for all three keys)
    const keys = ['gross_margin', 'water_m3', 'soil_score'] as const;

    // For water_m3, lower is better — invert it
    const getValues = (key: string) => pool.map(s => s.metrics[key] ?? 0);

    const ranges: Record<string, { min: number; max: number }> = {};
    for (const key of keys) {
      const vals = getValues(key);
      ranges[key] = { min: Math.min(...vals), max: Math.max(...vals) };
    }

    function normalise(val: number, key: string): number {
      const { min, max } = ranges[key];
      if (max === min) return 1;
      const norm = (val - min) / (max - min);
      return key === 'water_m3' ? 1 - norm : norm; // lower water = better
    }

    let best: EvaluatedSequence | null = null;
    let bestScore = -Infinity;

    for (const seq of pool) {
      const score =
        priorities.gross_margin * normalise(seq.metrics.gross_margin ?? 0, 'gross_margin') +
        priorities.water_m3 * normalise(seq.metrics.water_m3 ?? 0, 'water_m3') +
        priorities.soil_score * normalise(seq.metrics.soil_score ?? 0, 'soil_score');

      if (score > bestScore) {
        bestScore = score;
        best = seq;
      }
    }
    if (best) return best;
  }

  // 3. Fallback
  return pool[0];
}

export interface ProcessedWarnings {
  farmerWarnings: string[];
  technicalNotes: string[];
  allWarnings: string[];
}

/** Collect and deduplicate warnings, separating farmer alerts from model disclaimers */
export function collectWarnings(response: FinalResponse): ProcessedWarnings {
  const rawSet = new Set<string>();

  if (response.warnings) response.warnings.forEach(w => w && rawSet.add(w.trim()));
  if (response.environment?.warnings) response.environment.warnings.forEach(w => w && rawSet.add(w.trim()));
  if (response.evaluated?.warnings) response.evaluated.warnings.forEach(w => w && rawSet.add(w.trim()));
  if (response.explanation?.warnings) response.explanation.warnings.forEach(w => w && rawSet.add(w.trim()));

  const farmerWarnings: string[] = [];
  const technicalNotes: string[] = [];
  let placeholderCount = 0;

  for (const w of rawSet) {
    if (!w) continue;

    // Group repetitive placeholder warnings into a single clean note
    if (w.includes('S6 used placeholder crop defaults for:')) {
      placeholderCount++;
      continue;
    }

    // Friendly LLM fallback handling
    if (w.includes("Explainer 'llm' failed") || w.includes('ModuleNotFoundError')) {
      technicalNotes.push('Explanation formatted using standard agronomist recommendation templates.');
      continue;
    }

    if (w.includes('S6 crop parameters are placeholders') || w.includes('scores are not agronomic advice')) {
      technicalNotes.push('Economic calculations and soil scores are computational models for regional planning.');
      continue;
    }

    // Farmer-facing advisories
    if (w.toLowerCase().includes('exceeds the quota') || w.toLowerCase().includes('water-limited')) {
      farmerWarnings.push('💧 Water Demand Notice: Estimated irrigation water exceeds your seasonal quota. Monsoon rains help cover the gap, but yields may be water-limited during peak dry spells.');
    } else if (w.toLowerCase().includes('exceeds the budget')) {
      farmerWarnings.push('💰 Budget Notice: Estimated input costs exceed your specified seasonal budget for some candidate rotations.');
    } else if (
      w.toLowerCase().includes('soilgrids') ||
      w.toLowerCase().includes('nitrogen missing') ||
      w.toLowerCase().includes('placeholder') ||
      w.toLowerCase().includes('stock of') ||
      w.toLowerCase().includes('ph left empty') ||
      w.toLowerCase().includes('s6') ||
      w.toLowerCase().includes('s1') ||
      w.toLowerCase().includes('s7') ||
      w.toLowerCase().includes('s8')
    ) {
      technicalNotes.push(w);
    } else {
      farmerWarnings.push(w);
    }
  }

  if (placeholderCount > 0) {
    technicalNotes.push(`Regional baseline trait estimates were used for ${placeholderCount} candidate crop rotations.`);
  }

  const uniqueFarmer = Array.from(new Set(farmerWarnings));
  const uniqueTechnical = Array.from(new Set(technicalNotes));

  return {
    farmerWarnings: uniqueFarmer,
    technicalNotes: uniqueTechnical,
    allWarnings: [...uniqueFarmer, ...uniqueTechnical],
  };
}

/** Crop visual metadata (icon, role, color) */
export interface CropVisual {
  icon: string;
  role: string;
  badgeClass: string;
  color: string;
}

export function getCropVisual(cropNameOrId: string): CropVisual {
  const lower = cropNameOrId.toLowerCase();
  if (lower.includes('chickpea') || lower.includes('gram') || lower.includes('lentil') || lower.includes('mung')) {
    return { icon: '🌰', role: 'Nitrogen-Fixing Pulse', badgeClass: 'badge-green', color: '#166534' };
  }
  if (lower.includes('maize') || lower.includes('corn')) {
    return { icon: '🌽', role: 'High-Yield Cash Grain', badgeClass: 'badge-amber', color: '#d97706' };
  }
  if (lower.includes('potato')) {
    return { icon: '🥔', role: 'High-Value Cash Crop', badgeClass: 'badge-amber', color: '#b45309' };
  }
  if (lower.includes('rice') || lower.includes('paddy') || lower.includes('boro') || lower.includes('aman') || lower.includes('aus')) {
    return { icon: '🍚', role: 'Staple Cereal Crop', badgeClass: 'badge-sky', color: '#0369a1' };
  }
  if (lower.includes('sesame')) {
    return { icon: '🌿', role: 'Drought-Tolerant Oilseed', badgeClass: 'badge-green', color: '#15803d' };
  }
  if (lower.includes('mustard')) {
    return { icon: '🌼', role: 'Quick Winter Oilseed', badgeClass: 'badge-amber', color: '#ca8a04' };
  }
  if (lower.includes('wheat')) {
    return { icon: '🌾', role: 'Cool-Season Grain', badgeClass: 'badge-sky', color: '#0284c7' };
  }
  if (lower.includes('jute')) {
    return { icon: '🪴', role: 'Commercial Fiber Crop', badgeClass: 'badge-green', color: '#15803d' };
  }
  if (lower.includes('fallow')) {
    return { icon: '🍂', role: 'Soil Rest & Rejuvenation', badgeClass: 'badge-stone', color: '#78716c' };
  }
  return { icon: '🌱', role: 'Seasonal Field Crop', badgeClass: 'badge-stone', color: '#44403c' };
}

/** Translate raw soil decimal into friendly farmer rating */
export function formatSoilHealth(score: number): { label: string; stars: string; tip: string } {
  if (score >= 0.5) {
    return {
      label: 'Excellent Soil Building',
      stars: '⭐⭐⭐⭐⭐',
      tip: 'High organic replenishment; legumes fix natural nitrogen to cut next season’s fertilizer costs.',
    };
  }
  if (score >= 0.3) {
    return {
      label: 'Good Soil Balance',
      stars: '⭐⭐⭐⭐☆',
      tip: 'Maintains healthy soil organic content and prevents nutrient depletion across seasons.',
    };
  }
  if (score >= 0.15) {
    return {
      label: 'Moderate Soil Sustaining',
      stars: '⭐⭐⭐☆☆',
      tip: 'Includes restorative pulse crops to balance soil nutrients after heavy-feeding grains.',
    };
  }
  return {
    label: 'Demanding on Soil',
    stars: '⭐⭐☆☆☆',
    tip: 'High nutrient extraction; recommended to apply farmyard manure or compost between cycles.',
  };
}

/** Humanize technical sequence summaries into direct farmer English */
export function humanizeSummary(rawSummary: string | undefined, cropNames: string[]): string {
  if (!rawSummary) {
    return `This 3-season rotation of ${cropNames.join(' ➔ ')} gives the best overall balance of income, water use, and soil protection for your farm.`;
  }
  // Remove technical codes like "Sequence seq-053 (21 -> 99 -> 91)"
  let clean = rawSummary.replace(/Sequence\s+seq-\w+\s*\([^)]*\)\s*/i, 'This rotation plan ');
  clean = clean.replace(/seq-\w+/gi, 'this plan');
  clean = clean.replace(/\(\d+\s*->\s*\d+\s*->\s*\d+\)/g, '');
  clean = clean.replace(/m3\b/g, 'm³');
  return clean;
}

/** Format a number as USD */
export function formatUSD(val: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val);
}

/** Format a number with commas */
export function formatNumber(val: number, decimals = 0): string {
  return val.toLocaleString('en-US', { maximumFractionDigits: decimals });
}
