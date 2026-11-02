"""Quiz schema validation and export round-trip."""

import pytest
from app.schemas.content import ExerciseData, QuizItemIn
from pydantic import ValidationError


def _exercise(**quiz):
    return {
        "type": "recall",
        "prompt": "Say hello",
        "code": "print('hi')",
        "check": {"mode": "answers", "accepted_answers": ["print('hi')"]},
        "quiz": quiz.get("quiz", []),
    }


def test_quiz_item_rejects_wrong_equal_to_answer() -> None:
    with pytest.raises(ValidationError, match="Wrong answer matches"):
        QuizItemIn.model_validate(
            {
                "kind": "output",
                "q": "What does this print?",
                "code": "print(1)",
                "answer": "1",
                "wrong": ["1", "2"],
                "why": "It prints 1.",
            }
        )


def test_quiz_rejects_more_than_six() -> None:
    items = [
        {
            "kind": "concept",
            "q": f"Question {i}",
            "answer": "a",
            "wrong": ["b"],
        }
        for i in range(7)
    ]
    with pytest.raises(ValidationError):
        ExerciseData.model_validate(_exercise(quiz=items))


def test_exercise_data_round_trips_quiz() -> None:
    data = ExerciseData.model_validate(
        _exercise(
            quiz=[
                {
                    "kind": "output",
                    "q": "What does this print?",
                    "code": "print(2 + 2)",
                    "answer": "4",
                    "wrong": ["22", "2 + 2"],
                    "why": "Python adds the numbers first.",
                }
            ]
        )
    )
    dumped = data.model_dump()
    again = ExerciseData.model_validate(dumped)
    assert len(again.quiz) == 1
    assert again.quiz[0].answer == "4"
    assert again.quiz[0].wrong == ["22", "2 + 2"]
