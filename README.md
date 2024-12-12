# Bubble Sheet MCQ Checker

A simple tool for automatically checking answers on a bubble sheet. The user uploads an image of a bubble sheet containing 10 multiple-choice questions (MCQs), and the application processes the image, identifies the marked answers, and grades them.

## Features
- Processes images of bubble sheets.
- Automatically detects answers marked on the sheet.
- Compares detected answers with a predefined answer key.
- Calculates and displays the total score.

## Prerequisites
To run this project, ensure you have the following installed:
- Python 3.7 or higher
- Required Python libraries:
  - OpenCV
  - NumPy
  - Matplotlib

## Usage
1. Open the `Bubble Sheet Checker.ipynb` notebook in Jupyter Notebook or JupyterLab.
2. Provide the path of the image.
3. Run the notebook cells step-by-step:
   - Load and preprocess the image.
   - Define the answer key.
   - Process and grade the bubble sheet.
4. View the graded results, including the total score and visualizations of detected answers.

## Answer Key
Modify the answer key in the code to match your bubble sheet. For example:
```python
answer_key = ['A', 'B', 'A', 'C', 'B', 'D', 'B', 'A', 'C', 'A']
```

## Example Output
- Graded results: `Score: 8/10`
- Visualization of detected answers with correct/incorrect marks.

## Acknowledgments
This project was developed as part of a project in Computer Vision course. Contributions and suggestions are welcome!
