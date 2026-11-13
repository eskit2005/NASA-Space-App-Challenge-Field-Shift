"""S7 template explainer: deterministic text built from the S6 numbers.

1. Pick the sequence with the highest weighted `notes.score` (fallback: margin).
2. Write one summary and four short sections from that sequence's metrics.
3. List every sequence that repeats an exhaustive crop as a rotation risk.
4. Always add the placeholder-data caveat when S6 said the data is mock.
5. Emit a single evidence reference pointing back to S6.

No network, no model, no randomness.
"""

from cropseq.contracts import (
    EvaluatedSequences,
    EvidenceReference,
    Explanation,
)

from ..select import best_sequence, crops_text

PLACEHOLDER_CAVEAT = (
    "Crop prices, input costs and nitrogen values are placeholders, "
    "not agronomic advice. Ask an expert before planting."
)


class TemplateExplainer:
    """Deterministic explainer that never calls a model."""

    name = "template"

    def explain(self, evaluated: EvaluatedSequences) -> Explanation:
        sequences = evaluated.sequences
        if not sequences:
            return Explanation(
                summary=(
                    "No crop sequence passed the rotation rules for this farm, "
                    "so there is nothing to recommend yet."
                ),
                sections={
                    "water": "Not scored.",
                    "soil": "Not scored.",
                    "rotation_risk": "Not scored.",
                    "caveat": "Check the warnings from the earlier stages.",
                },
                evidence=[],
                generated_by="template",
                warnings=list(evaluated.warnings),
                source="S7 template explainer",
            )

        best = best_sequence(sequences)
        margin = best.metrics["gross_margin"]
        water = best.metrics["water_m3"]
        soil = best.metrics["soil_score"]
        supplied = best.notes.get("irrigation_used_m3", "unknown")
        nitrogen_start = best.notes.get("nitrogen_start_kg_ha", "unknown")
        nitrogen_end = best.notes.get("nitrogen_end_kg_ha", "unknown")

        summary = (
            f"Sequence {best.sequence_id} ({crops_text(best)}) gives the best balance "
            f"for your priorities. It earns about ${margin:,.0f}, needs "
            f"{water:,.0f} m3 of irrigation, and ends with a soil score of "
            f"{soil:.2f}."
        )

        water_section = (
            f"Irrigation demand is {water:,.0f} m3. The plan supplies "
            f"{supplied} m3 from your quota; any shortfall lowers yield."
        )
        soil_section = (
            f"Soil nitrogen moves from {nitrogen_start} to {nitrogen_end} kg/ha "
            f"across the rotation. The soil score of {soil:.2f} rewards nitrogen "
            f"gain and penalises nitrogen below the critical level."
        )
        risky = [
            sequence.sequence_id
            for sequence in sequences
            if "rotation_warning" in sequence.notes
        ]
        if risky:
            rotation_section = (
                "Two exhaustive crops sit next to each other in: "
                f"{', '.join(risky)}. That draws down soil nitrogen faster."
            )
        else:
            rotation_section = "No sequence puts two exhaustive crops back to back."

        placeholder = any(
            sequence.notes.get("data_quality") == "placeholder"
            for sequence in sequences
        )
        caveat = PLACEHOLDER_CAVEAT if placeholder else "Scores come from the S6 model."

        return Explanation(
            summary=summary,
            sections={
                "water": water_section,
                "soil": soil_section,
                "rotation_risk": rotation_section,
                "caveat": caveat,
            },
            evidence=[
                EvidenceReference(
                    source_id="ev-001",
                    title="S6 evaluation",
                    url=None,
                    claim=(
                        f"{best.sequence_id} is "
                        f"{'Pareto-optimal' if best.is_pareto_optimal else 'not Pareto-optimal'} "
                        f"with gross_margin={margin:.2f}, water_m3={water:.2f}, "
                        f"soil_score={soil:.4f}."
                    ),
                )
            ],
            generated_by="template",
            warnings=list(evaluated.warnings),
            source="S7 template explainer",
        )
