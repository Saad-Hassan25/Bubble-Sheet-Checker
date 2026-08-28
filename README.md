# Bubble Sheet Checker

<p align="center"><img src="assets/logo.svg" width="160" alt="Bubble Sheet Checker logo"></p>

Grade a multiple-choice bubble sheet from one image. The script detects circular answer bubbles, groups them into a question grid, identifies filled choices, and optionally scores them against an answer key.

## Features

- No Jupyter setup: run a single Python command.
- Detects 10-question, 4-option sheets by default; both values are configurable.
- Handles a photographed rectangular sheet by correcting its perspective when a page border is found.
- Writes an annotated result image and can also write a JSON report.
- Marks selected bubbles in green, invalid multi-selections in orange, and answer-key bubbles with a blue ring.

## Install

Requires Python 3.9 or later.

```bash
git clone https://github.com/Saad-Hassan25/Bubble-Sheet-Checker.git
cd Bubble-Sheet-Checker
python -m venv .venv
```

Activate the virtual environment, then install dependencies:

```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Quick start

The repository includes a filled sample. Run:

```bash
python bubble_sheet_checker.py \
  --image "Bubble Sheets Examples/BST1.png" \
  --answers "A,B,A,C,B,D,B,A,C,A" \
  --output graded_sheet.png \
  --json grade_report.json
```

PowerShell uses a backtick for line continuation, or place the command on one line:

```powershell
python bubble_sheet_checker.py --image "Bubble Sheets Examples/BST1.png" --answers "A,B,A,C,B,D,B,A,C,A" --output graded_sheet.png --json grade_report.json
```

The command prints one result per question and writes `graded_sheet.png`. The included sample has nine correct answers and one incorrect answer using the key above, for a score of `8.75/10` under the default marking scheme.

## Command reference

```text
python bubble_sheet_checker.py --image IMAGE [--answers A,B,C,...]
                               [--questions 10] [--choices 4]
                               [--fill-threshold 0.35]
                               [--output graded_sheet.png]
                               [--json report.json]
```

| Option | Meaning |
| --- | --- |
| `--image` | Required path to the bubble-sheet image. |
| `--answers` | Comma-separated answer key. Leave out to detect answers without grading. |
| `--questions` / `--choices` | Number of rows and options per row. Defaults to `10` and `4`. |
| `--fill-threshold` | Portion of a bubble centre that must be dark to count as filled. Raise it for noisy scans; lower it for light pencil marks. |
| `--output` | Annotated output image path. |
| `--json` | Optional structured report path. |

Scoring with an answer key is: correct `+1`, incorrect `-0.25`, multiple choices `-0.5`, and unanswered `0`.

## Sheet guidelines

- Keep the sheet flat, well lit, and in focus.
- Ensure every answer bubble has the same approximate size.
- Use dark, solid fills; avoid check marks that leave most of a bubble white.
- Keep all question rows and choice columns visible. A visible rectangular border improves perspective correction.

If light marks are reported as unanswered, try `--fill-threshold 0.25`. If printed outlines are being misread as marks, try `--fill-threshold 0.45`.

## Project layout

```text
bubble_sheet_checker.py       Command-line grader
requirements.txt              Runtime dependencies
assets/logo.svg               Repository avatar/logo
examples/answer_key.txt       Example answer key
Bubble Sheets Examples/       Blank and filled sample images
```

## License

This coursework project currently has no license file. Add an explicit license before distributing or accepting outside contributions.

