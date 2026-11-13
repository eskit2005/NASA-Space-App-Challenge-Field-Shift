# Resources

What we receive from each external source.

## Open-Meteo

API: `https://archive-api.open-meteo.com/v1/archive` (historical archive)

1. **Request we send**
   - `latitude`, `longitude` — farm location.
   - `start_date`, `end_date` — date range (`2025-01-01` … `2025-12-31` in the pipeline).
   - `daily` — three variables: `temperature_2m_mean`, `precipitation_sum`, `et0_fao_evapotranspiration`.
   - `timezone=auto`, `temperature_unit=celsius`, `precipitation_unit=mm`.

2. **Response we get**
   - `daily.time` — one date per day.
   - `daily.temperature_2m_mean` — daily mean air temperature, °C.
   - `daily.precipitation_sum` — daily rain/snow total, mm.
   - `daily.et0_fao_evapotranspiration` — daily reference evapotranspiration (FAO-56), mm.
   - `daily_units` — units for each array.
   - `latitude`, `longitude`, `elevation` — grid point used by the API.
   - `timezone`, `timezone_abbreviation`, `utc_offset_seconds`, `generationtime_ms`.

3. **What it gives us**

Open-Meteo daily:
  time: 31
  temperature_2m_mean: 31
  precipitation_sum: 31
  et0_fao_evapotranspiration: 31

### NASA POWER

1. Thermal & Temperature Metrics

• GDD10 / GDD0 (Growing Degree Days): Cumulative heat units accumulated above a base threshold of 10°C or 0°C. Used in Gate 1 to predict harvest windows and calculate if the next crop has enough thermal days to mature.
• T2M_MAX (Maximum Temperature at 2 Meters): The highest daily air temperature. Used in Gate 1 to flag heat stress and flower abortion risks during sensitive reproductive windows.
• T2M_MIN (Minimum Temperature at 2 Meters): The lowest daily air temperature. Used in Gate 1 to evaluate late-season frost risks or freezing injuries for winter crops.
• TS (Earth Skin Temperature): The actual surface temperature of the bare ground. Used in Gate 2 to determine the exact day the soil is warm enough for seed germination.
• T2MWET (Wet Bulb Temperature): Air temperature accounting for evaporation cooling. Used in Gate 3 to calculate absolute humidity bounds and canopy condensation points for disease modeling.

2. Moisture & Soil Hydrology

• GWETTOP (Surface Soil Wetness): Moisture level of the top profile layer (0 to 1 scale). Used in Gate 2 to assess seedbed readiness, crusting risks, and heavy machinery field access.
• GWETROOT (Root Zone Soil Wetness): Available moisture in the top 1 meter of soil (0 to 1 scale). Used in Gate 2 to evaluate post-harvest residual moisture and viability of non-irrigated fallback crops.
• GWETPROF (Profile Soil Moisture): Total moisture down to the bedrock layer (0 to 1 scale). Used in Gate 3 to monitor long-term regional watershed health and structural drought baselines.
• PRECTOTCORR (Precipitation): Total daily bias-corrected rainfall in millimeters. Used in Gate 3 as the primary water input parameter for calculating the field's seasonal water budget.
• SNODP (Snow Depth): Total accumulated snow blanket thickness in centimeters. Used in Gate 1/2 to evaluate soil thermal insulation during winter and predict spring planting delays.

3. Evaporation & Atmospheric Demand

• EVLAND (Evaporation Land): Total water vaporized from the ground surface and plant canopy (mm/day). Used in Gate 3 as the primary water output factor to measure real-time moisture depletion.
• EVPTRNS (Evapotranspiration Energy Flux): The structural energy driving water movement into the air. Used in Gate 3 alongside EVLAND to calculate irrigation quota fit and crop water deficits.
• RH2M (Relative Humidity): Percentage of moisture saturation in the air. Used in Gate 4 to identify combined high-heat and high-humidity microclimate triggers for fungal diseases.
• PS (Surface Pressure): Local barometric pressure profiles. Used in Gate 3 to adjust soil evaporation speeds when scaling the tool across varying geographic elevations.
• WS10M (Wind Speed): Daily wind velocity at 10 meters. Used in Gate 4 to evaluate crop lodging (falling) risks and to map out safe weather windows for chemical/pesticide spraying.

4. Solar Radiation & Energy

• ALLSKY_SFC_SW_DWN (Global Solar Radiation): Total raw sunlight energy reaching a horizontal field. Used in Gate 4 to estimate maximum photosynthetic biomass and baseline yield potential.
• ALLSKY_SFC_SW_DNI (Direct Normal Radiation): Perpendicular, unscattered solar rays. Used in Gate 3/4 to model peak daytime transpiration spikes and estimate open-canopy crop performance.
• ALLSKY_SFC_SW_DIFF (Diffuse Horizontal Radiation): Sunlight scattered by clouds or atmospheric particles. Used in Gate 4 to optimize sequence choices for multi-layered intercropping or shade-tolerant canopy understories.

Gates-

Gate 1: The Thermal Window Matrix (Predicting Rotation Timelines)

When Crop A is harvested, your engine must calculate if the oncoming climate season provides a safe, predictable timeline for Crop B to reach maturity before the next severe seasonal transition hits.
• The Check Engine: Continuous accumulation tracking.
• How to combine the parameters:
	• Accumulated Heat: Use a rolling cumulative sum of GDD10 (for warm-season crops) or GDD0 (for cool-season winter crops like wheat or mustard).
	• The Injury Trigger: Pair this with T2M_MAX and T2M_MIN. If your projected calendar places the sensitive flowering stage of Crop B in a window where historical T2M_MAX regularly spikes past critical thresholds (e.g., >35°C for lentils, which completely aborts flower fertility), the engine flags a timeline violation.
• The Code Logic:python
# Ensure crop finishes vegetative stage before high heat window strikes
if flowering_window_start <= target_date <= flowering_window_end:
    if daily_nasa_data['T2M_MAX'] > crop_critical_heat_threshold:
        recommendation_score -= 25  # Dock score for heat stress risk
Use code with caution.

Gate 2: Pre-Harvest & Sprouting Moisture Viability

When evaluating relay cropping (dropping seeds for Crop B right before or immediately after Crop A is harvested), your engine must evaluate topsoil state versus root-zone reserves.
• The Check Engine: Structural soil wetness limits.
• How to combine the parameters:
	• The Sprouting Safe Zone: Look at GWETTOP. Values between 0.40 and 0.70 indicate an ideal soft, moist seedbed. If GWETTOP drops below 0.25, the topsoil is baking into a hard crust.
	• The Long-term Reserve: Cross-reference this with GWETROOT. If GWETTOP is dry but GWETROOT is robust (>0.55), your algorithm should recommend deep-rooting, zero-tillage crops that can punch past the surface dry layer to tap the deeper water profile.
	• The Mud Trap: If GWETTOP is >0.85, the ground is waterlogged. Your tool should delay the sequence suggestion or flag a high risk of root rot for non-aquatic crops.

Gate 3: The True Evaporative Stress Index (Water Budgeting)

To calculate if a farmer will bust their local irrigation quota or drop yield due to water stress, you need to measure actual water leaving the ecosystem against rainfall entry.
• The Check Engine: Net Water Deficit balancing.
• How to combine the parameters:
	• The Atmospheric Pull: Your current parameter EVLAND gives you surface evaporation (mm/day). However, by pulling PS (Surface Pressure) and T2MWET (Wet Bulb Temperature), your model can calculate the true Vapor Pressure Deficit (VPD)—the metric that dictates exactly how hard the air is sucking moisture out of the plant leaves.
	• The Deficit Formula:
\(\text{Daily\ Soil\ Balance}=\text{PRECTOTCORR}-\text{EVLAND}\)
	• The Recommendation Action: If the cumulative negative deficit across the planned lifecycle of Crop B exceeds the farmer's irrigation buffer capacity, the sequence option is dropped or demoted in favor of a low-water consumption crop.

Gate 4: Photosynthetic Efficiency & Micro-Canopy Architecture

This determines how well a specific crop selection will convert sunlight into harvestable yield given the cloud/radiation split of that region.
• The Check Engine: Radiation Use Efficiency (RUE).
• How to combine the parameters:
	• Direct vs Diffuse Balance: Stacking ALLSKY_SFC_SW_DNI (Direct) and ALLSKY_SFC_SW_DIFF (Diffuse) tells you the quality of sunlight hitting the field.
	• The Architectural Match: Wide-canopy crops perform efficiently under direct rays (DNI). However, if your sequence is evaluating a high-density, multi-layered cropping system or an intercropped sequence (e.g., agroforestry or tall-short combinations), diffuse light (DIFF) penetrates deeper into the lower leaf layers without scorching the understory. Your algorithm can use high DIFF trends to favor shade-tolerant understory pulse crops.


## SoilGrids

API: `https://rest.isric.org/soilgrids/v2.0/properties/query` (ISRIC SoilGrids 2.0)

**What we send (3 requests, one per property group, run at the same time)**

- `lat`, `lon` — farm location.
- `property` — group 1: `clay, sand, silt`; group 2: `bdod, cfvo, phh2o`; group 3: `soc, nitrogen, cec`.
- `depth` — all six: `0-5cm`, `5-15cm`, `15-30cm`, `30-60cm`, `60-100cm`, `100-200cm`.
- `value=mean`.

**What we get back**

One value per property per depth. Depth order: `0-5cm`, `5-15cm`, `15-30cm`, `30-60cm`, `60-100cm`, `100-200cm`.
Convert with: raw value ÷ `d_factor` = target unit.

- `clay`: 343, 364, 412, 463, 458, 456 — g/kg, ÷10 → %
- `sand`: 328, 310, 277, 241, 261, 267 — g/kg, ÷10 → %
- `silt`: 329, 327, 311, 296, 281, 277 — g/kg, ÷10 → %
- `bdod`: 126, 127, 127, 132, 135, 135 — cg/cm³, ÷100 → kg/dm³
- `cfvo`: 53, 50, 52, 66, 67, 71 — cm³/dm³, ÷10 → cm³/100cm³
- `phh2o`: 58, 57, 58, 58, 59, 59 — pH×10, ÷10 → pH
- `soc`: 239, 176, 226, 336, 330, 326 — dg/kg, ÷10 → g/kg
- `nitrogen`: 167, 124, 108, 116, 122, 122 — cg/kg, ÷100 → g/kg
- `cec`: 194, 179, 178, 180, 178, 179 — mmol(c)/kg, ÷10 → cmol(c)/kg

Values are from `lat=24.0, lon=90.0`. A value is `null` where ISRIC has no data (e.g. city centres).


## FAO

API: `https://api-cropcalendar.apps.fao.org/api/v1` — Swagger at `/swagger.json`.
No auth. Every request needs `language` (`en`, `fr`, `es`, ...). Note: `lang` is ignored.
Codes are strings: `id_country` = 2 letters (`BD`), `crop_id` = 4 digits (`0024`), `zone_id` = 3 digits (`003`).

### A. Countries (lookup)

1. **Request we send:** `GET /countries?language=en`
2. **Response we get:** array of `{id: str, name: str}` (58 countries).
   Example: `{"id": "BD", "name": "Bangladesh"}`
3. **What it gives us:** name → code resolution. Other endpoints accept codes only.

### B. Crops for a country (lookup)

1. **Request we send:** `GET /countries/{id_country}/crops?language=en`
2. **Response we get:** array of crop records:
   - `crop_id: str` (4 digits), `crop_name: str`, `crop_scientific_name: str`
   - `crop_family: str`, `other_name: str`, `aditional_information: str` (sic)
   - `planting_material: str`, `id_country: str`
   - `link_image`, `link_audio`, `link_video`, `copyright: str`, `cropParent: {}`
3. **What it gives us:** which crops have a calendar in that country, plus crop name resolution.
   This is not an agronomic feasibility list, only crops with calendar data.

### C. Agro-ecological zones (lookup)

1. **Request we send:** `GET /countries/{id_country}/aez?language=en`
2. **Response we get:** array of zones:
   - `zone_id: str` (3 digits), `name: str`, `id_country: str`
   - `geographical_description: str`, `administratrative_units: str` (sic)
   - `main_agricultural_practices: str`
3. **What it gives us:** sub-national zone IDs + descriptions, used to filter calendars.

### D. Full crop calendar (primary data)

1. **Request we send:** `GET /countries/{id_country}/cropCalendar?language=en`
   - Optional `crop` (comma-separated 4-digit IDs, e.g. `crop=0024,0303`).
   - Optional `aez` (comma-separated zone IDs, e.g. `aez=003`).
   - Omit both to get every crop × zone for the country.
   - The filter param is `crop` (singular); `crops` is ignored.
2. **Response we get:** array of records:
   - `id_country: str`
   - `lastUpdated: str` (`dd/mm/yyyy`)
   - `crop: {id: str, name: str, link_image: str, copyright: str, cropParent: {}}`
   - `aez: {id: str, name: str}`
   - `sessions: [ ]` — one entry per growing season:
     - `additional_information: str` (e.g. `Rabi (winter) season`, rain/irrigation notes)
     - `comments: str` (local notes, yield, area, practices)
     - `all_year: str` (`"yes"` / `"no"`)
     - `early_sowing: {month: str, day: str}`
     - `later_sowing: {month: str, day: str}` (late sowing)
     - `early_harvest: {month: str, day: str}`
     - `late_harvest: {month: str, day: str}`
     - `growing_period: {value: str, period: "days"}` (value can be a range, e.g. `"115 - 120"`)
     - `sowing_rate: {value: str, unit: str}` (unit e.g. `kg/ha`)
3. **What it gives us:** planting and harvest windows, cycle length, seed rate, season name, local notes.
   No "peak" window, no variety, no year on dates, no explicit irrigation field.
4. **Empty answers:**
   - Unknown crop / no data → `200`, body `[]`
   - Unknown country → `204 No Content`
   - Filtered responses may omit `id_country`; unfiltered include it.

Bangladesh example (Barley in zone 003):
`early_sowing 11-01`, `later_sowing 12-30`, `early_harvest 02-23`, `late_harvest 04-25`,
`growing_period "115 - 120" days`, `sowing_rate "100 - 120" kg/ha`, `all_year "no"`.

### E. Excel export (optional)

1. **Request we send:** `GET /countries/{id_country}/cropCalendar/download?language=en`
   - Same optional `crop` and `aez` filters as D.
2. **Response we get:** binary `.xlsx`, content type
   `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`,
   `Content-Disposition: attachment; filename=Crop_Calendar_Data.xlsx`.
3. **What it gives us:** the same calendar data as a spreadsheet for offline use.

### Country → data flow

`country name → /countries (name→code) → /crops + /aez (IDs) → /cropCalendar (filtered or all)`




