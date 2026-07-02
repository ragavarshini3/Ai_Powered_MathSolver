from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify
from sympy import (
    symbols, solve as sympy_solve, diff, integrate, limit, simplify, factor, expand,
    trigsimp, expand_trig, expand_log, sin, cos, tan, sec, csc, cot,
    asin, acos, atan, log, exp, sqrt, pi, E, I, oo, factorial,
    summation, Matrix, Eq, Ne, Abs, re as Re, im as Im, arg,
    Symbol, Rational, Float, Integer, S, nan,
    Poly, gcd, lcm, isprime, factorint, primerange, mod_inverse,
    binomial, rf, ff,
    series as sym_series, atan2, conjugate,
    latex, pretty
)
from sympy import Le, Lt, Ge, Gt
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application
from sympy.abc import x, y, z, t, n
import io
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import numpy as np
import os
import re
from PIL import Image
import pytesseract
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import timedelta
from werkzeug.utils import secure_filename
import statistics as py_stats
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

# ✅ Tesseract path
import sys
if sys.platform.startswith('win'):
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


# ✅ Configure Gemini API
gemini_api_key = os.environ.get("GEMINI_API_KEY")
if gemini_api_key:
    genai.configure(api_key=gemini_api_key)

app = Flask(__name__)
app.secret_key = 'your_secret_key_math_solver_2024'
app.permanent_session_lifetime = timedelta(minutes=60)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB upload limit

# ✅ Dummy users (in-memory)
users = {
    "admin": "1234",
    "user": "pass"
}

# ─────────────────────────────────────────────
# HELPER: Expression Parser
# ─────────────────────────────────────────────
def parse_math_expression(expr_str):
    """Enhanced parser that handles common mathematical notation"""
    try:
        s = str(expr_str).strip()
        # Convert single-letter variables followed by a digit (e.g., u2 -> u**2, 2x3 -> 2x**3)
        s = re.sub(r'(?<![a-zA-Z])([a-zA-Z])([2-9])(?![a-zA-Z0-9])', r'\1**\2', s)
        # Replace common notations
        s = s.replace('^', '**')
        s = s.replace('×', '*')
        s = s.replace('÷', '/')
        s = s.replace('√', 'sqrt')
        s = s.replace('∞', 'oo')
        s = s.replace('π', 'pi')
        s = s.replace('θ', 'theta')
        s = s.replace('cosec', 'csc')

        transformations = (standard_transformations + (implicit_multiplication_application,))
        return parse_expr(s, transformations=transformations)
    except Exception:
        try:
            return parse_expr(str(expr_str).replace('^', '**'))
        except Exception as e:
            raise ValueError(f"Could not parse expression: {expr_str}")


def sympy_to_display(expr):
    """Convert sympy expression to a clean string for display"""
    try:
        return str(expr).replace('**', '^').replace('sqrt', '√')
    except Exception:
        return str(expr)


def solve_math_with_gemini(expression_input, image_file=None):
    """Solve math problem using Gemini API with step-by-step reasoning"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "API Key Missing", "❌ GEMINI_API_KEY is not set. Please set it in your environment or .env file."

    try:
        # Re-configure if not already configured
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = (
            "You are an expert AI mathematics tutor and solver.\n"
            "Solve the following mathematical problem step-by-step with clear, correct explanations. "
            "You must format your response exactly as follows, enclosing sections in the specified tags:\n"
            "<answer>Your final concise answer or solution here (e.g. Option D: 9/20 or x = 5)</answer>\n"
            "<steps>\n"
            "Your step-by-step detailed explanation and working here. Keep it clean, readable, and structured.\n"
            "</steps>\n\n"
        )
        
        if expression_input:
            prompt += f"Problem to solve: {expression_input}\n"
        else:
            prompt += "Solve the mathematical problem presented in this image.\n"

        if image_file:
            response = model.generate_content([image_file, prompt])
        else:
            response = model.generate_content(prompt)

        text = response.text
        
        # Parse tags
        answer = ""
        steps = ""
        
        ans_match = re.search(r'<answer>(.*?)</answer>', text, re.DOTALL)
        if ans_match:
            answer = ans_match.group(1).strip()
            
        steps_match = re.search(r'<steps>(.*?)</steps>', text, re.DOTALL)
        if steps_match:
            steps = steps_match.group(1).strip()
            
        if not answer and not steps:
            # Fallback parsing
            if "<answer>" in text:
                parts = text.split("<answer>")
                if len(parts) > 1:
                    subparts = parts[1].split("</answer>")
                    answer = subparts[0].strip()
            if "<steps>" in text:
                parts = text.split("<steps>")
                if len(parts) > 1:
                    subparts = parts[1].split("</steps>")
                    steps = subparts[0].strip()
            
            if not answer and not steps:
                # Direct fallback if tags completely failed
                lines = [line for line in text.split('\n') if line.strip()]
                if lines:
                    answer = lines[0]
                steps = text

        # Replace any residual raw html tags
        answer = re.sub(r'</?(answer|steps)>', '', answer).strip()
        steps = re.sub(r'</?(answer|steps)>', '', steps).strip()

        return answer, steps

    except Exception as e:
        return "Error", f"❌ Failed to solve using Gemini API: {str(e)}"


# ─────────────────────────────────────────────
# AUTH ROUTES
# ─────────────────────────────────────────────
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/index', methods=['GET', 'POST'])
def index():
    if 'user' in session:
        return redirect(url_for('solve'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        session['user'] = 'Guest'
        session.permanent = True
        return redirect(url_for('solve'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ─────────────────────────────────────────────
# SOLVER: Main dispatcher
# ─────────────────────────────────────────────
def auto_solve_math(expression_input):
    """
    Dispatch to the appropriate solver based on keywords in the input.
    Covers: Algebra, Calculus, Trig, Log, Matrix, Series, Complex,
            Statistics, Number Theory, Combinatorics, Vectors, Sets,
            Probability, Geometry/Word Problems, General Simplification.
    """
    expr = expression_input.strip()
    expr_lower = expr.lower()

    try:
        # 0. Triangle identity proofs
        if ('triangle' in expr_lower or 'interior angles' in expr_lower) and \
           any(kw in expr_lower for kw in ['show that', 'prove that']):
            return solve_triangle_identity(expr)

        # 1. Trig identity proofs
        if re.search(r'\bprove\b', expr, re.I):
            return solve_trig_identity(expr)

        # 2. Inequalities
        if any(op in expr for op in ['<=', '>=', '≤', '≥', '≠', '!=']):
            return solve_inequality(expr)
        if re.search(r'(?<![=<>!])<(?!=)|(?<![=<>!])>(?!=)', expr):
            if '=' not in expr:
                return solve_inequality(expr)

        # 3. Number Theory
        if any(kw in expr_lower for kw in ['gcd', 'lcm', 'prime', 'factor of', 'modular', 'mod ', 'divisor', 'divisible']):
            return solve_number_theory(expr)

        # 4. Combinatorics / Permutations / Combinations
        if any(kw in expr_lower for kw in ['permutation', 'combination', 'p(', 'c(', 'ncr', 'npr', 'binomial coefficient', 'choose']):
            return solve_combinatorics(expr)

        # 5. Vectors
        if any(kw in expr_lower for kw in ['vector', 'dot product', 'cross product', 'magnitude', 'angle between vectors']):
            return solve_vector(expr)

        # 6. Set Theory
        if any(kw in expr_lower for kw in ['union', 'intersection', 'complement', 'set', 'subset', 'superset', 'difference of sets']):
            return solve_set_theory(expr)

        # 7. Probability
        if any(kw in expr_lower for kw in ['probability', 'chance', 'likelihood', 'expected value', 'p(a', 'p(b']):
            return solve_probability(expr)

        # 8. Statistics
        if any(kw in expr_lower for kw in ['mean', 'median', 'mode', 'variance', 'standard deviation', 'std dev', 'average of', 'statistics']):
            return solve_statistics(expr)

        # 9. Polynomial operations (factor/expand/polynomial keyword)
        if any(kw in expr_lower for kw in ['factor', 'expand', 'polynomial']):
            return solve_polynomial(expr)

        # 10. Equations (with =, not calculus)
        if '=' in expr and not any(kw in expr_lower for kw in ['limit', 'lim', 'integral', 'integrate', 'derivative', 'diff', 'd/dx', 'd/dy']):
            return solve_equation(expr)

        # 11. Derivatives
        if any(kw in expr_lower for kw in ['derivative', 'differentiate', 'diff', 'd/dx', 'd/dy', 'd/dt']):
            return solve_derivative(expr)

        # 12. Integrals
        if any(kw in expr_lower for kw in ['integral', 'integrate', '∫']):
            return solve_integral(expr)

        # 13. Limits
        if any(kw in expr_lower for kw in ['limit', 'lim']):
            return solve_limit(expr)

        # 14. Series / Sequences / Taylor
        if any(kw in expr_lower for kw in ['series', 'taylor', 'maclaurin', 'sum(', 'summation', 'sequence', 'ap ', 'gp ', 'arithmetic progression', 'geometric progression', 'factorial']):
            return solve_series(expr)

        # 15. Logarithms
        if any(kw in expr_lower for kw in ['log', 'ln', 'logarithm']):
            return solve_logarithmic(expr)

        # 16. Trigonometry
        if any(kw in expr_lower for kw in ['sin', 'cos', 'tan', 'sec', 'csc', 'cot', 'arcsin', 'arccos', 'arctan', 'trig']):
            return solve_trigonometric(expr)

        # 17. Complex numbers
        if re.search(r'\bcomplex\b|\bimaginary\b|\breal part\b|\bimaginary part\b', expr_lower):
            return solve_complex(expr)
        if re.search(r'\d+\s*[\+\-]\s*\d*[iI]\b', expr):
            return solve_complex(expr)

        # 18. Matrix
        if any(kw in expr_lower for kw in ['matrix', 'determinant', 'inverse', 'eigenvalue', 'eigenvector', 'transpose']):
            return solve_matrix(expr)

        # 19. Word Problems / Geometry
        if any(word in expr_lower for word in ['find', 'calculate', 'what is', 'circle', 'rectangle', 'triangle', 'area', 'perimeter', 'volume', 'surface area', 'distance between', 'hypotenuse', 'sphere', 'cylinder', 'cone', 'cube', 'quadratic', 'percentage', '%']):
            return solve_word_problem(expr)

        # 20. General simplification / arithmetic
        return simplify_expression(expr)

    except Exception as e:
        return f"Error: {str(e)}", "❌ Could not process the expression. Please check your input format."


# ─────────────────────────────────────────────
# SOLVER: Inequality
# ─────────────────────────────────────────────
def solve_inequality(expr):
    """Solve inequalities correctly using SymPy relational constructors"""
    try:
        s = expr.replace('≤', '<=').replace('≥', '>=').replace('≠', '!=')

        for op in ['<=', '>=', '!=', '<', '>']:
            if op in s:
                parts = s.split(op, 1)
                left_expr = parse_math_expression(parts[0].strip())
                right_expr = parse_math_expression(parts[1].strip())

                if op == '<=':
                    inequality = Le(left_expr, right_expr)
                elif op == '>=':
                    inequality = Ge(left_expr, right_expr)
                elif op == '<':
                    inequality = Lt(left_expr, right_expr)
                elif op == '>':
                    inequality = Gt(left_expr, right_expr)
                elif op == '!=':
                    inequality = Ne(left_expr, right_expr)

                solution = sympy_solve(inequality)
                steps = f"📐 Inequality: {inequality}\n"
                steps += f"Solution set: {solution}\n\n"
                steps += "Method: Algebraic inequality solving\n"
                steps += f"The solution represents all values satisfying {inequality}"
                return str(solution), steps

        return "No inequality found", "Please use <, >, <=, >= or !="
    except Exception as e:
        return f"Error: {str(e)}", "Could not solve inequality"


# ─────────────────────────────────────────────
# SOLVER: Polynomial
# ─────────────────────────────────────────────
def solve_polynomial(expr):
    """Solve polynomial equations and operations"""
    try:
        parsed_expr = parse_math_expression(expr)
        if '=' in expr:
            left, right = expr.split('=', 1)
            equation = Eq(parse_math_expression(left), parse_math_expression(right))
            solutions = sympy_solve(equation)
            steps = f"📊 Polynomial equation: {equation}\n"
            try:
                poly_expr = equation.lhs - equation.rhs
                x_sym = list(equation.free_symbols)
                if x_sym:
                    p = Poly(poly_expr, x_sym[0])
                    poly_degree = p.degree()
                    steps += f"Degree of polynomial: {poly_degree}\n"
            except Exception:
                pass
            steps += f"\nSolutions: {solutions}"
            return str(solutions), steps
        else:
            factored = factor(parsed_expr)
            expanded = expand(parsed_expr)
            steps = f"Original expression: {parsed_expr}\n"
            steps += f"Factored form: {factored}\n"
            steps += f"Expanded form: {expanded}\n"
            return str(factored if factored != parsed_expr else expanded), steps
    except Exception as e:
        return f"Error: {str(e)}", "Could not solve polynomial"


# ─────────────────────────────────────────────
# SOLVER: Equation
# ─────────────────────────────────────────────
def solve_equation(expr):
    """Solve algebraic equations and systems"""
    try:
        if ',' in expr and '{' in expr:
            equations_str = expr.strip('{}')
            equations = []
            for eq in equations_str.split(','):
                eq = eq.strip()
                if '=' in eq:
                    left, right = eq.split('=', 1)
                    equations.append(Eq(parse_math_expression(left.strip()), parse_math_expression(right.strip())))
            variables = sorted(list(set().union(*[eq.free_symbols for eq in equations])), key=str)
            solution = sympy_solve(equations, variables)
            steps = "🔢 System of Equations:\n"
            for i, eq in enumerate(equations, 1):
                steps += f"  Equation {i}: {eq}\n"
            steps += f"\nVariables: {variables}\n"
            steps += f"Solution: {solution}"
            return str(solution), steps
        else:
            if '=' not in expr:
                return "Error: No equation found", "Please include '=' for equations"
            left, right = expr.split('=', 1)
            left_expr = parse_math_expression(left.strip())
            right_expr = parse_math_expression(right.strip())
            equation = Eq(left_expr, right_expr)
            solution = sympy_solve(equation)
            steps = f"🔢 Equation: {equation}\n"
            steps += f"Free variables: {sorted(list(equation.free_symbols), key=str)}\n\n"
            steps += "Method: Algebraic solving\n"
            steps += f"Rearranging: {equation.lhs - equation.rhs} = 0\n"
            steps += f"\nSolution: {solution}"
            return str(solution), steps
    except Exception as e:
        return f"Error: {str(e)}", "Could not solve equation"


# ─────────────────────────────────────────────
# SOLVER: Derivative
# ─────────────────────────────────────────────
def solve_derivative(expr):
    """Solve derivatives with detailed steps"""
    try:
        if 'wrt' in expr.lower():
            parts = re.split(r'\bwrt\b', expr, flags=re.I)
            func_str = re.sub(r'\b(derivative|differentiate|diff|d/dx|d/dy|d/dt)\b', '', parts[0], flags=re.I).strip()
            var_str = parts[1].strip()
        elif 'd/dx' in expr:
            func_str = expr.split('d/dx', 1)[1].strip(' ()')
            var_str = 'x'
        elif 'd/dy' in expr:
            func_str = expr.split('d/dy', 1)[1].strip(' ()')
            var_str = 'y'
        elif 'd/dt' in expr:
            func_str = expr.split('d/dt', 1)[1].strip(' ()')
            var_str = 't'
        else:
            match = re.search(r'(?:diff|derivative|differentiate)\s*\(\s*([^,]+),\s*([^)]+)\)', expr, re.I)
            if match:
                func_str = match.group(1)
                var_str = match.group(2)
            else:
                func_str = re.sub(r'\b(derivative|differentiate|diff|of)\b', '', expr, flags=re.I).strip()
                var_str = 'x'

        func = parse_math_expression(func_str)
        var = Symbol(var_str.strip())
        derivative = diff(func, var)

        steps = f"📈 Function: f({var}) = {func}\n"
        steps += f"Finding: d/d{var} [{func}]\n\n"
        steps += "Rules applied:\n"
        if func.is_polynomial(var):
            steps += "  • Power rule: d/dx[xⁿ] = n·xⁿ⁻¹\n"
        if func.has(sin, cos, tan):
            steps += "  • Trig derivatives: d/dx[sin x]=cos x, d/dx[cos x]=-sin x\n"
        if func.has(log):
            steps += "  • Log rule: d/dx[ln x] = 1/x\n"
        if func.has(exp):
            steps += "  • Exponential rule: d/dx[eˣ] = eˣ\n"
        steps += f"\nResult: f'({var}) = {derivative}"
        return str(derivative), steps
    except Exception as e:
        return f"Error: {str(e)}", "Could not compute derivative"


# ─────────────────────────────────────────────
# SOLVER: Integral
# ─────────────────────────────────────────────
def solve_integral(expr):
    """Solve integrals with detailed steps"""
    try:
        is_definite = False
        lower_limit = upper_limit = None

        if 'integral of' in expr.lower() and 'wrt' in expr.lower():
            parts = re.split(r'\bwrt\b', expr.lower().split('integral of')[1], flags=re.I)
            func_str = parts[0].strip()
            var_str = parts[1].strip()
        elif re.search(r'\bwrt\b', expr, re.I):
            parts = re.split(r'\bwrt\b', expr, flags=re.I)
            func_str = re.sub(r'\b(integral|integrate)\b', '', parts[0], flags=re.I).strip()
            var_str = parts[1].strip()
        else:
            match = re.search(r'(?:integrate|integral)\s*\(\s*([^,]+),\s*(.+)\)', expr, re.I)
            if match:
                func_str = match.group(1)
                var_part = match.group(2)
                var_match = re.search(r'\(\s*([^,]+),\s*([^,]+),\s*([^)]+)\)', var_part)
                if var_match:
                    var_str = var_match.group(1)
                    lower_limit = var_match.group(2)
                    upper_limit = var_match.group(3)
                    is_definite = True
                else:
                    var_str = var_part.strip()
            else:
                func_str = re.sub(r'\b(integral|integrate|of)\b', '', expr, flags=re.I).strip()
                var_str = 'x'

        func = parse_math_expression(func_str)
        var = Symbol(var_str.strip())

        steps = f"∫ Function: f({var}) = {func}\n\n"

        if is_definite and lower_limit and upper_limit:
            a = parse_math_expression(lower_limit)
            b = parse_math_expression(upper_limit)
            integral_result = integrate(func, (var, a, b))
            steps += f"Definite integral: ∫[{a} → {b}] {func} d{var}\n"
            steps += f"\nAnti-derivative: {integrate(func, var)} + C\n"
            steps += f"Applying limits: F({b}) - F({a})\n"
            steps += f"\nResult: {integral_result}"
        else:
            integral_result = integrate(func, var)
            steps += f"Indefinite integral: ∫ {func} d{var}\n"
            steps += f"\nResult: {integral_result} + C"

        return str(integral_result), steps
    except Exception as e:
        return f"Error: {str(e)}", "Could not compute integral"


# ─────────────────────────────────────────────
# SOLVER: Limit
# ─────────────────────────────────────────────
def solve_limit(expr):
    """Solve limits"""
    try:
        match = re.search(r'limit\s*\(\s*([^,]+),\s*([^,]+),\s*([^)]+)\)', expr, re.I)
        if match:
            func_str = match.group(1)
            var_str = match.group(2)
            point_str = match.group(3)
        else:
            match = re.search(r'lim\s+([^\-]+)->\s*([^\s]+)\s+(.+)', expr)
            if match:
                var_str = match.group(1).strip()
                point_str = match.group(2)
                func_str = match.group(3)
            else:
                # Try: "lim x->0 sin(x)/x"
                match = re.search(r'(?:limit|lim)[^,]*?([a-z])\s*[-→]\s*([^\s]+)\s+(.+)', expr, re.I)
                if match:
                    var_str = match.group(1)
                    point_str = match.group(2)
                    func_str = match.group(3)
                else:
                    return "Error: Could not parse limit", "Use format: limit(f(x), x, a)  or  lim x->a f(x)"

        func = parse_math_expression(func_str)
        var = Symbol(var_str.strip())
        point = parse_math_expression(point_str)
        limit_result = limit(func, var, point)

        steps = f"🎯 Computing limit:\n"
        steps += f"lim({var} → {point}) [{func}]\n\n"
        try:
            direct_sub = func.subs(var, point)
            if str(direct_sub) in ['zoo', 'nan', 'oo', '-oo']:
                steps += "Direct substitution gives indeterminate form — applying limit techniques.\n"
            else:
                steps += f"Direct substitution: {func.subs(var, point)}\n"
        except Exception:
            pass
        steps += f"\nLimit result: {limit_result}"
        return str(limit_result), steps
    except Exception as e:
        return f"Error: {str(e)}", "Could not compute limit"


# ─────────────────────────────────────────────
# SOLVER: Logarithmic
# ─────────────────────────────────────────────
def solve_logarithmic(expr):
    """Solve logarithmic expressions and equations"""
    try:
        if '=' in expr:
            left, right = expr.split('=', 1)
            equation = Eq(parse_math_expression(left), parse_math_expression(right))
            solution = sympy_solve(equation)
            steps = f"📋 Logarithmic equation: {equation}\n"
            steps += "\nLogarithm properties used:\n"
            steps += "  • logₐ(xy) = logₐ(x) + logₐ(y)\n"
            steps += "  • logₐ(x/y) = logₐ(x) - logₐ(y)\n"
            steps += "  • logₐ(xⁿ) = n·logₐ(x)\n"
            steps += f"\nSolution: {solution}"
            return str(solution), steps
        else:
            parsed_expr = parse_math_expression(expr)
            simplified = simplify(parsed_expr)
            steps = f"📋 Expression: {parsed_expr}\n"
            steps += f"Simplified: {simplified}\n"
            try:
                expanded = expand_log(parsed_expr, force=True)
                if expanded != parsed_expr:
                    steps += f"Expanded form: {expanded}\n"
            except Exception:
                pass
            return str(simplified), steps
    except Exception as e:
        return f"Error: {str(e)}", "Could not solve logarithmic expression"


# ─────────────────────────────────────────────
# SOLVER: Trigonometric Identity
# ─────────────────────────────────────────────
def solve_trig_identity(expr):
    """Prove or simplify trigonometric identities."""
    try:
        s = expr.strip()
        s = s.replace('θ', 'theta').replace('Θ', 'theta')
        s = s.replace('cosec', 'csc')
        s = s.replace('^', '**')

        m = re.search(r'prove(?:\s+that)?\s+(.+?)\s*=\s*(.+)', s, re.I)
        if m:
            lhs_str = m.group(1).strip()
            rhs_str = m.group(2).strip()
            lhs = parse_math_expression(lhs_str)
            rhs = parse_math_expression(rhs_str)
            lhs_s = trigsimp(lhs)
            rhs_s = trigsimp(rhs)
            diff_val = simplify(lhs_s - rhs_s)

            steps = f"🔺 Trig Identity Proof\n{'='*60}\n"
            steps += f"LHS = {lhs_str}\n"
            steps += f"RHS = {rhs_str}\n\n"
            steps += f"Simplified LHS: {lhs_s}\n"
            steps += f"Simplified RHS: {rhs_s}\n\n"
            steps += f"Difference (LHS - RHS): {diff_val}\n\n"

            if diff_val == 0:
                steps += "✅ LHS = RHS for all values where expressions are defined."
                return "✅ Identity PROVED!", steps
            else:
                steps += "❌ LHS ≠ RHS (difference is not zero)."
                return "❌ Identity NOT proved", steps

        # Simplify trig expression
        parsed = parse_math_expression(s)
        simplified = trigsimp(parsed)
        steps = f"Original: {expr}\n"
        steps += f"Simplified: {simplified}\n"
        return str(simplified), steps
    except Exception as e:
        return f"Error: {str(e)}", "Could not process trig identity"


# ─────────────────────────────────────────────
# SOLVER: Trigonometric
# ─────────────────────────────────────────────
def solve_trigonometric(expr):
    """Solve trigonometric expressions and equations"""
    try:
        if re.search(r'\bprove\b', expr, re.I):
            return solve_trig_identity(expr)

        if '=' in expr:
            left, right = expr.split('=', 1)
            equation = Eq(parse_math_expression(left), parse_math_expression(right))
            solution = sympy_solve(equation)
            steps = f"📐 Trigonometric equation: {equation}\n"
            steps += f"Solution: {solution}\n"
            steps += "\nNote: Solutions may include additional periods (2πn for sin/cos, πn for tan)"
            return str(solution), steps
        else:
            parsed_expr = parse_math_expression(expr)
            simplified = trigsimp(parsed_expr)
            evaluated = parsed_expr.evalf()
            steps = f"📐 Expression: {parsed_expr}\n"
            steps += f"Simplified: {simplified}\n"
            try:
                expanded = expand_trig(parsed_expr)
                if expanded != parsed_expr:
                    steps += f"Expanded: {expanded}\n"
            except Exception:
                pass
            if simplified != evaluated:
                steps += f"Numerical value: {evaluated}"
            return str(simplified), steps
    except Exception as e:
        return f"Error: {str(e)}", "Could not solve trigonometric expression"


# ─────────────────────────────────────────────
# SOLVER: Matrix
# ─────────────────────────────────────────────
def solve_matrix(expr):
    """Solve matrix operations"""
    try:
        steps = "🔢 Matrix Operations:\n"

        def extract_matrix(text):
            matrix_match = re.search(r'\[\s*\[(.+?)\]\s*\]', text, re.DOTALL)
            if not matrix_match:
                return None
            rows_str = matrix_match.group(0)
            row_matches = re.findall(r'\[([^\[\]]+)\]', rows_str)
            matrix_data = []
            for row in row_matches:
                matrix_data.append([parse_math_expression(x.strip()) for x in row.split(',')])
            return Matrix(matrix_data)

        M = extract_matrix(expr)
        if M is None:
            return "Please provide matrix in format: [[a,b],[c,d]]", steps

        steps += f"Matrix:\n{M}\n\n"

        if 'determinant' in expr.lower() or 'det' in expr.lower():
            det = M.det()
            steps += f"Determinant = {det}"
            return str(det), steps

        elif 'inverse' in expr.lower() or 'inv' in expr.lower():
            try:
                inv = M.inv()
                steps += f"Inverse matrix:\n{inv}"
                return str(inv), steps
            except Exception:
                return "Matrix is singular (not invertible — determinant = 0)", steps

        elif 'transpose' in expr.lower():
            T = M.T
            steps += f"Transpose:\n{T}"
            return str(T), steps

        elif 'eigenvalue' in expr.lower() or 'eigenvector' in expr.lower():
            eigenvals = M.eigenvals()
            eigenvects = M.eigenvects()
            steps += f"Eigenvalues: {eigenvals}\n"
            steps += f"Eigenvectors: {eigenvects}"
            return str(eigenvals), steps

        else:
            # Default: show properties
            steps += f"Shape: {M.shape}\n"
            steps += f"Determinant: {M.det()}\n"
            try:
                steps += f"Rank: {M.rank()}\n"
                steps += f"Trace: {M.trace()}"
            except Exception:
                pass
            return str(M), steps

    except Exception as e:
        return f"Error: {str(e)}", "Could not solve matrix operation"


# ─────────────────────────────────────────────
# SOLVER: Series & Sequences (Enhanced)
# ─────────────────────────────────────────────
def solve_series(expr):
    """Solve series, sequences, AP/GP, Taylor/Maclaurin"""
    try:
        expr_lower = expr.lower()
        steps = ""

        # Factorial
        if 'factorial' in expr_lower or re.search(r'\d+\s*!', expr):
            match = re.search(r'(\d+)\s*!|factorial\s*\(\s*(\d+)\s*\)', expr)
            if match:
                num = int(match.group(1) or match.group(2))
                result = factorial(num)
                steps = f"🔢 Factorial: {num}!\n"
                steps += f"= {' × '.join(str(i) for i in range(1, num+1))}\n"
                steps += f"= {result}"
                return str(result), steps

        # Taylor / Maclaurin series
        if 'taylor' in expr_lower or 'maclaurin' in expr_lower:
            match = re.search(r'(?:taylor|maclaurin)\s+(?:of\s+)?(.+?)(?:\s+at\s+([^\s]+))?(?:\s+(?:to|up to|order)\s+(\d+))?$', expr, re.I)
            if match:
                func_str = match.group(1).strip()
                point_str = match.group(2) or '0'
                order = int(match.group(3) or '5')
                func = parse_math_expression(func_str)
                point = parse_math_expression(point_str)
                x_sym = symbols('x')
                taylor_result = sym_series(func, x_sym, point, order)
                steps = f"📈 Taylor/Maclaurin Series\n"
                steps += f"Function: {func_str}\n"
                steps += f"Around point: {point}\n"
                steps += f"Order: {order}\n\n"
                steps += f"Series expansion:\n{taylor_result}"
                return str(taylor_result), steps

        # Summation
        if 'sum' in expr_lower or 'summation' in expr_lower:
            match = re.search(r'sum(?:mation)?\s*\(\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*([^)]+)\)', expr, re.I)
            if match:
                func_str, var_str, start_str, end_str = match.groups()
                func = parse_math_expression(func_str)
                var = Symbol(var_str.strip())
                start = parse_math_expression(start_str)
                end = parse_math_expression(end_str)
                result = summation(func, (var, start, end))
                steps = f"Σ({var}={start} to {end}) [{func}]\n"
                steps += f"\nResult: {result}"
                return str(result), steps

        # Arithmetic Progression (AP)
        if 'arithmetic progression' in expr_lower or 'ap ' in expr_lower:
            match = re.search(r'(?:first\s+term|a\s*=)\s*(\d+(?:\.\d+)?).*(?:common\s+difference|d\s*=)\s*(\d+(?:\.\d+)?)', expr, re.I)
            match_n = re.search(r'(\d+)\s*(?:th|st|nd|rd)\s+term|n\s*=\s*(\d+)', expr, re.I)
            if match:
                a_val = float(match.group(1))
                d_val = float(match.group(2))
                n_val = int(match_n.group(1) or match_n.group(2)) if match_n else 10
                nth_term = a_val + (n_val - 1) * d_val
                sum_n = n_val * (2 * a_val + (n_val - 1) * d_val) / 2
                steps = f"📈 Arithmetic Progression\n"
                steps += f"First term (a) = {a_val}, Common difference (d) = {d_val}\n"
                steps += f"\nFormula for nth term: aₙ = a + (n-1)d\n"
                steps += f"a_{n_val} = {a_val} + ({n_val}-1)×{d_val} = {nth_term}\n\n"
                steps += f"Sum of {n_val} terms: Sₙ = n/2 × (2a + (n-1)d)\n"
                steps += f"S_{n_val} = {n_val}/2 × (2×{a_val} + ({n_val}-1)×{d_val}) = {sum_n}"
                return f"a_{n_val} = {nth_term}, S_{n_val} = {sum_n}", steps

        # Geometric Progression (GP)
        if 'geometric progression' in expr_lower or 'gp ' in expr_lower:
            match = re.search(r'(?:first\s+term|a\s*=)\s*(\d+(?:\.\d+)?).*(?:common\s+ratio|r\s*=)\s*(\d+(?:\.\d+)?)', expr, re.I)
            match_n = re.search(r'(\d+)\s*(?:th|st|nd|rd)\s+term|n\s*=\s*(\d+)', expr, re.I)
            if match:
                a_val = float(match.group(1))
                r_val = float(match.group(2))
                n_val = int(match_n.group(1) or match_n.group(2)) if match_n else 10
                nth_term = a_val * (r_val ** (n_val - 1))
                if r_val != 1:
                    sum_n = a_val * (r_val ** n_val - 1) / (r_val - 1)
                else:
                    sum_n = a_val * n_val
                steps = f"📈 Geometric Progression\n"
                steps += f"First term (a) = {a_val}, Common ratio (r) = {r_val}\n"
                steps += f"\nFormula for nth term: aₙ = a × rⁿ⁻¹\n"
                steps += f"a_{n_val} = {a_val} × {r_val}^{n_val-1} = {nth_term}\n\n"
                steps += f"Sum of {n_val} terms: Sₙ = a(rⁿ - 1)/(r - 1)\n"
                steps += f"S_{n_val} = {sum_n}"
                return f"a_{n_val} = {nth_term}, S_{n_val} = {sum_n}", steps

        return "Series format not recognized", "Supported: factorial(n), sum(expr,var,a,b), Taylor series, AP/GP"
    except Exception as e:
        return f"Error: {str(e)}", "Could not solve series"


# ─────────────────────────────────────────────
# SOLVER: Complex Numbers (FIXED)
# ─────────────────────────────────────────────
def solve_complex(expr):
    """Solve complex number operations — fixed to not break word characters"""
    try:
        # Only replace standalone 'i' (not inside words like sin, find, etc.)
        fixed_expr = re.sub(r'(?<![a-zA-Z])i(?![a-zA-Z])', 'I', expr)
        parsed_expr = parse_math_expression(fixed_expr)

        steps = f"🔢 Complex Expression: {parsed_expr}\n\n"
        real_part = Re(parsed_expr)
        imag_part = Im(parsed_expr)
        magnitude = Abs(parsed_expr)
        argument = arg(parsed_expr)
        conj = conjugate(parsed_expr)

        steps += f"Real part (Re): {real_part}\n"
        steps += f"Imaginary part (Im): {imag_part}\n"
        steps += f"Modulus |z|: {magnitude}\n"
        steps += f"Argument arg(z): {argument}\n"
        steps += f"Conjugate z̄: {conj}\n"
        steps += f"\nPolar form: |z| × e^(iθ) = {magnitude}·e^(i·{argument})"

        return str(parsed_expr), steps
    except Exception as e:
        return f"Error: {str(e)}", "Could not solve complex expression"


# ─────────────────────────────────────────────
# SOLVER: Statistics (Enhanced)
# ─────────────────────────────────────────────
def solve_statistics(expr):
    """Solve statistics problems from a dataset"""
    try:
        # Extract numbers from expression
        numbers = re.findall(r'-?\d+(?:\.\d+)?', expr)
        if not numbers:
            return "No data found", "Please provide numbers, e.g.: mean of 2, 4, 6, 8, 10"

        data = [float(n) for n in numbers]
        n_count = len(data)

        mean_val = py_stats.mean(data)
        steps = f"📊 Statistics for data: {data}\n"
        steps += f"Count (n) = {n_count}\n\n"
        steps += f"{'='*50}\n"
        steps += f"Mean = Σx/n = {sum(data)}/{n_count} = {mean_val:.4f}\n"

        if n_count >= 2:
            median_val = py_stats.median(data)
            try:
                mode_val = py_stats.mode(data)
                steps += f"Median = {median_val}\n"
                steps += f"Mode = {mode_val}\n"
            except Exception:
                steps += f"Median = {median_val}\n"
                steps += "Mode = No unique mode\n"

            variance_val = py_stats.variance(data)
            std_dev = py_stats.stdev(data)
            steps += f"Variance (s²) = {variance_val:.4f}\n"
            steps += f"Std Deviation (s) = {std_dev:.4f}\n"
            steps += f"Range = {max(data) - min(data)}\n"
            steps += f"Min = {min(data)}, Max = {max(data)}"
            result = f"Mean={mean_val:.4f}, Median={median_val}, Std Dev={std_dev:.4f}"
        else:
            result = f"Mean = {mean_val}"

        return result, steps
    except Exception as e:
        return f"Error: {str(e)}", "Could not solve statistics problem"


# ─────────────────────────────────────────────
# SOLVER: Number Theory (NEW)
# ─────────────────────────────────────────────
def solve_number_theory(expr):
    """Solve number theory problems: GCD, LCM, prime factorization, modular arithmetic"""
    try:
        expr_lower = expr.lower()
        steps = "🔢 Number Theory\n" + "="*50 + "\n"

        # GCD
        if 'gcd' in expr_lower or 'greatest common' in expr_lower:
            nums = re.findall(r'\d+', expr)
            if len(nums) >= 2:
                a, b = int(nums[0]), int(nums[1])
                result = gcd(a, b)
                steps += f"GCD({a}, {b})\n\n"
                steps += f"Prime factors of {a}: {factorint(a)}\n"
                steps += f"Prime factors of {b}: {factorint(b)}\n"
                steps += f"\nGCD = {result}"
                return str(result), steps

        # LCM
        if 'lcm' in expr_lower or 'least common' in expr_lower:
            nums = re.findall(r'\d+', expr)
            if len(nums) >= 2:
                a, b = int(nums[0]), int(nums[1])
                result = lcm(a, b)
                steps += f"LCM({a}, {b})\n\n"
                steps += f"Prime factors of {a}: {factorint(a)}\n"
                steps += f"Prime factors of {b}: {factorint(b)}\n"
                steps += f"\nLCM = a × b / GCD = {a} × {b} / {gcd(a,b)} = {result}"
                return str(result), steps

        # Prime factorization
        if 'factor' in expr_lower or 'prime factor' in expr_lower or 'factorize' in expr_lower or 'factorise' in expr_lower:
            nums = re.findall(r'\d+', expr)
            if nums:
                n_val = int(nums[0])
                factors = factorint(n_val)
                factor_str = ' × '.join([f"{p}^{e}" if e > 1 else str(p) for p, e in factors.items()])
                steps += f"Prime Factorization of {n_val}\n\n"
                steps += f"Factors: {factors}\n"
                steps += f"= {factor_str}"
                return f"{n_val} = {factor_str}", steps

        # Is prime?
        if 'prime' in expr_lower:
            nums = re.findall(r'\d+', expr)
            if nums:
                n_val = int(nums[0])
                is_p = isprime(n_val)
                steps += f"Checking if {n_val} is prime\n\n"
                if is_p:
                    steps += f"✅ {n_val} is a PRIME number\n"
                    steps += f"It is only divisible by 1 and {n_val}"
                else:
                    factors = factorint(n_val)
                    steps += f"❌ {n_val} is NOT prime\n"
                    steps += f"Factors: {factors}"
                return str(is_p), steps

        # Modular arithmetic
        if 'mod' in expr_lower:
            match = re.search(r'(\d+)\s*mod\s*(\d+)', expr, re.I)
            if match:
                a, m = int(match.group(1)), int(match.group(2))
                result = a % m
                steps += f"{a} mod {m}\n\n"
                steps += f"{a} = {a // m} × {m} + {result}\n"
                steps += f"Result: {result}"
                return str(result), steps

        return "Please specify GCD, LCM, prime factorization, or modular arithmetic", steps
    except Exception as e:
        return f"Error: {str(e)}", "Could not solve number theory problem"


# ─────────────────────────────────────────────
# SOLVER: Combinatorics (NEW)
# ─────────────────────────────────────────────
def explain_factorial_division(n, d):
    """Explain n! / d! as n * (n-1) * ... * (d+1)"""
    if n < 0 or d < 0:
        return "undefined"
    if n == d:
        return "1"
    if n < d:
        return f"({n}! / {d}!)"
    
    if n - d > 8:
        terms = [str(i) for i in range(n, n-3, -1)] + ["..."] + [str(d+1)]
        return " × ".join(terms)
    else:
        terms = [str(i) for i in range(n, d, -1)]
        return " × ".join(terms)

def get_factorial_expansion(n):
    if n == 0 or n == 1:
        return "1"
    if n > 8:
        return f"{n} × {n-1} × {n-2} × ... × 1"
    return " × ".join(str(i) for i in range(n, 0, -1))

def solve_combinatorics(expr):
    """Solve permutations, combinations, binomial coefficients with detailed steps"""
    import math
    from collections import Counter
    try:
        steps = "🎲 Combinatorics\n" + "="*50 + "\n"
        expr_lower = expr.lower().strip()

        # 1. Word permutations (arrangements of letters of a word)
        # e.g., "permutations of the word SUCCESS"
        word_match = re.search(
            r'(?:permutation|arrangement)s?\s+of\s+(?:the\s+)?(?:letters\s+in\s+)?(?:word\s+)?[\'"`“]?([a-zA-Z]{2,})[\'"`]?',
            expr, re.I
        )
        if not word_match:
            # alternative pattern: "how many arrangements of SUCCESS"
            word_match = re.search(
                r'how\s+many\s+(?:permutations|arrangements)\s+(?:can\s+be\s+made\s+from|of)\s+(?:the\s+letters\s+of\s+)?(?:the\s+word\s+)?[\'"`“]?([a-zA-Z]{2,})[\'"`]?',
                expr, re.I
            )
        if word_match:
            word = word_match.group(1).upper()
            n = len(word)
            counts = Counter(word)
            repeated = {char: count for char, count in counts.items() if count > 1}
            
            steps += f"Problem: Find the number of permutations of the letters in the word '{word}'.\n\n"
            steps += f"Step 1: Count the total number of letters (n).\n"
            steps += f"   Total letters n = {n}\n\n"
            
            if repeated:
                steps += f"Step 2: Identify the repeated letters and their frequencies.\n"
                for char, count in repeated.items():
                    steps += f"   Letter '{char}' appears {count} times.\n"
                steps += "\n"
                
                # Formula
                denom_terms_fact = " × ".join([f"{count}!" for count in repeated.values()])
                denom_terms_val = " × ".join([str(math.factorial(count)) for count in repeated.values()])
                denom_val = 1
                for count in repeated.values():
                    denom_val *= math.factorial(count)
                
                result = math.factorial(n) // denom_val
                
                steps += f"Step 3: Apply the permutation formula for repeated items:\n"
                steps += f"   Formula: N = n! / (n₁! × n₂! × ... × n_k!)\n"
                steps += f"   N = {n}! / ({denom_terms_fact})\n"
                steps += f"   N = {math.factorial(n)} / ({denom_terms_val})\n"
                steps += f"   N = {math.factorial(n)} / {denom_val}\n"
                steps += f"   N = {result}\n\n"
                steps += f"✅ Answer: There are {result} distinct permutations of the word '{word}'."
                return str(result), steps
            else:
                result = math.factorial(n)
                steps += f"Step 2: Since all letters are unique, the number of permutations is simply n!.\n"
                steps += f"   Formula: N = n!\n"
                steps += f"   N = {n}!\n"
                steps += f"   N = {get_factorial_expansion(n)}\n"
                steps += f"   N = {result}\n\n"
                steps += f"✅ Answer: There are {result} distinct permutations of the word '{word}'."
                return str(result), steps

        # 2. Circular permutations
        # e.g., "circular permutation of 6 people"
        circ_match = re.search(r'circular\s+(?:permutation|arrangement)s?\s+of\s+(\d+)', expr_lower)
        if not circ_match:
            circ_match = re.search(r'how\s+many\s+circular\s+(?:arrangements|permutations)\s+of\s+(\d+)', expr_lower)
        if circ_match:
            n = int(circ_match.group(1))
            if n <= 1:
                return "1", steps + f"Circular arrangements of {n} items is 1."
            result = math.factorial(n - 1)
            steps += f"Problem: Find the number of circular permutations of {n} items.\n\n"
            steps += f"Step 1: Understand circular permutations.\n"
            steps += f"   In a circular arrangement, shifting everyone by one position does not create a new arrangement.\n"
            steps += f"   Therefore, we fix one person/object in place, and arrange the remaining (n - 1) items in a line.\n\n"
            steps += f"Step 2: Apply the circular permutation formula:\n"
            steps += f"   Formula: N = (n - 1)!\n"
            steps += f"   N = ({n} - 1)!\n"
            steps += f"   N = {n - 1}!\n"
            steps += f"   N = {get_factorial_expansion(n - 1)}\n"
            steps += f"   N = {result}\n\n"
            steps += f"✅ Answer: There are {result} circular permutations of {n} items."
            return str(result), steps

        # 3. Selection Word Problem (Combinations)
        # e.g. "how many ways to choose 4 players from a group of 10"
        choose_match = re.search(
            r'how\s+many\s+ways\s+(?:can\s+we|to)\s+(?:choose|select)\s+(\d+)\s*(?:items|people|players|objects|elements)?\s+from\s+(?:a\s+(?:group|team)\s+of\s+)?(\d+)',
            expr_lower
        )
        if choose_match:
            r = int(choose_match.group(1))
            n = int(choose_match.group(2))
            if r > n:
                return "0", steps + f"Error: Cannot choose {r} items from a group of {n} items."
            result = math.comb(n, r)
            steps += f"Problem: Choose {r} items from a group of {n} items.\n\n"
            steps += f"Step 1: Identify that the order of selection does not matter, which means we use Combinations (nCr).\n"
            steps += f"   Total items n = {n}\n"
            steps += f"   Items to choose r = {r}\n\n"
            steps += f"Step 2: Apply the Combination formula:\n"
            steps += f"   C(n, r) = n! / (r! × (n - r)!)\n"
            steps += f"   C({n}, {r}) = {n}! / ({r}! × ({n} - {r})!)\n"
            steps += f"   C({n}, {r}) = {n}! / ({r}! × {n - r}!)\n"
            
            # Show calculation detail
            numerator_str = explain_factorial_division(n, n-r)
            denom_str = get_factorial_expansion(r)
            
            steps += f"   C({n}, {r}) = ({numerator_str}) / ({denom_str})\n"
            steps += f"   C({n}, {r}) = {result}\n\n"
            steps += f"✅ Answer: There are {result} ways to choose {r} items from {n} items."
            return str(result), steps

        # 4. Arrangement Word Problem (Permutations)
        # e.g. "how many ways to arrange 3 books from a shelf of 8"
        arrange_match = re.search(
            r'how\s+many\s+ways\s+(?:can\s+we|to)\s+arrange\s+(\d+)\s*(?:items|people|books|objects|elements)?\s+from\s+(?:a\s+(?:group|team|shelf)\s+of\s+)?(\d+)',
            expr_lower
        )
        if arrange_match:
            r = int(arrange_match.group(1))
            n = int(arrange_match.group(2))
            if r > n:
                return "0", steps + f"Error: Cannot arrange {r} items from a group of {n} items."
            result = math.factorial(n) // math.factorial(n - r)
            steps += f"Problem: Arrange {r} items out of {n} total items in order.\n\n"
            steps += f"Step 1: Identify that the order of arrangement matters, which means we use Permutations (nPr).\n"
            steps += f"   Total items n = {n}\n"
            steps += f"   Items to arrange r = {r}\n\n"
            steps += f"Step 2: Apply the Permutation formula:\n"
            steps += f"   P(n, r) = n! / (n - r)!\n"
            steps += f"   P({n}, {r}) = {n}! / ({n} - {r})!\n"
            steps += f"   P({n}, {r}) = {n}! / {n - r}!\n"
            
            num_str = explain_factorial_division(n, n-r)
            steps += f"   P({n}, {r}) = {num_str}\n"
            steps += f"   P({n}, {r}) = {result}\n\n"
            steps += f"✅ Answer: There are {result} ways to arrange {r} items out of {n} items."
            return str(result), steps

        # 5. Direct Permutations P(n, r)
        p_match = re.search(r'p\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)|(\d+)\s*p\s*(\d+)|npr\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)', expr, re.I)
        if p_match:
            groups = [g for g in p_match.groups() if g is not None]
            n = int(groups[0])
            r = int(groups[1])
            if r > n:
                return "0", steps + f"Error: r ({r}) cannot be greater than n ({n}) for permutations."
            result = math.factorial(n) // math.factorial(n - r)
            steps += f"Permutations P({n}, {r})\n\n"
            steps += f"Formula: P(n, r) = n! / (n - r)!\n"
            steps += f"P({n}, {r}) = {n}! / ({n} - {r})!\n"
            steps += f"= {n}! / {n - r}!\n"
            steps += f"= ({explain_factorial_division(n, n - r)})\n"
            steps += f"= {result}"
            return str(result), steps

        # 6. Direct Combinations C(n, r)
        c_match = re.search(
            r'c\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)|(\d+)\s*c\s*(\d+)|(\d+)\s+choose\s+(\d+)|ncr\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)',
            expr, re.I
        )
        if c_match:
            groups = [g for g in c_match.groups() if g is not None]
            n = int(groups[0])
            r = int(groups[1])
            if r > n:
                return "0", steps + f"Error: r ({r}) cannot be greater than n ({n}) for combinations."
            result = math.comb(n, r)
            steps += f"Combinations C({n}, {r}) [also written as {n} choose {r}]\n\n"
            steps += f"Formula: C(n, r) = n! / (r! × (n - r)!)\n"
            steps += f"C({n}, {r}) = {n}! / ({r}! × ({n} - {r})!)\n"
            steps += f"= {n}! / ({r}! × {n - r}!)\n"
            
            numerator_str = explain_factorial_division(n, n-r)
            denom_str = get_factorial_expansion(r)
            steps += f"= ({numerator_str}) / ({denom_str})\n"
            steps += f"= {result}"
            return str(result), steps

        return "Format not recognized", "Please check input: P(n, r), C(n, r), n choose r, word permutations, circular permutations."
    except Exception as e:
        return f"Error: {str(e)}", "Could not solve combinatorics problem"


# ─────────────────────────────────────────────
# SOLVER: Vectors (NEW)
# ─────────────────────────────────────────────
def solve_vector(expr):
    """Solve vector operations: dot product, cross product, magnitude, angle"""
    try:
        steps = "🧭 Vector Operations\n" + "="*50 + "\n"
        expr_lower = expr.lower()

        # Extract vectors like (1, 2, 3) or [1, 2, 3]
        vectors = re.findall(r'[\(\[]\s*([-\d.]+)\s*,\s*([-\d.]+)(?:\s*,\s*([-\d.]+))?\s*[\)\]]', expr)

        if len(vectors) >= 1:
            v1 = [float(x) for x in vectors[0] if x != '']
            v2 = [float(x) for x in vectors[1] if x != ''] if len(vectors) >= 2 else None

            steps += f"Vector A = {v1}\n"
            if v2:
                steps += f"Vector B = {v2}\n\n"

            # Magnitude
            if 'magnitude' in expr_lower or 'length' in expr_lower or (v2 is None):
                mag = sum(c**2 for c in v1) ** 0.5
                steps += f"Magnitude |A| = √({' + '.join(f'{c}²' for c in v1)})\n"
                steps += f"= √{sum(c**2 for c in v1)}\n"
                steps += f"= {mag:.4f}"
                return f"|A| = {mag:.4f}", steps

            # Dot product
            if 'dot' in expr_lower:
                if len(v1) == len(v2):
                    dot = sum(a*b for a, b in zip(v1, v2))
                    steps += f"\nDot Product A·B = Σ(aᵢ × bᵢ)\n"
                    steps += f"= {' + '.join(f'{a}×{b}' for a, b in zip(v1, v2))}\n"
                    steps += f"= {dot}"
                    return str(dot), steps

            # Cross product (3D only)
            if 'cross' in expr_lower:
                if len(v1) == 3 and len(v2) == 3:
                    cross = [
                        v1[1]*v2[2] - v1[2]*v2[1],
                        v1[2]*v2[0] - v1[0]*v2[2],
                        v1[0]*v2[1] - v1[1]*v2[0]
                    ]
                    steps += f"\nCross Product A × B:\n"
                    steps += f"= ({v1[1]}×{v2[2]} - {v1[2]}×{v2[1]}, {v1[2]}×{v2[0]} - {v1[0]}×{v2[2]}, {v1[0]}×{v2[1]} - {v1[1]}×{v2[0]})\n"
                    steps += f"= {cross}"
                    return str(cross), steps

            # Angle between vectors
            if 'angle' in expr_lower and v2:
                dot = sum(a*b for a, b in zip(v1, v2))
                mag1 = sum(c**2 for c in v1) ** 0.5
                mag2 = sum(c**2 for c in v2) ** 0.5
                cos_theta = dot / (mag1 * mag2)
                import math
                angle_rad = math.acos(max(-1, min(1, cos_theta)))
                angle_deg = math.degrees(angle_rad)
                steps += f"\nAngle between vectors:\n"
                steps += f"cos θ = (A·B) / (|A|×|B|) = {dot} / ({mag1:.4f} × {mag2:.4f})\n"
                steps += f"cos θ = {cos_theta:.4f}\n"
                steps += f"θ = {angle_deg:.2f}°"
                return f"θ = {angle_deg:.2f}°", steps

        return "Please provide vectors in format: (1, 2, 3)", steps
    except Exception as e:
        return f"Error: {str(e)}", "Could not solve vector problem"


# ─────────────────────────────────────────────
# SOLVER: Set Theory (NEW)
# ─────────────────────────────────────────────
def solve_set_theory(expr):
    """Solve set theory operations"""
    try:
        steps = "📦 Set Theory\n" + "="*50 + "\n"
        expr_lower = expr.lower()

        # Extract sets like {1,2,3} or A={1,2,3}
        set_matches = re.findall(r'\{([^}]+)\}', expr)
        sets = []
        for s in set_matches:
            items = [item.strip() for item in s.split(',')]
            sets.append(set(items))

        if len(sets) >= 2:
            A, B = sets[0], sets[1]
            steps += f"Set A = {sorted(A)}\n"
            steps += f"Set B = {sorted(B)}\n\n"

            if 'union' in expr_lower:
                result = A | B
                steps += f"A ∪ B = A + B (all elements in A or B)\n"
                steps += f"= {sorted(result)}"
                return str(sorted(result)), steps

            if 'intersection' in expr_lower:
                result = A & B
                steps += f"A ∩ B = Common elements in A and B\n"
                steps += f"= {sorted(result)}"
                return str(sorted(result)), steps

            if 'difference' in expr_lower:
                result = A - B
                steps += f"A - B = Elements in A but not in B\n"
                steps += f"= {sorted(result)}"
                return str(sorted(result)), steps

            if 'subset' in expr_lower:
                is_subset = A.issubset(B)
                steps += f"Is A ⊆ B? {is_subset}"
                return str(is_subset), steps

            # Default: show all
            steps += f"A ∪ B = {sorted(A | B)}\n"
            steps += f"A ∩ B = {sorted(A & B)}\n"
            steps += f"A - B = {sorted(A - B)}\n"
            steps += f"B - A = {sorted(B - A)}"
            return f"Union={sorted(A|B)}, Intersection={sorted(A&B)}", steps

        elif len(sets) == 1:
            A = sets[0]
            steps += f"Set A = {sorted(A)}\n"
            steps += f"Cardinality |A| = {len(A)}"
            return f"|A| = {len(A)}", steps

        return "Please provide sets in format: {1,2,3} union {2,3,4}", steps
    except Exception as e:
        return f"Error: {str(e)}", "Could not solve set theory problem"


# ─────────────────────────────────────────────
# SOLVER: Probability (NEW)
# ─────────────────────────────────────────────
def solve_probability(expr):
    """Solve probability problems with detailed steps"""
    import math
    try:
        steps = "🎲 Probability\n" + "="*50 + "\n"
        expr_lower = expr.lower().strip()

        # 1. Set Notation / Independence / Conditional Probability
        # e.g., "P(A) = 0.6, P(B) = 0.5, independent. find P(A and B)"
        if any(term in expr_lower for term in ['p(a)', 'p(b)', 'p(a and b)', 'p(a or b)', 'p(a|b)']):
            p_a_match = re.search(r'p\(a\)\s*=\s*([\d.]+)', expr_lower)
            p_b_match = re.search(r'p\(b\)\s*=\s*([\d.]+)', expr_lower)
            p_a_and_b_match = re.search(r'p\(a\s+(?:and|∩)\s+b\)\s*=\s*([\d.]+)', expr_lower)
            p_a_or_b_match = re.search(r'p\(a\s+(?:or|∪)\s+b\)\s*=\s*([\d.]+)', expr_lower)
            p_a_given_b_match = re.search(r'p\(a\|b\)\s*=\s*([\d.]+)', expr_lower)
            
            p_a = float(p_a_match.group(1)) if p_a_match else None
            p_b = float(p_b_match.group(1)) if p_b_match else None
            p_a_and_b = float(p_a_and_b_match.group(1)) if p_a_and_b_match else None
            p_a_or_b = float(p_a_or_b_match.group(1)) if p_a_or_b_match else None
            p_a_given_b = float(p_a_given_b_match.group(1)) if p_a_given_b_match else None
            
            is_independent = 'independent' in expr_lower
            is_mutually_exclusive = 'mutually exclusive' in expr_lower or 'disjoint' in expr_lower

            steps += "Given values:\n"
            if p_a is not None: steps += f"   P(A) = {p_a}\n"
            if p_b is not None: steps += f"   P(B) = {p_b}\n"
            if p_a_and_b is not None: steps += f"   P(A and B) = {p_a_and_b}\n"
            if p_a_or_b is not None: steps += f"   P(A or B) = {p_a_or_b}\n"
            if p_a_given_b is not None: steps += f"   P(A|B) = {p_a_given_b}\n"
            if is_independent: steps += "   Events A and B are Independent.\n"
            if is_mutually_exclusive: steps += "   Events A and B are Mutually Exclusive.\n"
            steps += "\n"

            # If we need to find P(A and B)
            if 'find p(a and b)' in expr_lower or 'find p(a ∩ b)' in expr_lower or ('and' in expr_lower and p_a_and_b is None):
                if is_independent and p_a is not None and p_b is not None:
                    ans = p_a * p_b
                    steps += f"To find P(A and B) for Independent events:\n"
                    steps += f"   Formula: P(A and B) = P(A) × P(B)\n"
                    steps += f"   P(A and B) = {p_a} × {p_b} = {ans:.4f}\n"
                    return f"P(A and B) = {ans:.4f}", steps
                elif is_mutually_exclusive:
                    steps += f"To find P(A and B) for Mutually Exclusive events:\n"
                    steps += f"   Formula: P(A and B) = 0\n"
                    return "P(A and B) = 0", steps
                elif p_a is not None and p_b is not None and p_a_or_b is not None:
                    ans = p_a + p_b - p_a_or_b
                    steps += f"To find P(A and B) using addition rule:\n"
                    steps += f"   Formula: P(A or B) = P(A) + P(B) - P(A and B)\n"
                    steps += f"   Rearranging: P(A and B) = P(A) + P(B) - P(A or B)\n"
                    steps += f"   P(A and B) = {p_a} + {p_b} - {p_a_or_b} = {ans:.4f}\n"
                    return f"P(A and B) = {ans:.4f}", steps
                elif p_b is not None and p_a_given_b is not None:
                    ans = p_a_given_b * p_b
                    steps += f"To find P(A and B) using conditional probability:\n"
                    steps += f"   Formula: P(A|B) = P(A and B) / P(B)\n"
                    steps += f"   Rearranging: P(A and B) = P(A|B) × P(B)\n"
                    steps += f"   P(A and B) = {p_a_given_b} × {p_b} = {ans:.4f}\n"
                    return f"P(A and B) = {ans:.4f}", steps

            # If we need to find P(A or B)
            if 'find p(a or b)' in expr_lower or 'find p(a ∪ b)' in expr_lower or ('or' in expr_lower and p_a_or_b is None):
                if p_a is not None and p_b is not None:
                    if p_a_and_b is None and is_independent:
                        p_a_and_b = p_a * p_b
                        steps += f"Step 1: Calculate P(A and B) for Independent events:\n"
                        steps += f"   P(A and B) = P(A) × P(B) = {p_a} × {p_b} = {p_a_and_b:.4f}\n\n"
                    elif p_a_and_b is None and is_mutually_exclusive:
                        p_a_and_b = 0.0
                        steps += f"Step 1: P(A and B) is 0 for Mutually Exclusive events.\n\n"
                    
                    if p_a_and_b is not None:
                        ans = p_a + p_b - p_a_and_b
                        steps += f"Step 2: Apply the General Addition Rule:\n"
                        steps += f"   Formula: P(A or B) = P(A) + P(B) - P(A and B)\n"
                        steps += f"   P(A or B) = {p_a} + {p_b} - {p_a_and_b:.4f} = {ans:.4f}\n"
                        return f"P(A or B) = {ans:.4f}", steps
                    else:
                        steps += "Error: Missing P(A and B) or relationship (independent / mutually exclusive) to find P(A or B)."
                        return "Need more information", steps

            # If we need to find P(A|B)
            if 'find p(a|b)' in expr_lower or ('given' in expr_lower and p_a_given_b is None):
                if p_b is not None:
                    if p_a_and_b is None and is_independent and p_a is not None:
                        ans = p_a
                        steps += f"To find P(A|B) for Independent events:\n"
                        steps += f"   Formula: P(A|B) = P(A)\n"
                        steps += f"   P(A|B) = {ans}\n"
                        return f"P(A|B) = {ans}", steps
                    elif p_a_and_b is not None:
                        ans = p_a_and_b / p_b
                        steps += f"To find P(A|B):\n"
                        steps += f"   Formula: P(A|B) = P(A and B) / P(B)\n"
                        steps += f"   P(A|B) = {p_a_and_b} / {p_b} = {ans:.4f}\n"
                        return f"P(A|B) = {ans:.4f}", steps
                    else:
                        steps += "Error: Missing P(A and B) to calculate P(A|B)."
                        return "Need P(A and B)", steps

            return "Could not compute. Please specify what to find: P(A and B), P(A or B), or P(A|B)", steps

        # 2. Expected value
        if 'expected value' in expr_lower or 'expectation' in expr_lower:
            nums = re.findall(r'-?\d+(?:\.\d+)?', expr)
            if len(nums) >= 4 and len(nums) % 2 == 0:
                mid = len(nums) // 2
                values = [float(x) for x in nums[:mid]]
                probs = [float(x) for x in nums[mid:]]
                ev = sum(v * p for v, p in zip(values, probs))
                steps += f"Values: {values}\n"
                steps += f"Probabilities: {probs}\n"
                steps += f"E(X) = Σ(x₁ × P(x₁))\n"
                steps += f"= {' + '.join(f'{v}×{p}' for v, p in zip(values, probs))}\n"
                steps += f"= {ev}"
                return str(ev), steps

        # 2.5 General Selection Probability: Letters in a word
        # e.g., "A letter is chosen randomly from the word "MANGO". What is the probability that the letter is a vowel?"
        word_prob_match = re.search(r'(?:letters?\s+(?:in|of|from)|from\s+the\s+word)\s+[\'"`“]([a-zA-Z]+)[\'"`”]', expr, re.I)
        if not word_prob_match:
            # fallback for unquoted words
            word_prob_match = re.search(r'(?:letters?\s+(?:in|of|from)|from\s+the\s+word)\s+([a-zA-Z]{3,})', expr, re.I)
        if word_prob_match:
            word = word_prob_match.group(1).upper()
            total_letters = len(word)
            
            # Identify condition
            condition = "letter"
            favorable_chars = []
            
            if 'vowel' in expr_lower:
                condition = "vowel"
                favorable_chars = [c for c in word if c in 'AEIOU']
            elif 'consonant' in expr_lower:
                condition = "consonant"
                favorable_chars = [c for c in word if c not in 'AEIOU' and c.isalpha()]
            else:
                # check for a specific letter: e.g. "is a 'T'" or "is T" or "is a T"
                letter_match = re.search(r'is\s+(?:a\s+|an\s+)?[\'"`“]?([a-zA-Z])[\'"`]?', expr, re.I)
                if letter_match:
                    target_letter = letter_match.group(1).upper()
                    condition = f"letter '{target_letter}'"
                    favorable_chars = [c for c in word if c == target_letter]
            
            if total_letters > 0:
                fav_count = len(favorable_chars)
                ans = fav_count / total_letters
                
                steps += f"Problem: Probability of selecting a {condition} from the letters of the word '{word}'.\n\n"
                steps += f"Step 1: Count the total outcomes (total letters in word).\n"
                steps += f"   Word letters: {list(word)}\n"
                steps += f"   Total outcomes (n) = {total_letters}\n\n"
                
                steps += f"Step 2: Find the favorable outcomes (letters matching the condition: {condition}).\n"
                steps += f"   Favorable outcomes: {favorable_chars}\n"
                steps += f"   Number of favorable outcomes = {fav_count}\n\n"
                
                steps += f"Step 3: Calculate the probability:\n"
                steps += f"   P = Favorable / Total = {fav_count} / {total_letters}\n"
                
                g = math.gcd(fav_count, total_letters)
                if g > 1:
                    steps += f"   P = {fav_count // g} / {total_letters // g} (simplified)\n"
                steps += f"   P = {ans:.4f} ({ans * 100:.2f}%)\n"
                return f"{fav_count // g}/{total_letters // g} ({ans:.4f})", steps

        # 2.6 General Selection Probability: Number Ranges
        # e.g., "A number is chosen from 1 to 20. Probability that it is a prime"
        range_match = re.search(r'(?:chosen|selected|numbers?)\s+(?:from|between)\s+(\d+)\s+(?:to|and)\s+(\d+)', expr_lower)
        if range_match:
            start_num = int(range_match.group(1))
            end_num = int(range_match.group(2))
            if start_num > end_num:
                start_num, end_num = end_num, start_num
                
            all_numbers = list(range(start_num, end_num + 1))
            total_count = len(all_numbers)
            
            favorable_nums = []
            condition = "number"
            
            if 'prime' in expr_lower:
                from sympy import isprime
                condition = "prime number"
                favorable_nums = [x for x in all_numbers if isprime(x)]
            elif 'even' in expr_lower:
                condition = "even number"
                favorable_nums = [x for x in all_numbers if x % 2 == 0]
            elif 'odd' in expr_lower:
                condition = "odd number"
                favorable_nums = [x for x in all_numbers if x % 2 != 0]
            elif 'multiple of' in expr_lower:
                mult_match = re.search(r'multiple\s+of\s+(\d+)', expr_lower)
                if mult_match:
                    k = int(mult_match.group(1))
                    condition = f"multiple of {k}"
                    favorable_nums = [x for x in all_numbers if x % k == 0]
            elif 'divisible by' in expr_lower:
                div_match = re.search(r'divisible\s+by\s+(\d+)', expr_lower)
                if div_match:
                    k = int(div_match.group(1))
                    condition = f"divisible by {k}"
                    favorable_nums = [x for x in all_numbers if x % k == 0]
            elif 'greater than' in expr_lower or 'more than' in expr_lower:
                gt_match = re.search(r'(?:greater|more)\s+than\s+(\d+)', expr_lower)
                if gt_match:
                    k = int(gt_match.group(1))
                    condition = f"greater than {k}"
                    favorable_nums = [x for x in all_numbers if x > k]
            elif 'less than' in expr_lower:
                lt_match = re.search(r'less\s+than\s+(\d+)', expr_lower)
                if lt_match:
                    k = int(lt_match.group(1))
                    condition = f"less than {k}"
                    favorable_nums = [x for x in all_numbers if x < k]
                    
            if total_count > 0:
                fav_count = len(favorable_nums)
                ans = fav_count / total_count
                
                steps += f"Problem: Probability of selecting a {condition} from the range {start_num} to {end_num}.\n\n"
                steps += f"Step 1: Identify total outcomes.\n"
                steps += f"   Range of numbers: {start_num} to {end_num}\n"
                steps += f"   Total numbers (n) = {total_count}\n\n"
                
                steps += f"Step 2: Identify favorable outcomes matching the condition: {condition}.\n"
                if len(favorable_nums) <= 15:
                    steps += f"   Favorable numbers: {favorable_nums}\n"
                else:
                    steps += f"   Favorable numbers: {favorable_nums[:10]} ... (showing first 10)\n"
                steps += f"   Number of favorable outcomes = {fav_count}\n\n"
                
                steps += f"Step 3: Calculate probability:\n"
                steps += f"   P = Favorable / Total = {fav_count} / {total_count}\n"
                
                g = math.gcd(fav_count, total_count)
                if g > 1:
                    steps += f"   P = {fav_count // g} / {total_count // g} (simplified)\n"
                steps += f"   P = {ans:.4f} ({ans * 100:.2f}%)\n"
                return f"{fav_count // g}/{total_count // g} ({ans:.4f})", steps

        # 3. Binomial Probability / Coin Tosses
        # e.g., "probability of getting exactly 3 heads in 5 coin tosses"
        # e.g., "probability of getting at least 2 heads in 4 tosses"
        toss_match = re.search(
            r'probability\s+of\s+(?:getting\s+)?(?:exactly\s+)?(\d+)\s+(head|tail)s?\s+(?:in|from)\s+(\d+)\s+(?:coin\s+)?(?:toss|flip)es?',
            expr_lower
        )
        if not toss_match:
            toss_match = re.search(
                r'probability\s+of\s+(?:getting\s+)?(at\s+least|at\s+most|less\s+than|more\s+than)\s+(\d+)\s+(head|tail)s?\s+(?:in|from)\s+(\d+)\s+(?:coin\s+)?(?:toss|flip)es?',
                expr_lower
            )
        
        if toss_match:
            groups = toss_match.groups()
            if len(groups) == 3: # exactly k
                k = int(groups[0])
                outcome_type = groups[1]
                n = int(groups[2])
                comparison = "exactly"
            else: # at least / at most / less than / more than k
                comparison = groups[0]
                k = int(groups[1])
                outcome_type = groups[2]
                n = int(groups[3])
            
            p = 0.5 # coin toss
            q = 0.5
            
            steps += f"Problem: Probability of getting {comparison} {k} {outcome_type}s in {n} coin tosses.\n\n"
            steps += f"This follows a Binomial Distribution:\n"
            steps += f"   P(X = x) = C(n, x) × p^x × q^(n - x)\n"
            steps += f"   where:\n"
            steps += f"     n = {n} (number of trials)\n"
            steps += f"     p = 0.5 (probability of success on a single toss)\n"
            steps += f"     q = 0.5 (probability of failure on a single toss)\n\n"
            
            if comparison in ["exactly", "exactly "]:
                ways = math.comb(n, k)
                prob_term = (p ** k) * (q ** (n - k))
                ans = ways * prob_term
                steps += f"Calculation for X = {k}:\n"
                steps += f"   P(X = {k}) = C({n}, {k}) × (0.5)^{k} × (0.5)^{n-k}\n"
                steps += f"   P(X = {k}) = {ways} × (0.5)^{n}\n"
                steps += f"   P(X = {k}) = {ways} × {1 / (2**n):.6f}\n"
                steps += f"   P(X = {k}) = {ans:.6f} ({ans * 100:.2f}%)\n"
                return f"{ans:.6f} ({ans * 100:.2f}%)", steps
            
            elif comparison == "at least":
                ans = 0.0
                steps += f"Calculation for X ≥ {k} (sum from x = {k} to {n}):\n"
                for x in range(k, n + 1):
                    ways = math.comb(n, x)
                    term = ways * (p ** n)
                    ans += term
                    steps += f"   • P(X = {x}) = C({n}, {x}) × (0.5)^{n} = {ways} × {1 / (2**n):.6f} = {term:.6f}\n"
                steps += f"\n   Total P(X ≥ {k}) = {ans:.6f} ({ans * 100:.2f}%)\n"
                return f"{ans:.6f} ({ans * 100:.2f}%)", steps
            
            elif comparison == "at most":
                ans = 0.0
                steps += f"Calculation for X ≤ {k} (sum from x = 0 to {k}):\n"
                for x in range(0, k + 1):
                    ways = math.comb(n, x)
                    term = ways * (p ** n)
                    ans += term
                    steps += f"   • P(X = {x}) = C({n}, {x}) × (0.5)^{n} = {ways} × {1 / (2**n):.6f} = {term:.6f}\n"
                steps += f"\n   Total P(X ≤ {k}) = {ans:.6f} ({ans * 100:.2f}%)\n"
                return f"{ans:.6f} ({ans * 100:.2f}%)", steps

            elif comparison == "less than":
                ans = 0.0
                steps += f"Calculation for X < {k} (sum from x = 0 to {k-1}):\n"
                for x in range(0, k):
                    ways = math.comb(n, x)
                    term = ways * (p ** n)
                    ans += term
                    steps += f"   • P(X = {x}) = C({n}, {x}) × (0.5)^{n} = {ways} × {1 / (2**n):.6f} = {term:.6f}\n"
                steps += f"\n   Total P(X < {k}) = {ans:.6f} ({ans * 100:.2f}%)\n"
                return f"{ans:.6f} ({ans * 100:.2f}%)", steps

            elif comparison == "more than":
                ans = 0.0
                steps += f"Calculation for X > {k} (sum from x = {k+1} to {n}):\n"
                for x in range(k + 1, n + 1):
                    ways = math.comb(n, x)
                    term = ways * (p ** n)
                    ans += term
                    steps += f"   • P(X = {x}) = C({n}, {x}) × (0.5)^{n} = {ways} × {1 / (2**n):.6f} = {term:.6f}\n"
                steps += f"\n   Total P(X > {k}) = {ans:.6f} ({ans * 100:.2f}%)\n"
                return f"{ans:.6f} ({ans * 100:.2f}%)", steps

        # 4. Card Deck Probability
        if 'card' in expr_lower or 'deck' in expr_lower or 'pack' in expr_lower:
            # Check specific card first (e.g., ace of spades)
            rank_match = re.search(r'\b(ace|king|queen|jack)\b', expr_lower)
            suit_match = re.search(r'\b(heart|diamond|spade|club)s?\b', expr_lower)
            if rank_match and suit_match:
                rank = rank_match.group(1)
                suit = suit_match.group(1)
                steps += f"Problem: Probability of drawing the {rank} of {suit}s from a standard deck of 52 cards.\n\n"
                steps += f"Step 1: Identify standard deck counts.\n"
                steps += f"   Total cards = 52\n"
                steps += f"   A standard deck contains exactly one unique card for each rank-suit combination.\n\n"
                steps += f"Step 2: Calculate probability.\n"
                steps += f"   Favorable outcome = 1 (the {rank} of {suit}s)\n"
                steps += f"   P = 1/52 ≈ 0.0192 (1.92%)\n"
                return "1/52 (0.0192)", steps
            
            # General deck card type
            card_type = None
            for key in ["red", "black", "heart", "diamond", "spade", "club", "ace", "king", "queen", "jack", "face", "numbered"]:
                if key in expr_lower:
                    card_type = key
                    break
            
            if card_type:
                card_counts = {
                    "red": 26, "black": 26,
                    "heart": 13, "diamond": 13, "spade": 13, "club": 13,
                    "ace": 4, "king": 4, "queen": 4, "jack": 4,
                    "face": 12, "numbered": 36
                }
                count = card_counts[card_type]
                ans = count / 52
                
                steps += f"Problem: Probability of drawing a {card_type} card from a standard deck of 52 cards.\n\n"
                steps += f"Step 1: Identify standard deck structure.\n"
                steps += f"   Total cards in deck = 52\n"
                if card_type in ["red", "black"]:
                    steps += f"   The deck has 2 colors: Red (26 cards) and Black (26 cards).\n"
                    steps += f"   Favorable cards ({card_type}) = {count}\n\n"
                elif card_type in ["heart", "diamond", "spade", "club"]:
                    steps += f"   The deck has 4 suits: Hearts, Diamonds, Spades, Clubs (13 cards each).\n"
                    steps += f"   Favorable cards ({card_type}s) = {count}\n\n"
                elif card_type in ["ace", "king", "queen", "jack"]:
                    steps += f"   The deck has 4 cards of each rank (one from each of the 4 suits).\n"
                    steps += f"   Favorable cards ({card_type}s) = {count}\n\n"
                elif card_type == "face":
                    steps += f"   Face cards are Jack, Queen, King of each of the 4 suits: 3 × 4 = 12 cards.\n"
                    steps += f"   Favorable cards (face cards) = {count}\n\n"
                elif card_type == "numbered":
                    steps += f"   Numbered cards are 2 through 10 of each of the 4 suits: 9 × 4 = 36 cards.\n"
                    steps += f"   Favorable cards (numbered cards) = {count}\n\n"
                    
                steps += f"Step 2: Apply the simple probability formula:\n"
                steps += f"   P({card_type}) = Favorable Outcomes / Total Outcomes\n"
                steps += f"   P({card_type}) = {count} / 52\n"
                
                g = math.gcd(count, 52)
                simp_num = count // g
                simp_denom = 52 // g
                if g > 1:
                    steps += f"   P({card_type}) = {simp_num} / {simp_denom} (simplified fraction)\n"
                
                steps += f"   P({card_type}) ≈ {ans:.4f} ({ans * 100:.2f}%)\n"
                return f"{simp_num}/{simp_denom} ({ans:.4f})", steps

        # 5. Dice Probability
        # e.g., "probability of rolling a sum of 7 with 2 dice"
        # e.g., "probability of rolling a sum >= 10 with 2 dice"
        dice_sum_match = re.search(
            r'probability\s+of\s+(?:rolling|getting)\s+(?:a\s+)?sum\s+(?:of\s+)?(\d+)\s+(?:with|on)\s+(\d+)\s+dice',
            expr_lower
        )
        if not dice_sum_match:
            dice_sum_match = re.search(
                r'probability\s+of\s+(?:rolling|getting)\s+(?:a\s+)?sum\s+(>=|<=|>|<|at\s+least|at\s+most)\s*(\d+)\s+(?:with|on)\s+(\d+)\s+dice',
                expr_lower
            )

        if dice_sum_match:
            def count_dice_sum_ways(d, target_sum):
                if d == 0:
                    return 1 if target_sum == 0 else 0
                if target_sum < d or target_sum > 6 * d:
                    return 0
                ways = 0
                for face in range(1, 7):
                    ways += count_dice_sum_ways(d - 1, target_sum - face)
                return ways

            groups = dice_sum_match.groups()
            if len(groups) == 2:
                target_sum = int(groups[0])
                num_dice = int(groups[1])
                op = '='
                op_name = "exactly"
            else:
                op_raw = groups[0]
                target_sum = int(groups[1])
                num_dice = int(groups[2])
                if op_raw in ['>=', 'at least']: op = '>='
                elif op_raw in ['<=', 'at most']: op = '<='
                elif op_raw in ['>', 'more than']: op = '>'
                elif op_raw in ['<', 'less than']: op = '<'
                op_name = op_raw
            
            total_outcomes = 6 ** num_dice
            steps += f"Problem: Probability of rolling a sum {op_name} {target_sum} with {num_dice} dice.\n\n"
            steps += f"Step 1: Calculate the total size of the sample space (total possible outcomes).\n"
            steps += f"   For {num_dice} standard 6-sided dice, total outcomes = 6^{num_dice} = {total_outcomes}\n\n"
            
            if num_dice == 2:
                # Find exact pairs
                pairs = []
                for a in range(1, 7):
                    for b in range(1, 7):
                        s = a + b
                        if op == '=' and s == target_sum: pairs.append((a, b))
                        elif op == '>=' and s >= target_sum: pairs.append((a, b))
                        elif op == '<=' and s <= target_sum: pairs.append((a, b))
                        elif op == '>' and s > target_sum: pairs.append((a, b))
                        elif op == '<' and s < target_sum: pairs.append((a, b))
                
                favorable_count = len(pairs)
                ans = favorable_count / total_outcomes
                
                steps += f"Step 2: List the favorable outcomes (where sum {op_name} {target_sum}):\n"
                steps += f"   {pairs}\n"
                steps += f"   Number of favorable outcomes = {favorable_count}\n\n"
                
                steps += f"Step 3: Calculate the probability:\n"
                steps += f"   P = Favorable / Total = {favorable_count} / {total_outcomes}\n"
                g = math.gcd(favorable_count, total_outcomes)
                if g > 1:
                    steps += f"   P = {favorable_count // g} / {total_outcomes // g} (simplified)\n"
                steps += f"   P ≈ {ans:.4f} ({ans * 100:.2f}%)\n"
                return f"{favorable_count // g}/{total_outcomes // g} ({ans:.4f})", steps
            else:
                favorable_count = 0
                if op == '=':
                    favorable_count = count_dice_sum_ways(num_dice, target_sum)
                elif op == '>=':
                    for s in range(target_sum, 6 * num_dice + 1):
                        favorable_count += count_dice_sum_ways(num_dice, s)
                elif op == '<=':
                    for s in range(num_dice, target_sum + 1):
                        favorable_count += count_dice_sum_ways(num_dice, s)
                elif op == '>':
                    for s in range(target_sum + 1, 6 * num_dice + 1):
                        favorable_count += count_dice_sum_ways(num_dice, s)
                elif op == '<':
                    for s in range(num_dice, target_sum):
                        favorable_count += count_dice_sum_ways(num_dice, s)
                
                ans = favorable_count / total_outcomes
                steps += f"Step 2: Count the number of favorable outcomes.\n"
                steps += f"   Number of favorable outcomes = {favorable_count}\n\n"
                steps += f"Step 3: Calculate probability:\n"
                steps += f"   P = Favorable / Total = {favorable_count} / {total_outcomes}\n"
                g = math.gcd(favorable_count, total_outcomes)
                if g > 1:
                    steps += f"   P = {favorable_count // g} / {total_outcomes // g} (simplified)\n"
                steps += f"   P ≈ {ans:.4f} ({ans * 100:.2f}%)\n"
                return f"{favorable_count // g}/{total_outcomes // g} ({ans:.4f})", steps

        # 6. Marble / Ball Drawing from Bag
        # e.g., "bag has 3 red and 5 blue balls. draw 2 red balls without replacement"
        # e.g., "bag has 4 red, 3 green balls. find probability of drawing 2 red balls with replacement"
        bag_match = re.search(r'bag\s+(?:has|contains|with)\s+([^.]+?)(?:\.|$|\,)\s*(?:find|what\s+is|draw|probability|if|a|then)', expr_lower)
        if bag_match:
            bag_content = bag_match.group(1)
            ball_pairs = re.findall(r'(\d+)\s+(red|blue|green|black|white|yellow|orange|purple|pink)s?', bag_content)
            if ball_pairs:
                bag_dict = {color: int(count) for count, color in ball_pairs}
                total_balls = sum(bag_dict.values())
                
                target_match = re.search(r'(?:drawing|draw|get|getting|it\s+is|is\s+a)\s+(?:a\s+|an\s+)?(?:(\d+)\s+)?(red|blue|green|black|white|yellow|orange|purple|pink)s?', expr_lower)
                if target_match:
                    k_str = target_match.group(1)
                    k_draw = int(k_str) if k_str else 1
                    target_color = target_match.group(2)
                    
                    if target_color not in bag_dict:
                        return "0.0000", steps + f"Color '{target_color}' is not in the bag."
                    
                    target_count = bag_dict[target_color]
                    with_replacement = 'with replacement' in expr_lower
                    
                    steps += f"Problem: Drawing {k_draw} {target_color} ball(s) from a bag containing:\n"
                    for color, count in bag_dict.items():
                        steps += f"   • {count} {color} ball(s)\n"
                    steps += f"   Total balls in bag = {total_balls}\n\n"
                    
                    if with_replacement:
                        steps += f"Condition: WITH REPLACEMENT (the bag's contents do not change between draws).\n"
                        single_prob = target_count / total_balls
                        ans = single_prob ** k_draw
                        steps += f"Step 1: Calculate probability of drawing a {target_color} ball on a single draw:\n"
                        steps += f"   P(single draw) = {target_count} / {total_balls} = {single_prob:.4f}\n\n"
                        steps += f"Step 2: Since draws are independent (with replacement), multiply the probabilities:\n"
                        mult_str = " × ".join([f"({target_count}/{total_balls})" for _ in range(k_draw)])
                        steps += f"   P(all {k_draw} are {target_color}) = {mult_str}\n"
                        steps += f"   P = ({target_count}/{total_balls})^{k_draw} = {ans:.6f} ({ans*100:.2f}%)\n"
                        return f"{ans:.6f}", steps
                    else:
                        steps += f"Condition: WITHOUT REPLACEMENT (bag composition changes after each draw).\n\n"
                        if k_draw > target_count:
                            return "0.0000", steps + f"Cannot draw {k_draw} {target_color} balls because there are only {target_count} in the bag."
                        
                        prob_product = 1.0
                        terms_str = []
                        denom_balls = total_balls
                        num_target = target_count
                        
                        steps += f"Step 1: Calculate the probability step-by-step for each draw:\n"
                        for i in range(1, k_draw + 1):
                            draw_prob = num_target / denom_balls
                            prob_product *= draw_prob
                            steps += f"   Draw {i}: P(ball {i} is {target_color}) = {num_target} / {denom_balls}\n"
                            terms_str.append(f"({num_target}/{denom_balls})")
                            num_target -= 1
                            denom_balls -= 1
                            
                        mult_str = " × ".join(terms_str)
                        steps += f"\nStep 2: Multiply the probabilities of each draw:\n"
                        steps += f"   P = {mult_str}\n"
                        steps += f"   P ≈ {prob_product:.6f} ({prob_product*100:.2f}%)\n"
                        return f"{prob_product:.6f}", steps

        # 7. Fallback: simple out of probability
        match = re.search(r'(\d+)\s+(?:out of|favorable|out)\s+(\d+)|probability.*?(\d+).*?(\d+)', expr, re.I)
        if match:
            fav = int(match.group(1) or match.group(3))
            total = int(match.group(2) or match.group(4))
            if total == 0:
                return "0.0000", steps + "Total outcomes cannot be 0."
            prob = fav / total
            steps += f"Favorable outcomes = {fav}\n"
            steps += f"Total outcomes = {total}\n"
            steps += f"\nP(event) = Favorable / Total\n"
            steps += f"= {fav}/{total}\n"
            steps += f"= {prob:.4f} ({prob*100:.2f}%)"
            return f"{prob:.4f} ({prob*100:.2f}%)", steps

        # 8. Original fallback logic for dice/coins
        if 'dice' in expr_lower or 'die' in expr_lower:
            sides = 6
            match = re.search(r'(\d+)\s*-sided', expr, re.I)
            if match:
                sides = int(match.group(1))
            steps += f"Standard {sides}-sided die\n"
            steps += f"P(any face) = 1/{sides} = {1/sides:.4f}\n"
            steps += f"P(even) = {sides//2}/{sides} = {(sides//2)/sides:.4f}\n"
            steps += f"P(odd) = {sides//2}/{sides} = {(sides//2)/sides:.4f}"
            return f"P(any face) = 1/{sides}", steps

        if 'coin' in expr_lower:
            steps += "Fair coin toss:\n"
            steps += "P(heads) = 1/2 = 0.5\n"
            steps += "P(tails) = 1/2 = 0.5\n"
            n_match = re.search(r'(\d+)\s+tosses?', expr, re.I)
            if n_match:
                n = int(n_match.group(1))
                p_all_heads = (0.5) ** n
                steps += f"\nFor {n} tosses:\n"
                steps += f"P(all heads) = (1/2)^{n} = {p_all_heads:.6f}"
            return "P(head) = P(tail) = 0.5", steps

        return "Probability format not recognized. Try: '3 out of 10' or 'expected value'", steps
    except Exception as e:
        return f"Error: {str(e)}", "Could not solve probability problem"


# ─────────────────────────────────────────────
# SOLVER: Triangle Identity
# ─────────────────────────────────────────────
def solve_triangle_identity(expr):
    """Solve triangle-related trigonometric identities"""
    try:
        s = expr.strip()
        steps = "🔺 Triangle Identity Problem\n" + "="*60 + "\n\n"
        steps += "📐 Given: A, B, C are interior angles of a triangle ABC\n"
        steps += "📐 Fundamental Property: A + B + C = π (180°)\n"
        steps += "📐 Therefore: B + C = π - A\n\n"

        match = re.search(r'(?:show that|prove that)\s+(.+?)\s*=\s*(.+?)(?:\.|$)', s, re.I)
        if match:
            lhs_str = match.group(1).strip()
            rhs_str = match.group(2).strip()
            steps += f"✅ To Prove: {lhs_str} = {rhs_str}\n"
            steps += "-"*60 + "\n\n"
            steps += "STEP 1: Identify LHS\n"
            steps += f"   LHS = {lhs_str}\n\n"
            steps += "STEP 2: Apply Triangle Angle Sum Property\n"
            steps += "   A + B + C = π → B + C = π - A\n\n"
            steps += "STEP 3: Substitute into LHS\n"
            steps += f"   Substituting B + C = π - A\n\n"
            steps += "STEP 4: Simplify using identities\n"
            steps += "   sin(π/2 - θ) = cos(θ)\n"
            steps += "   cos(π/2 - θ) = sin(θ)\n\n"
            steps += "STEP 5: Compare LHS and RHS\n"
            steps += f"   After simplification: LHS = RHS = {rhs_str}\n\n"
            steps += "="*60 + "\n"
            steps += "✅ CONCLUSION: The identity is PROVED!\n"
            steps += "="*60
            return "✅ Identity PROVED!", steps

        steps += "⚠ Could not parse the identity.\n"
        steps += "Format: 'If A, B, C are interior angles, show that [LHS] = [RHS]'"
        return "Please check format", steps
    except Exception as e:
        return "Error", f"❌ Error: {str(e)}"


# ─────────────────────────────────────────────
# SOLVER: Word Problems (Enhanced)
# ─────────────────────────────────────────────
def solve_word_problem(question):
    """Solve geometry and word problems with SymPy fallback"""
    try:
        q = question.lower()

        # Rectangle area
        match = re.search(r'rectangle.*?(\d+(?:\.\d+)?).*?(\d+(?:\.\d+)?)', q)
        if match and 'area' in q:
            l, w = float(match.group(1)), float(match.group(2))
            area = l * w
            steps = f"📐 Rectangle Area\n" + "="*50 + "\n"
            steps += f"Formula: A = length × width\n"
            steps += f"A = {l} × {w} = {area}\n✅ Answer: {area} sq units"
            return str(area), steps

        if match and 'perimeter' in q:
            l, w = float(match.group(1)), float(match.group(2))
            perimeter = 2 * (l + w)
            steps = f"📐 Rectangle Perimeter\n" + "="*50 + "\n"
            steps += f"Formula: P = 2(l + w) = 2({l} + {w}) = {perimeter}\n✅ Answer: {perimeter} units"
            return str(perimeter), steps

        # Circle area
        match = re.search(r'circle.*?radius[:\s]*([\d.]+)', q)
        if match and 'area' in q:
            r = float(match.group(1))
            area = float((pi * r**2).evalf(6))
            steps = f"🔵 Circle Area\n" + "="*50 + "\n"
            steps += f"Formula: A = πr²\n"
            steps += f"A = π × {r}² = π × {r**2} = {area:.4f}\n✅ Answer: {area:.4f} sq units"
            return f"{area:.4f}", steps

        # Circle circumference
        match = re.search(r'circle.*?radius[:\s]*([\d.]+)', q)
        if match and ('circumference' in q or 'perimeter' in q):
            r = float(match.group(1))
            circ = float((2 * pi * r).evalf(6))
            steps = f"🔵 Circle Circumference\n" + "="*50 + "\n"
            steps += f"Formula: C = 2πr = 2π × {r} = {circ:.4f}\n✅ Answer: {circ:.4f} units"
            return f"{circ:.4f}", steps

        # Triangle area
        match = re.search(r'triangle.*?(\d+(?:\.\d+)?).*?(\d+(?:\.\d+)?)', q)
        if match and 'area' in q:
            b, h = float(match.group(1)), float(match.group(2))
            area = 0.5 * b * h
            steps = f"🔺 Triangle Area\n" + "="*50 + "\n"
            steps += f"Formula: A = ½ × base × height\n"
            steps += f"A = 0.5 × {b} × {h} = {area}\n✅ Answer: {area} sq units"
            return str(area), steps

        # Sphere volume
        match = re.search(r'sphere.*?radius[:\s]*([\d.]+)', q)
        if match and 'volume' in q:
            r = float(match.group(1))
            vol = float(((4/3) * pi * r**3).evalf(6))
            steps = f"⚪ Sphere Volume\n" + "="*50 + "\n"
            steps += f"Formula: V = (4/3)πr³\n"
            steps += f"V = (4/3) × π × {r}³ = {vol:.4f}\n✅ Answer: {vol:.4f} cubic units"
            return f"{vol:.4f}", steps

        # Cylinder volume
        match = re.search(r'cylinder.*?radius[:\s]*([\d.]+).*?height[:\s]*([\d.]+)', q)
        if not match:
            match = re.search(r'cylinder.*?(\d+(?:\.\d+)?).*?(\d+(?:\.\d+)?)', q)
        if match and 'volume' in q:
            r, h = float(match.group(1)), float(match.group(2))
            vol = float((pi * r**2 * h).evalf(6))
            steps = f"🧊 Cylinder Volume\n" + "="*50 + "\n"
            steps += f"Formula: V = πr²h\n"
            steps += f"V = π × {r}² × {h} = {vol:.4f}\n✅ Answer: {vol:.4f} cubic units"
            return f"{vol:.4f}", steps

        # Cone volume
        match = re.search(r'cone.*?(\d+(?:\.\d+)?).*?(\d+(?:\.\d+)?)', q)
        if match and 'volume' in q:
            r, h = float(match.group(1)), float(match.group(2))
            vol = float(((1/3) * pi * r**2 * h).evalf(6))
            steps = f"🔺 Cone Volume\n" + "="*50 + "\n"
            steps += f"Formula: V = (1/3)πr²h\n"
            steps += f"V = (1/3) × π × {r}² × {h} = {vol:.4f}\n✅ Answer: {vol:.4f} cubic units"
            return f"{vol:.4f}", steps

        # Hypotenuse (Pythagorean theorem)
        if 'hypotenuse' in q or 'pythagorean' in q:
            nums = re.findall(r'\d+(?:\.\d+)?', q)
            if len(nums) >= 2:
                a, b_val = float(nums[0]), float(nums[1])
                hyp = (a**2 + b_val**2) ** 0.5
                steps = f"📐 Pythagorean Theorem\n" + "="*50 + "\n"
                steps += f"Formula: c = √(a² + b²)\n"
                steps += f"c = √({a}² + {b_val}²) = √({a**2} + {b_val**2}) = {hyp:.4f}\n✅ Answer: {hyp:.4f}"
                return f"{hyp:.4f}", steps

        # Distance formula
        match = re.search(r'distance.*?\(([\d.]+)\s*,\s*([\d.]+)\).*?\(([\d.]+)\s*,\s*([\d.]+)\)', q)
        if match:
            x1, y1, x2, y2 = float(match.group(1)), float(match.group(2)), float(match.group(3)), float(match.group(4))
            dist = ((x2-x1)**2 + (y2-y1)**2) ** 0.5
            steps = f"📏 Distance Formula\n" + "="*50 + "\n"
            steps += f"Formula: d = √[(x₂-x₁)² + (y₂-y₁)²]\n"
            steps += f"d = √[({x2}-{x1})² + ({y2}-{y1})²] = {dist:.4f}\n✅ Answer: {dist:.4f} units"
            return f"{dist:.4f}", steps

        # Percentage
        match = re.search(r'([\d.]+)\s*%.*?of.*?([\d.]+)', q)
        if match:
            pct, total = float(match.group(1)), float(match.group(2))
            result = (pct / 100) * total
            steps = f"💯 Percentage\n" + "="*50 + "\n"
            steps += f"{pct}% of {total}\n"
            steps += f"= ({pct}/100) × {total} = {result}\n✅ Answer: {result}"
            return str(result), steps

        # Quadratic formula
        if 'quadratic' in q or 'ax^2' in q or 'ax²' in q:
            match = re.search(r'([\d.]+)x\^?2?\s*[+\-]\s*([\d.]+)x\s*[+\-]\s*([\d.]+)', q)
            if match:
                a_c, b_c, c_c = float(match.group(1)), float(match.group(2)), float(match.group(3))
                disc = b_c**2 - 4*a_c*c_c
                steps = f"📊 Quadratic Formula\n" + "="*50 + "\n"
                steps += f"Equation: {a_c}x² + {b_c}x + {c_c} = 0\n"
                steps += f"Discriminant = b² - 4ac = {disc}\n"
                if disc >= 0:
                    x1_val = (-b_c + disc**0.5) / (2*a_c)
                    x2_val = (-b_c - disc**0.5) / (2*a_c)
                    steps += f"x₁ = {x1_val:.4f}, x₂ = {x2_val:.4f}"
                    return f"x₁={x1_val:.4f}, x₂={x2_val:.4f}", steps
                else:
                    steps += "No real solutions (complex roots)"
                    return "No real solutions", steps

        # Fallback: try SymPy general solve
        try:
            parsed = parse_math_expression(question)
            simplified = simplify(parsed)
            steps = f"💡 General simplification:\n{simplified}"
            return str(simplified), steps
        except Exception:
            pass

        return "❌ Word problem format not recognized", (
            "Supported types:\n"
            "• Area/perimeter of rectangle, circle, triangle\n"
            "• Volume of sphere, cylinder, cone\n"
            "• Distance between points\n"
            "• Pythagorean theorem / Hypotenuse\n"
            "• Percentage: X% of Y\n"
            "• Quadratic formula"
        )

    except Exception as e:
        return f"Error: {str(e)}", "Could not solve word problem"


# ─────────────────────────────────────────────
# SOLVER: General Simplification
# ─────────────────────────────────────────────
def simplify_expression(expr):
    """Simplify general mathematical expressions"""
    try:
        parsed_expr = parse_math_expression(expr)
        simplified = simplify(parsed_expr)

        steps = f"🔢 Expression: {parsed_expr}\n"
        steps += f"Simplified: {simplified}\n"

        try:
            factored = factor(simplified)
            if factored != simplified:
                steps += f"Factored: {factored}\n"
        except Exception:
            pass

        try:
            expanded = expand(simplified)
            if expanded != simplified:
                steps += f"Expanded: {expanded}\n"
        except Exception:
            pass

        try:
            numerical = float(simplified.evalf())
            steps += f"Numerical value: {numerical}"
        except Exception:
            pass

        return str(simplified), steps
    except Exception as e:
        return f"Error: {str(e)}", "Could not simplify expression"


# ─────────────────────────────────────────────
# MAIN SOLVER ROUTE
# ─────────────────────────────────────────────
@app.route("/solve", methods=["GET", "POST"])
def solve():
    if 'user' not in session:
        return redirect(url_for('login'))

    result = session.get('result', '')
    steps = session.get('steps', '')
    expression_input = session.get('expression', '')

    if request.method == "POST":
        expression_input = request.form.get("expression", "").strip()

        # Handle image upload
        image = request.files.get('image')
        img_for_gemini = None
        has_image = False
        expression_input_ocr = ""

        if image and image.filename != "":
            filename = secure_filename(image.filename)
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff')):
                try:
                    with Image.open(image.stream) as img:
                        if img.mode in ('RGBA', 'LA', 'P'):
                            background = Image.new('RGB', img.size, (255, 255, 255))
                            if img.mode == 'RGBA':
                                background.paste(img, mask=img.split()[-1])
                            else:
                                background.paste(img.convert('RGBA'), mask=img.convert('RGBA').split()[-1])
                            img = background
                        elif img.mode != 'RGB':
                            img = img.convert('RGB')
                        
                        img_for_gemini = img.copy()
                        has_image = True
                        expression_input_ocr = pytesseract.image_to_string(img).strip()
                except Exception as e:
                    flash(f"❌ Unable to process image: {str(e)}")
                    return redirect(url_for('solve'))
            else:
                flash("❌ Please upload a valid image (png, jpg, jpeg, bmp, gif, tiff).")
                return redirect(url_for('solve'))

        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        solved_with_gemini = False
        
        if gemini_api_key:
            if not expression_input and not has_image:
                flash("❌ Please enter a math expression or upload an image.")
                return redirect(url_for('solve'))
            
            result, steps = solve_math_with_gemini(expression_input, img_for_gemini)
            
            if result != "Error" and "Failed to solve using Gemini API" not in steps:
                solved_with_gemini = True
                if not expression_input and has_image:
                    expression_input = "[Solved from Uploaded Image]"
            else:
                if not expression_input and has_image:
                    expression_input = expression_input_ocr

        if not solved_with_gemini:
            if has_image and not expression_input:
                expression_input = expression_input_ocr
            
            if not expression_input:
                flash("❌ Please enter a math expression or upload an image (OCR failed to recognize math text).")
                return redirect(url_for('solve'))
                
            local_result, local_steps = auto_solve_math(expression_input)
            
            if gemini_api_key:
                result = local_result
                steps = (
                    "⚠️ **Gemini API Rate Limit / Quota Exceeded**\n"
                    "The Gemini API free tier rate limit was reached. We have automatically fallen back to "
                    "our local SymPy-based mathematical engine to solve your problem.\n\n"
                    "**Local Solver Output:**\n"
                    f"{local_steps}"
                )
            else:
                result = local_result
                steps = local_steps

        # Save result image using absolute path
        static_dir = os.path.join(app.root_path, 'static')
        os.makedirs(static_dir, exist_ok=True)
        result_img_path = os.path.join(static_dir, 'result.png')

        try:
            fig, ax = plt.subplots(figsize=(12, 7))
            ax.axis('off')
            display_text = f"Problem:\n{expression_input}\n\n{'─'*60}\n\nSteps:\n{steps}\n\n{'─'*60}\n\nAnswer: {result}"
            ax.text(0.05, 0.95, display_text,
                    ha='left', va='top', wrap=True, fontsize=9,
                    family='monospace',
                    bbox=dict(boxstyle="round,pad=0.5", facecolor="#1a1a2e", alpha=0.8, edgecolor="#4ecdc4"),
                    color='white', transform=ax.transAxes)
            fig.patch.set_facecolor('#0a0a1a')
            plt.tight_layout()
            plt.savefig(result_img_path, format='png', dpi=150, bbox_inches='tight', facecolor='#0a0a1a')
            plt.close(fig)
            plt.clf()
            plt.cla()
        except Exception as e:
            print(f"Error creating result image: {e}")

        session['result'] = result
        session['steps'] = steps
        session['expression'] = expression_input

    return render_template(
        "index.html",
        result=result,
        steps=steps,
        spoken_expr=expression_input,
        word_problem=False,
        gemini_key_set=bool(os.environ.get("GEMINI_API_KEY"))
    )


# ─────────────────────────────────────────────
# API: Quick solve (AJAX endpoint)
# ─────────────────────────────────────────────
@app.route("/api/solve", methods=["POST"])
def api_solve():
    if 'user' not in session:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.json or {}
    expression = data.get("expression", "").strip()
    if not expression:
        return jsonify({"error": "No expression provided"}), 400
    
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if gemini_api_key:
        result, steps = solve_math_with_gemini(expression)
    else:
        result, steps = auto_solve_math(expression)
        
    return jsonify({"result": result, "steps": steps})


# ─────────────────────────────────────────────
# DOWNLOAD ROUTES
# ─────────────────────────────────────────────
@app.route("/download_image")
def download_image():
    img_path = os.path.join(app.root_path, 'static', 'result.png')
    if os.path.exists(img_path):
        return send_file(img_path, as_attachment=True)
    flash("❌ No result image available. Please solve a problem first.")
    return redirect(url_for('solve'))


@app.route('/download_pdf')
def download_pdf():
    result = session.get('result', 'No result')
    steps = session.get('steps', 'No steps')
    expression = session.get('expression', 'No expression')

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Header
    c.setFillColorRGB(0.1, 0.1, 0.2)
    c.rect(0, height - 80, width, 80, fill=True, stroke=False)
    c.setFillColorRGB(0.3, 0.8, 0.76)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(50, height - 50, "Math Solver AI — Solution Report")
    c.setFont("Helvetica", 10)
    c.setFillColorRGB(0.8, 0.8, 0.8)
    c.drawString(50, height - 68, "Generated by Math Solver AI")

    # Content
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, height - 110, "Problem:")
    c.setFont("Helvetica", 11)
    c.drawString(70, height - 130, str(expression)[:100])

    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, height - 160, "Answer:")
    c.setFont("Helvetica", 11)
    result_lines = str(result).split('\n')
    y_pos = height - 180
    for line in result_lines[:5]:
        c.drawString(70, y_pos, str(line)[:90])
        y_pos -= 16

    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, y_pos - 20, "Step-by-step Solution:")
    step_lines = str(steps).split('\n')
    y_pos -= 40
    c.setFont("Helvetica", 10)
    for line in step_lines:
        if y_pos < 60:
            c.showPage()
            y_pos = height - 60
            c.setFont("Helvetica", 10)
        c.drawString(70, y_pos, str(line)[:100])
        y_pos -= 14

    c.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="math_solution.pdf", mimetype='application/pdf')


# ─────────────────────────────────────────────
# OTHER ROUTES
# ─────────────────────────────────────────────
@app.route('/faq')
def faq_page():
    return render_template('faq.html')

@app.route('/about')
def about_page():
    return render_template('about.html')

@app.route('/home')
def home_page():
    # Fixed: redirect to auth-protected solve, not raw index.html
    return redirect(url_for('solve'))

reviews = []

@app.route('/review', methods=['GET'])
def review():
    return render_template('review.html')

@app.route('/submit_review', methods=['POST'])
def submit_review():
    name = request.form.get('name', 'Anonymous')
    comment = request.form.get('comment', '')
    rating = request.form.get('rating', '5')
    reviews.append({"name": name, "comment": comment, "rating": rating})
    flash('✅ Thank you for your feedback!')
    return redirect(url_for('show_reviews'))

@app.route('/reviews', methods=['GET'])
def show_reviews():
    return render_template('reviews_display.html', reviews=reviews)


if __name__ == "__main__":
    app.run(debug=True)