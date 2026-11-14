import type { CropReference, SeasonReference } from '../types/api';

export const CROP_NAMES: Record<string, string> = {
  wheat: 'Wheat',
  rice: 'Rice',
  mung_bean: 'Mung Bean',
  maize: 'Maize',
  corn: 'Corn',
  soybean: 'Soybean',
  lentil: 'Lentil',
  chickpea: 'Chickpea',
  cotton: 'Cotton',
  sugarcane: 'Sugarcane',
  potato: 'Potato',
  tomato: 'Tomato',
  mustard: 'Mustard',
  sunflower: 'Sunflower',
  jute: 'Jute',
  barley: 'Barley',
  sorghum: 'Sorghum',
  millet: 'Millet',
  groundnut: 'Groundnut',
  peanut: 'Peanut',
  sesame: 'Sesame',
  flaxseed: 'Flaxseed',
  onion: 'Onion',
  garlic: 'Garlic',
  capsicum: 'Capsicum',
  eggplant: 'Eggplant',
  spinach: 'Spinach',
  cabbage: 'Cabbage',
  cauliflower: 'Cauliflower',
  bitter_gourd: 'Bitter Gourd',
  pumpkin: 'Pumpkin',
  fallow: 'Fallow (Resting Soil)',
  '999': 'Fallow (Resting Soil)',
};

const dynamicCrops: Record<string, string> = {};
const dynamicSeasons: Record<string, string> = {};

export function registerCrops(crops: CropReference[]) {
  for (const c of crops) {
    dynamicCrops[c.crop_id] = c.name;
    dynamicCrops[c.crop_id.toLowerCase()] = c.name;
  }
}

export function registerSeasons(seasons: SeasonReference[]) {
  seasons.forEach((s, idx) => {
    const label = `${s.name} (Months ${s.start_month}–${s.end_month})`;
    dynamicSeasons[s.name] = label;
    dynamicSeasons[`season_${idx + 1}`] = label;
  });
}

export function getCropName(crop_id: string): string {
  if (dynamicCrops[crop_id]) return dynamicCrops[crop_id];
  if (dynamicCrops[crop_id.toLowerCase()]) return dynamicCrops[crop_id.toLowerCase()];
  if (CROP_NAMES[crop_id]) return CROP_NAMES[crop_id];
  if (CROP_NAMES[crop_id.toLowerCase()]) return CROP_NAMES[crop_id.toLowerCase()];
  return crop_id.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

/** Friendly season labels */
export function getSeasonLabel(season: string, index: number): string {
  if (dynamicSeasons[season]) return dynamicSeasons[season];
  const fallbackLabels: Record<string, string> = {
    season_1: 'Season 1 (Rabi: Nov–Feb)',
    season_2: 'Season 2 (Kharif-1: Mar–Jun)',
    season_3: 'Season 3 (Kharif-2: Jul–Oct)',
    Rabi: 'Rabi (Nov–Feb)',
    'Kharif-1': 'Kharif-1 (Mar–Jun)',
    'Kharif-2': 'Kharif-2 (Jul–Oct)',
  };
  return fallbackLabels[season] ?? `Season ${index + 1}`;
}
