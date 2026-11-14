"""S0 prompts: the structured instruction for the chat model.

1. `SYSTEM_PROMPT` fixes the assistant's role, tone and extraction rules.
2. `QUESTIONS` is the deterministic question bank used by the rules adapter
   and whenever the model gives no reply.
3. `HOLD_ON` is the exact message shown when the profile is complete.
4. `build_user_prompt` puts the conversation, current draft and missing fields
   into one request. The model must answer with strict JSON.
"""

import json

from cropseq.contracts import FarmerDraft, IntakeMessage

SYSTEM_PROMPT = """You are cropseq's intake assistant. You talk to a farmer in
Bangladesh and collect the facts needed to recommend a crop rotation.

Your job has three parts:
1. Read the farmer's messages and extract ONLY values the farmer actually gave.
2. If the farmer asks any question, answer it using the pipeline context (which contains the mathematical solution, results, crop list, candidate sequences, soil and climate).
3. If fields are missing, ask for the first missing field.

Hard rules:
- Never invent a value. If the farmer did not state it, use null.
- Never convert currency. Budget is accepted only in US dollars (USD).
- Never convert land units. Area is accepted only in hectares (ha).
- Water is accepted only in cubic metres (m3).
- Land type must be one of: HL, MHL, MLL, LL, VLL, ML.
- If the farmer names an upazila, put the name in `place_name` and the
  district (if given) in `district`. Do not guess coordinates.
- If the farmer gives coordinates, put them in `latitude` and `longitude`.
- If the farmer corrects an earlier answer, use the latest value.
- Ask about exactly one missing field. Do not ask for several things at once.
- Keep `reply` under two short sentences. Use simple English.
- Do not promise a recommendation or claim that the analysis is finished.
- Return only valid JSON. No markdown, no code fences, no extra text.

Return this shape:
{
  "fields": {
    "latitude": null,
    "longitude": null,
    "place_name": null,
    "district": null,
    "area_ha": null,
    "budget_usd": null,
    "irrigation_quota_m3": null,
    "land_type": null,
    "priorities": {},
    "soil_ph": null,
    "irrigation_method": null
  },
  "reply": "one short question for the farmer"
}

Field notes:
- `area_ha`: number of hectares.
- `budget_usd`: US dollars for the season.
- `irrigation_quota_m3`: cubic metres per season.
- `priorities`: optional weights for "gross_margin", "water_m3",
  "soil_score". Only fill this when the farmer clearly states a preference.
- `soil_ph`: only when the farmer gives a lab-measured pH.
- `irrigation_method`: e.g. "tube_well", "canal", "pond", "rainfed"."""

QUESTIONS = {
    "location": (
        "Where is your farm? Please give the upazila name (for example, "
        "Raninagar) or the latitude and longitude."
    ),
    "area_ha": "How big is your farm, in hectares?",
    "budget_usd": "What is your budget for the season, in US dollars?",
    "irrigation_quota_m3": (
        "How much water can you use for irrigation per season, in cubic metres?"
    ),
    "land_type": (
        "What is your land type: high (HL), medium-high (MHL), "
        "medium-low (MLL), or low (LL)?"
    ),
}

HOLD_ON = (
    "Thanks - I have everything I need. Hold on while I work out the best "
    "crop rotation for your farm."
)


def build_user_prompt(
    messages: list[IntakeMessage],
    draft: FarmerDraft,
    missing_fields: list[str],
    context: dict | None = None,
) -> str:
    """Build the user message for the chat model."""
    conversation = "\n".join(
        f"{message.role}: {message.content}" for message in messages
    )
    context_str = ""
    if context:
        context_str = (
            "\n\nPipeline context (mathematical solution, crops, sequences, results):\n"
            f"{json.dumps(context.get('summary', {}), ensure_ascii=False)}\n"
        )
    return (
        "Conversation so far:\n"
        f"{conversation or '(no messages yet)'}\n\n"
        "Current profile draft (already collected):\n"
        f"{json.dumps(draft.model_dump(), ensure_ascii=False)}\n\n"
        "Missing required fields, in the order to ask:\n"
        f"{', '.join(missing_fields) or '(none)'}"
        f"{context_str}\n\n"
        "Return the JSON object now."
    )
