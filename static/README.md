# 🧮 AI Math Solver Web App

A simple full-stack Python web app using **Flask + SymPy** to solve and simplify math expressions with pretty LaTeX output using **MathJax**.

## 🚀 Features
- Supports integration, differentiation, solving equations, limits, and simplification.
- Clean Bootstrap UI with LaTeX-rendered answers.
- Backend powered by SymPy.

## 🧠 Example Inputs
- `integrate(x^2, x)`
- `diff(sin(x), x)`
- `solve(x^2 - 4, x)`
- `limit(sin(x)/x, x, 0)`

## 🛠 Setup

```bash
git clone <your-repo-url>
cd math_solver_ai
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python app.py
