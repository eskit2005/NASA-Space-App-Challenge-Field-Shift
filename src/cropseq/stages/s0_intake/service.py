"""S0 intake: a stateless chat turn -> the next question or a full profile.

1. Read the whole conversation and the current draft (frontend resends both).
2. Ask the configured extractor (LLM or rules) for fields the farmer stated.
3. If the LLM is disabled or fails, use the rules adapter; never crash.
4. Merge only valid values into the draft; never guess a missing value.
5. If something is still required, return the next question.
6. When everything is present, return `is_complete=True` plus the exact
   FarmerProfile. The frontend then calls /api/v1/recommendations/optimize.
"""

from pathlib import Path

from cropseq.config import config
from cropseq.context import load_pipeline_context
from cropseq.contracts import IntakeReply, IntakeTurn

from .adapters.llm import LlmExtractor
from .adapters.rules import RulesExtractor
from .draft import build_profile, merge_fields, missing_fields
from .ports import IntakeExtractor
from .prompts import HOLD_ON, QUESTIONS
from .qa import answer_farmer_question, detect_question

DATA = Path(__file__).resolve().parents[4] / "data" / "data_shape"
S0_INPUT = DATA / "s0_input.json"


def _build_extractor() -> tuple[IntakeExtractor, list[str]]:
    """Pick the configured adapter. LLM is opt-in through config."""
    name = (config.adapters.get("intake") or config.adapter_intake).strip().lower()
    if name == "llm":
        if not config.llm_enabled:
            return RulesExtractor(), [
                "ADAPTER_INTAKE=llm but LLM_ENABLED is false; using rules."
            ]
        return LlmExtractor(), []
    if name == "rules":
        return RulesExtractor(), []
    raise NotImplementedError(
        f"Intake adapter '{name}' is not implemented. Use 'rules' or 'llm' "
        "in ADAPTER_INTAKE."
    )


def run(turn: IntakeTurn | None = None) -> IntakeReply:
    """Process one intake turn.

    Standalone: loads data/data_shape/s0_input.json.
    """
    if turn is None:
        turn = IntakeTurn.model_validate_json(S0_INPUT.read_text(encoding="utf-8"))

    # Load context saved from all stages in the single file
    context = load_pipeline_context()
    question = detect_question(turn.messages)

    extractor, warnings = _build_extractor()
    try:
        extracted = extractor.extract(turn.messages, turn.draft)
    except Exception as exc:  # noqa: BLE001 - a model failure must not crash the chat
        warnings.append(
            f"Intake model failed ({type(exc).__name__}); used rule-based extraction."
        )
        extractor = RulesExtractor()
        extracted = extractor.extract(turn.messages, turn.draft)

    draft, merge_warnings = merge_fields(turn.draft, extracted.fields)
    warnings.extend(merge_warnings)
    missing = missing_fields(draft)

    # Check if this draft was already complete prior to this turn
    was_already_complete = not missing_fields(turn.draft)

    # If the farmer asked a question, answer it using the pipeline context from the single file
    if question is not None:
        answer = answer_farmer_question(question, context)
        if missing:
            reply = f"{answer}\n\n{QUESTIONS[missing[0]]}"
            return IntakeReply(
                reply=reply,
                draft=draft,
                missing_fields=missing,
                is_complete=False,
                profile=None,
                warnings=warnings,
                source=f"S0 intake ({extractor.name})",
            )
        else:
            profile = build_profile(turn, draft)
            reply = answer if was_already_complete else f"{answer}\n\n{HOLD_ON}"
            return IntakeReply(
                reply=reply,
                draft=draft,
                missing_fields=[],
                is_complete=True,
                profile=profile,
                warnings=warnings,
                source=f"S0 intake ({extractor.name})",
            )

    if missing:
        reply = extracted.reply.strip() if isinstance(extracted.reply, str) else ""
        return IntakeReply(
            reply=reply or QUESTIONS[missing[0]],
            draft=draft,
            missing_fields=missing,
            is_complete=False,
            profile=None,
            warnings=warnings,
            source=f"S0 intake ({extractor.name})",
        )

    profile = build_profile(turn, draft)
    reply = HOLD_ON
    if not was_already_complete:
        if draft.attributes.get("irrigation_method") is None:
            reply = (
                "Thanks - I have your core farm details! Hold on while I prepare your crop rotation options. "
                "Optional: What irrigation method do you use (tube well, canal, pond, or rain-fed)? "
                "You can select an option below, or click 'Proceed to Review' to use standard defaults."
            )
    else:
        updated_notes: list[str] = []
        if extracted.fields.get("soil_ph") is not None:
            updated_notes.append(f"soil pH to {extracted.fields['soil_ph']}")
        if extracted.fields.get("irrigation_method") is not None:
            method_name = str(extracted.fields["irrigation_method"]).replace("_", " ")
            updated_notes.append(f"irrigation method to {method_name}")
        if updated_notes:
            reply = (
                f"Noted! Updated your {', and '.join(updated_notes)}. "
                "Hold on while I update your crop rotation profile, or click 'Proceed to Review' to continue."
            )

    return IntakeReply(
        reply=reply,
        draft=draft,
        missing_fields=[],
        is_complete=True,
        profile=profile,
        warnings=warnings,
        source=f"S0 intake ({extractor.name})",
    )
