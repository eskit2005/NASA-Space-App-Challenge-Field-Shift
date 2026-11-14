"""Tests for Stage 0 Q&A capability and single pipeline context file."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cropseq.config import config
from cropseq.context import get_context_path, load_pipeline_context, save_pipeline_context
from cropseq.contracts import (
    FarmerDraft,
    FarmerProfile,
    IntakeMessage,
    IntakeTurn,
    Location,
)
from cropseq.pipeline import run as run_pipeline
from cropseq.stages.s0_intake.qa import answer_farmer_question, detect_question
from cropseq.stages.s0_intake.service import run as run_intake


def _make_turn(*messages: str, draft: FarmerDraft | None = None) -> IntakeTurn:
    return IntakeTurn(
        messages=[
            IntakeMessage(role="farmer", content=m) for m in messages
        ],
        draft=draft or FarmerDraft(),
        farm_id="farm-test-qa",
    )


def test_single_context_file_exists_and_has_all_stages() -> None:
    """Verify whatever was produced in every stage is saved into one single file."""
    context_path = get_context_path()
    context = load_pipeline_context()

    assert context_path.is_file()
    assert "stages" in context
    assert "summary" in context

    stages = context["stages"]
    # All stages present in the single file
    assert "s1_farmer" in stages
    assert "s2_raw_environment" in stages
    assert "s3_environment" in stages
    assert "s4_feasible_crops" in stages
    assert "s5_sequence_pool" in stages
    assert "s6_mathematical_solution" in stages
    assert "s7_explanation" in stages
    assert "s8_final_result" in stages

    summary = context["summary"]
    assert "mathematical_solution" in summary
    assert "crop_list" in summary
    assert "sequence_pool" in summary
    assert "best_rotation" in summary


def test_detect_farmer_question() -> None:
    # Pure intake answer -> None
    assert detect_question([IntakeMessage(role="farmer", content="12.5 hectares")]) is None
    assert detect_question([IntakeMessage(role="farmer", content="Raninagar")]) is None

    # Explicit question mark -> Detected
    assert detect_question([IntakeMessage(role="farmer", content="Why this rotation?")]) == "Why this rotation?"
    assert detect_question([IntakeMessage(role="farmer", content="What if I have less water?")]) == "What if I have less water?"

    # Keyword questions -> Detected
    assert detect_question([IntakeMessage(role="farmer", content="Why not rice every season")]) is not None
    assert detect_question([IntakeMessage(role="farmer", content="Which crop is riskiest")]) is not None
    assert detect_question([IntakeMessage(role="farmer", content="Explain the mathematical solution")]) is not None


def test_answer_why_this_rotation() -> None:
    context = load_pipeline_context()
    answer = answer_farmer_question("Why this rotation?", context)

    assert "recommended rotation" in answer.lower()
    assert "pareto" in answer.lower()
    assert "gross margin" in answer.lower()
    assert "water" in answer.lower()


def test_answer_less_water() -> None:
    context = load_pipeline_context()
    answer = answer_farmer_question("What if I have less water?", context)

    assert "water" in answer.lower()
    assert "pareto" in answer.lower() or "drought" in answer.lower()


def test_answer_rice_monoculture() -> None:
    context = load_pipeline_context()
    answer = answer_farmer_question("Why not rice every season?", context)

    assert "rice" in answer.lower()
    assert "pest" in answer.lower() or "nitrogen" in answer.lower() or "soil" in answer.lower()


def test_answer_crop_risk() -> None:
    context = load_pipeline_context()
    answer = answer_farmer_question("Which crop is riskiest?", context)

    assert "risk" in answer.lower()
    assert "crop" in answer.lower()


def test_answer_crop_list() -> None:
    context = load_pipeline_context()
    answer = answer_farmer_question("What crops can grow here?", context)

    assert "feasible crops" in answer.lower()
    assert "rabi" in answer.lower() or "kharif" in answer.lower()


def test_stage0_intake_answers_question_and_asks_for_missing_field() -> None:
    """When intake is incomplete and farmer asks a question, S0 answers AND asks for next field."""
    turn = _make_turn("What crops can grow here?")
    reply = run_intake(turn)

    assert reply.is_complete is False
    assert "location" in reply.missing_fields
    # Answers the question based on context
    assert "feasible crops" in reply.reply.lower() or "rabi" in reply.reply.lower()
    # Also asks the missing field question
    assert "where is your farm" in reply.reply.lower()


def test_stage0_intake_answers_question_when_profile_complete() -> None:
    """When profile is already complete, asking a question returns the grounded answer directly."""
    completed_draft = FarmerDraft(
        location=Location(latitude=24.0, longitude=90.0),
        area_ha=10.0,
        budget_usd=5000.0,
        irrigation_quota_m3=30000.0,
        land_type="MHL",
    )
    turn = _make_turn("Why this rotation?", draft=completed_draft)
    reply = run_intake(turn)

    assert reply.is_complete is True
    assert reply.missing_fields == []
    assert "recommended rotation" in reply.reply.lower()
    assert "gross margin" in reply.reply.lower()
