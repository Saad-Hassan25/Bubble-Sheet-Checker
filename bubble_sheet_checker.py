#!/usr/bin/env python3
"""Grade multiple-choice bubble sheets from an image.

The detector finds circular bubbles, arranges them into a question/choice grid,
and classifies each bubble from the ink inside its centre.  It works best with
clean, high-contrast sheets where every choice uses the same bubble size.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np


STATUS_UNANSWERED = "Unanswered"
STATUS_INVALID = "Invalid"


@dataclass
class QuestionResult:
    """The detected choice and score for one question."""

    question: int
    selected: str
    expected: str | None
    score: float
    fill_ratios: dict[str, float]


@dataclass
class GradeReport:
    """The machine-readable result of grading a sheet."""

    questions: list[QuestionResult]
    correct: int
    incorrect: int
    invalid: int
    unanswered: int
    score: float
    maximum_score: float


def order_corners(points: np.ndarray) -> np.ndarray:
    """Return four points ordered as top-left, top-right, bottom-left, bottom-right."""
    points = points.reshape(4, 2).astype(np.float32)
    ordered = np.zeros((4, 2), dtype=np.float32)
    sums = points.sum(axis=1)
    differences = np.diff(points, axis=1).ravel()
    ordered[0] = points[np.argmin(sums)]
    ordered[3] = points[np.argmax(sums)]
    ordered[1] = points[np.argmin(differences)]
    ordered[2] = points[np.argmax(differences)]
    return ordered


def find_sheet_corners(image: np.ndarray) -> np.ndarray | None:
    """Find a large rectangular sheet border, if the photograph contains one."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    image_area = image.shape[0] * image.shape[1]

    candidates: list[tuple[float, np.ndarray]] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < image_area * 0.10:
            continue
        perimeter = cv2.arcLength(contour, True)
        approximation = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approximation) == 4 and cv2.isContourConvex(approximation):
            candidates.append((area, approximation))

    if not candidates:
        return None
    return order_corners(max(candidates, key=lambda item: item[0])[1])


def rectify_sheet(image: np.ndarray) -> np.ndarray:
    """Perspective-correct the detected page border, or return a copy unchanged."""
    corners = find_sheet_corners(image)
    if corners is None:
        return image.copy()

    top = np.linalg.norm(corners[1] - corners[0])
    bottom = np.linalg.norm(corners[3] - corners[2])
    left = np.linalg.norm(corners[2] - corners[0])
    right = np.linalg.norm(corners[3] - corners[1])
    width, height = int(max(top, bottom)), int(max(left, right))
    if width < 100 or height < 100:
        return image.copy()

    destination = np.float32([[0, 0], [width - 1, 0], [0, height - 1], [width - 1, height - 1]])
    transform = cv2.getPerspectiveTransform(corners, destination)
    return cv2.warpPerspective(image, transform, (width, height))


def resize_for_detection(image: np.ndarray, longest_edge: int = 1600) -> tuple[np.ndarray, float]:
    """Downscale very large input to keep circle detection fast and consistent."""
    height, width = image.shape[:2]
    scale = min(1.0, longest_edge / max(height, width))
    if scale == 1.0:
        return image, 1.0
    return cv2.resize(image, (round(width * scale), round(height * scale))), scale


def find_bubbles(image: np.ndarray, questions: int) -> np.ndarray:
    """Detect candidate answer bubbles using Hough circles."""
    detection_image, scale = resize_for_detection(image)
    gray = cv2.cvtColor(detection_image, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)
    expected_radius = max(8, round(detection_image.shape[0] / (questions * 7)))
    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=max(18, expected_radius * 2),
        param1=100,
        param2=24,
        minRadius=max(6, round(expected_radius * 0.45)),
        maxRadius=round(expected_radius * 2.2),
    )
    if circles is None:
        raise ValueError("No answer bubbles were detected. Use a sharper, well-lit image.")
    circles = np.round(circles[0]).astype(np.float32)
    circles[:, :2] /= scale
    circles[:, 2] /= scale
    # Hough detection also picks up letter counters (for example the hole in a
    # printed ``D``).  If radii form two clearly separated families, retain
    # the larger one. A cropped sheet normally has only answer bubbles, so we
    # deliberately leave a single, tightly grouped family untouched.
    radii = np.sort(circles[:, 2])
    gaps = np.diff(radii)
    if len(gaps):
        split = int(np.argmax(gaps))
        if gaps[split] >= radii[-1] * 0.20:
            circles = circles[circles[:, 2] >= radii[split + 1]]
    return circles


def cluster_axis(values: np.ndarray, groups: int) -> np.ndarray:
    """Cluster one coordinate into evenly reusable grid locations without extra packages."""
    if len(values) < groups:
        raise ValueError("Too few bubbles were detected to form the requested grid.")
    centres = np.quantile(values, np.linspace(0, 1, groups))
    for _ in range(40):
        labels = np.abs(values[:, None] - centres).argmin(axis=1)
        updated = np.array([
            values[labels == index].mean() if np.any(labels == index) else centres[index]
            for index in range(groups)
        ])
        if np.allclose(centres, updated, atol=0.1):
            break
        centres = updated
    return np.sort(centres)


def build_bubble_grid(circles: np.ndarray, questions: int, choices: int) -> np.ndarray:
    """Map detected circles to a [question, choice] grid."""
    if len(circles) < questions * choices:
        raise ValueError(
            f"Detected {len(circles)} circles, but the requested layout needs at least {questions * choices}."
        )
    rows = cluster_axis(circles[:, 1], questions)
    columns = cluster_axis(circles[:, 0], choices)
    grid = np.empty((questions, choices, 3), dtype=np.float32)

    for row, y in enumerate(rows):
        for column, x in enumerate(columns):
            distance = np.hypot(circles[:, 0] - x, circles[:, 1] - y)
            circle = circles[np.argmin(distance)]
            grid[row, column] = circle
    return grid


def ink_ratio(thresholded: np.ndarray, circle: np.ndarray) -> float:
    """Measure black ink in the centre of a bubble, ignoring its printed outline."""
    x, y, radius = np.round(circle).astype(int)
    mask = np.zeros(thresholded.shape, dtype=np.uint8)
    cv2.circle(mask, (x, y), max(2, int(radius * 0.60)), 255, cv2.FILLED)
    return float(cv2.countNonZero(cv2.bitwise_and(thresholded, thresholded, mask=mask)) / cv2.countNonZero(mask))


def parse_answers(value: str | None, choices: int) -> list[str] | None:
    """Validate a comma-separated answer key."""
    if not value:
        return None
    answers = [answer.strip().upper() for answer in value.split(",") if answer.strip()]
    valid = set(option_labels(choices))
    invalid = [answer for answer in answers if answer not in valid]
    if invalid:
        raise ValueError(f"Invalid answer key entries: {', '.join(invalid)}")
    return answers


def option_labels(choices: int) -> list[str]:
    if not 1 <= choices <= 26:
        raise ValueError("--choices must be between 1 and 26.")
    return [chr(ord("A") + index) for index in range(choices)]


def grade_sheet(
    image: np.ndarray,
    questions: int,
    choices: int,
    answers: Sequence[str] | None,
    fill_threshold: float,
) -> tuple[GradeReport, np.ndarray]:
    """Detect, score, and annotate a bubble sheet."""
    if answers is not None and len(answers) != questions:
        raise ValueError("The answer key must contain exactly --questions answers.")
    if not 0 < fill_threshold < 1:
        raise ValueError("--fill-threshold must be between 0 and 1.")

    sheet = rectify_sheet(image)
    grid = build_bubble_grid(find_bubbles(sheet, questions), questions, choices)
    gray = cv2.cvtColor(sheet, cv2.COLOR_BGR2GRAY)
    thresholded = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    labels = option_labels(choices)
    results: list[QuestionResult] = []
    annotation = sheet.copy()

    for row in range(questions):
        ratios = {labels[column]: ink_ratio(thresholded, grid[row, column]) for column in range(choices)}
        selected_labels = [label for label, ratio in ratios.items() if ratio >= fill_threshold]
        selected = selected_labels[0] if len(selected_labels) == 1 else (
            STATUS_UNANSWERED if not selected_labels else STATUS_INVALID
        )
        expected = answers[row] if answers else None
        score = 0.0 if expected is None or selected == STATUS_UNANSWERED else (
            1.0 if selected == expected else (-0.5 if selected == STATUS_INVALID else -0.25)
        )
        results.append(QuestionResult(row + 1, selected, expected, score, ratios))

        for column, label in enumerate(labels):
            x, y, radius = np.round(grid[row, column]).astype(int)
            if label in selected_labels:
                color = (0, 165, 255) if selected == STATUS_INVALID else (0, 180, 0)
                cv2.circle(annotation, (x, y), int(radius * 1.18), color, 4)
            if expected == label:
                cv2.circle(annotation, (x, y), int(radius * 1.32), (255, 140, 0), 2)

    correct = sum(item.score == 1 for item in results)
    invalid = sum(item.selected == STATUS_INVALID for item in results)
    unanswered = sum(item.selected == STATUS_UNANSWERED for item in results)
    incorrect = questions - correct - invalid - unanswered
    report = GradeReport(
        questions=results,
        correct=correct,
        incorrect=incorrect,
        invalid=invalid,
        unanswered=unanswered,
        score=sum(item.score for item in results),
        maximum_score=float(questions) if answers else 0.0,
    )
    return report, annotation


def print_report(report: GradeReport) -> None:
    for item in report.questions:
        expected = f" | key: {item.expected}" if item.expected else ""
        print(f"Q{item.question:02}: {item.selected}{expected} | {item.score:+.2f}")
    print(
        f"\nScore: {report.score:.2f}/{report.maximum_score:.0f} | "
        f"correct: {report.correct}, incorrect: {report.incorrect}, "
        f"invalid: {report.invalid}, unanswered: {report.unanswered}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Grade a multiple-choice bubble-sheet image.")
    parser.add_argument("--image", required=True, type=Path, help="Path to a bubble-sheet image.")
    parser.add_argument("--answers", help="Comma-separated key, for example: A,B,A,C")
    parser.add_argument("--questions", type=int, default=10, help="Number of question rows (default: 10).")
    parser.add_argument("--choices", type=int, default=4, help="Choices per question (default: 4).")
    parser.add_argument("--fill-threshold", type=float, default=0.35, help="Ink ratio that counts as filled (default: 0.35).")
    parser.add_argument("--output", type=Path, default=Path("graded_sheet.png"), help="Annotated image destination.")
    parser.add_argument("--json", dest="json_output", type=Path, help="Optional JSON report destination.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.questions < 1:
        raise ValueError("--questions must be positive.")
    image = cv2.imread(str(args.image))
    if image is None:
        raise ValueError(f"Could not read image: {args.image}")
    report, annotation = grade_sheet(
        image, args.questions, args.choices, parse_answers(args.answers, args.choices), args.fill_threshold
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(args.output), annotation):
        raise OSError(f"Could not write output image: {args.output}")
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    print_report(report)
    print(f"Annotated image: {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(2)

