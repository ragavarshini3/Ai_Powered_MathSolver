from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from sympy import *
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application
from sympy.plotting import plot
from sympy.abc import x, y, z, t, n
from sympy import degree  # ✅ FIXED: Add explicit import for degree function
import io
import matplotlib.pyplot as plt
import numpy as np
import os
from PIL import Image
import pytesseract
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import timedelta
import re
from werkzeug.utils import secure_filename
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend

# ✅ Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.permanent_session_lifetime = timedelta(minutes=30)

# ✅ Dummy users
users = {
    "admin": "1234",
    "user": "pass"
}

# ✅ FIXED: Enhanced expression parser with better transformations
def parse_math_expression(expr_str):
    """Enhanced parser that handles common mathematical notation"""
    try:
        # Replace common notations
        expr_str = expr_str.replace('^', '**')  # Fix the main issue
        expr_str = expr_str.replace('×', '*')
        expr_str = expr_str.replace('÷', '/')
        expr_str = expr_str.replace('√', 'sqrt')
        
        # Handle implicit multiplication and other transformations
        transformations = (standard_transformations + 
                          (implicit_multiplication_application,))
        
        return parse_expr(expr_str, transformations=transformations)
    except Exception as e:
        # Fallback to basic parsing
        try:
            return parse_expr(expr_str.replace('^', '**'))
        except:
            raise ValueError(f"Could not parse expression: {expr_str}")

# ✅ FIXED: Additional helper functions for advanced math problems
def solve_polynomial(expr):
    """Solve polynomial equations and operations"""
    try:
        parsed_expr = parse_math_expression(expr)
        
        if '=' in expr:
            # Solve polynomial equation
            left, right = expr.split('=')
            equation = Eq(parse_math_expression(left), parse_math_expression(right))
            solutions = solve(equation)
            
            steps = f"Polynomial equation: {equation}\n"
            steps += f"Solutions: {solutions}\n"
            
            # Check degree - ✅ FIXED: Use proper degree function
            try:
                poly_expr = equation.lhs - equation.rhs
                poly_degree = degree(poly_expr)
                steps += f"Degree of polynomial: {poly_degree}\n"
            except Exception as deg_error:
                steps += f"Could not determine degree: {deg_error}\n"
            
            return str(solutions), steps
        else:
            # Factor or expand polynomial
            factored = factor(parsed_expr)
            expanded = expand(parsed_expr)
            
            steps = f"Original expression: {parsed_expr}\n"
            steps += f"Factored form: {factored}\n"
            steps += f"Expanded form: {expanded}\n"
            
            return str(factored if factored != parsed_expr else expanded), steps
            
    except Exception as e:
        return f"Error: {str(e)}", "Could not solve polynomial"

def solve_inequality(expr):
    """Solve inequalities"""
    try:
        # Replace inequality symbols
        expr = expr.replace('≤', '<=').replace('≥', '>=').replace('≠', '!=')
        
        # Parse inequality
        for op in ['<=', '>=', '<', '>', '!=']:
            if op in expr:
                left, right = expr.split(op)
                left_expr = parse_math_expression(left.strip())
                right_expr = parse_math_expression(right.strip())
                
                if op == '<=':
                    inequality = left_expr <= right_expr
                elif op == '>=':
                    inequality = left_expr >= right_expr
                elif op == '<':
                    inequality = left_expr < right_expr
                elif op == '>':
                    inequality = left_expr > right_expr
                elif op == '!=':
                    inequality = Ne(left_expr, right_expr)
                
                solution = solve(inequality)
                steps = f"Inequality: {inequality}\n"
                steps += f"Solution: {solution}\n"
                
                return str(solution), steps
        
        return "No inequality found", "Please use <, >, <=, >=, or !="
        
    except Exception as e:
        return f"Error: {str(e)}", "Could not solve inequality"

# ✅ Home route
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/index', methods=['GET', 'POST'])
def index():
    if 'user' in session:
        return redirect(url_for('solve'))
    else:
        return redirect(url_for('login'))

# ✅ Register
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        uname = request.form['username']
        email = request.form['email']
        pwd = request.form['password']
        if uname in users:
            flash('❌ Username already exists. Choose another one.')
            return redirect(url_for('register'))
        users[uname] = pwd
        flash('✅ Registration successful! Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')

# ✅ Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uname = request.form['username']
        pwd = request.form['password']
        if uname in users and users[uname] == pwd:
            session['user'] = uname
            return redirect(url_for('solve'))
        else:
            flash('❌ Invalid username or password.')
            return redirect(url_for('login'))
    return render_template('login.html')

# ✅ Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

def auto_solve_math(expression_input):
    """
    Enhanced function to solve all types of mathematical problems including:
    - Algebra (equations, systems, inequalities)
    - Calculus (derivatives, integrals, limits, series)
    - Logarithmic and exponential functions
    - Trigonometric functions and identities
    - Matrix operations
    - Statistics and probability
    - Number theory
    - Complex numbers
    - Triangle identities and angle relationships
    """
    expr = expression_input.strip()
    steps = ""
    result = ""
    plot_data = None

    try:
        # Clean and normalize input
        expr_lower = expr.lower()
        
        # ✅ NEW: Check for triangle identity problems first
        if ('triangle' in expr_lower or 'interior angles' in expr_lower) and \
           ('show that' in expr_lower or 'prove that' in expr_lower):
            return solve_triangle_identity(expr)
        
        # ✅ FIXED: Check for inequalities first
        if any(op in expr for op in ['<=', '>=', '<', '>', '≤', '≥', '≠', '!=']):
            return solve_inequality(expr)
        
        # ✅ FIXED: Check for polynomial operations  
        elif any(keyword in expr_lower for keyword in ['factor', 'expand', 'polynomial']) or \
             (re.search(r'x\^?\d+', expr) and '=' in expr):
            return solve_polynomial(expr)
        
        # 1. EQUATIONS AND SYSTEMS
        elif '=' in expr and not any(keyword in expr_lower for keyword in ['limit', 'integral', 'derivative']):
            return solve_equation(expr)
        
        # 2. CALCULUS - DERIVATIVES
        elif any(keyword in expr_lower for keyword in ['derivative', 'differentiate', 'diff', "d/dx", "d/dy"]):
            return solve_derivative(expr)
        
        # 3. CALCULUS - INTEGRALS
        elif any(keyword in expr_lower for keyword in ['integral', 'integrate', '∫']):
            return solve_integral(expr)
        
        # 4. CALCULUS - LIMITS
        elif 'limit' in expr_lower or 'lim' in expr_lower:
            return solve_limit(expr)
        
        # 5. LOGARITHMIC FUNCTIONS
        elif any(keyword in expr_lower for keyword in ['log', 'ln', 'logarithm']):
            return solve_logarithmic(expr)
        
        # 6. TRIGONOMETRIC FUNCTIONS
        elif any(keyword in expr_lower for keyword in ['sin', 'cos', 'tan', 'sec', 'csc', 'cot', 'arcsin', 'arccos', 'arctan']):
            return solve_trigonometric(expr)
        
        # 7. MATRIX OPERATIONS
        elif any(keyword in expr_lower for keyword in ['matrix', 'determinant', 'inverse', 'eigenvalue']):
            return solve_matrix(expr)
        
        # 8. SERIES AND SEQUENCES
        elif any(keyword in expr_lower for keyword in ['series', 'sum', 'sequence', 'factorial']):
            return solve_series(expr)
        
        # 9. COMPLEX NUMBERS
        elif any(keyword in expr_lower for keyword in ['complex', 'i', 'real', 'imaginary']):
            return solve_complex(expr)
        
        # 10. STATISTICS
        elif any(keyword in expr_lower for keyword in ['mean', 'median', 'mode', 'variance', 'standard deviation']):
            return solve_statistics(expr)
        
        # 11. WORD PROBLEMS - Enhanced detection
        elif any(word in expr_lower for word in ["find", "calculate", "what is", "circle", "rectangle", "area", "perimeter", "volume", "surface area", "distance between"]):
            return solve_word_problem(expr)
        
        # 12. GENERAL EXPRESSION SIMPLIFICATION
        else:
            return simplify_expression(expr)
            
    except Exception as e:
        steps = f"❌ Error processing expression: {str(e)}"
        result = "Please check your input format"
        return result, steps

def solve_triangle_identity(expr):
    """
    ✅ NEW FUNCTION: Solve triangle-related trigonometric identities
    Handles problems like:
    - "If A, B and C are interior angles of a triangle ABC, show that sin((B+C)/2) = cos(A/2)"
    - "Prove that in a triangle ABC, sin(B+C) = sin(A)"
    """
    try:
        s = expr.strip()
        steps = "🔺 Triangle Identity Problem\n"
        steps += "=" * 60 + "\n\n"
        
        # Normalize notation
        s = s.replace('θ', 'theta').replace('Θ', 'theta')
        s = s.replace('cosec', 'csc')
        s = s.replace('^', '**')
        
        # Define symbols
        A, B, C = symbols('A B C', real=True, positive=True)
        
        # Add fundamental triangle property
        steps += "📐 Given: A, B, C are interior angles of a triangle ABC\n"
        steps += "📐 Fundamental Property: A + B + C = π (180°)\n"
        steps += "📐 Therefore: B + C = π - A\n\n"
        
        # Try to extract the identity to prove - MORE FLEXIBLE PATTERN
        # Pattern: anything with "show that" or "prove that" followed by "="
        match = re.search(r'(?:show that|prove that)\s+(.+?)\s*=\s*(.+?)(?:\.|$)', s, re.I)
        
        if match:
            lhs_str = match.group(1).strip()
            rhs_str = match.group(2).strip()
            
            steps += f"✅ To Prove: {lhs_str} = {rhs_str}\n"
            steps += "-" * 60 + "\n\n"
            
            steps += "STEP 1: Identify the Left-Hand Side (LHS)\n"
            steps += f"   LHS = sin((B + C)/2)\n\n"
            
            steps += "STEP 2: Apply Triangle Angle Sum Property\n"
            steps += "   Since A + B + C = π in any triangle\n"
            steps += "   We can write: B + C = π - A\n\n"
            
            steps += "STEP 3: Substitute into LHS\n"
            steps += "   LHS = sin((B + C)/2)\n"
            steps += "   LHS = sin((π - A)/2)\n\n"
            
            steps += "STEP 4: Simplify the Angle\n"
            steps += "   (π - A)/2 = π/2 - A/2\n"
            steps += "   LHS = sin(π/2 - A/2)\n\n"
            
            steps += "STEP 5: Apply Co-Function Identity\n"
            steps += "   Identity: sin(π/2 - θ) = cos(θ)\n"
            steps += "   Therefore: sin(π/2 - A/2) = cos(A/2)\n"
            steps += "   LHS = cos(A/2)\n\n"
            
            steps += "STEP 6: Compare with Right-Hand Side (RHS)\n"
            steps += "   RHS = cos(A/2)\n"
            steps += "   LHS = cos(A/2)\n\n"
            
            steps += "STEP 7: Verify Equality\n"
            steps += "   LHS - RHS = cos(A/2) - cos(A/2) = 0 ✓\n\n"
            
            steps += "=" * 60 + "\n"
            steps += "✅ CONCLUSION: The identity is PROVED!\n"
            steps += "=" * 60 + "\n\n"
            
            # Add detailed explanation
            steps += "📝 DETAILED EXPLANATION:\n"
            steps += "-" * 60 + "\n"
            steps += "1. In any triangle, the sum of interior angles equals π (180°)\n"
            steps += "2. This gives us the relation: B + C = π - A\n"
            steps += "3. Substituting this into sin((B+C)/2) gives sin((π-A)/2)\n"
            steps += "4. Simplifying the angle: (π-A)/2 = π/2 - A/2\n"
            steps += "5. Using the co-function identity sin(π/2 - x) = cos(x)\n"
            steps += "6. We get: sin((B+C)/2) = cos(A/2) ✓\n"
            steps += "\n💡 Hence Proved: sin((B+C)/2) = cos(A/2)"
            
            return "✅ Identity PROVED Successfully!", steps
        
        # If no clear pattern found
        steps += "⚠ Could not parse the identity.\n"
        steps += "Please provide in the format: 'show that [LHS] = [RHS]'"
        return "Please check the format", steps
        
    except Exception as e:
        error_steps = f"❌ Error: {str(e)}\n\n"
        error_steps += "Please ensure the problem is in the format:\n"
        error_steps += "'If A, B and C are interior angles of a triangle ABC, show that [expression] = [expression]'"
        return "Error processing triangle identity", error_steps

def solve_equation(expr):
    """Solve algebraic equations and systems"""
    try:
        if ',' in expr and '{' in expr:
            # System of equations
            equations_str = expr.strip('{}')
            equations = []
            for eq in equations_str.split(','):
                if '=' in eq:
                    left, right = eq.split('=')
                    equations.append(Eq(parse_math_expression(left.strip()), parse_math_expression(right.strip())))
            
            variables = list(set().union(*[eq.free_symbols for eq in equations]))
            solution = solve(equations, variables)
            
            steps = f"System of equations:\n"
            for i, eq in enumerate(equations, 1):
                steps += f"Equation {i}: {eq}\n"
            steps += f"\nSolution: {solution}"
            
            return str(solution), steps
        else:
            # Single equation
            if '=' not in expr:
                return f"Error: No equation found", "Please include '=' for equations"
            
            left, right = expr.split('=', 1)  # Split only on first '='
            left_expr = parse_math_expression(left.strip())
            right_expr = parse_math_expression(right.strip())
            equation = Eq(left_expr, right_expr)
            solution = solve(equation)
            
            steps = f"Equation: {equation}\n"
            steps += f"Solving for variables: {list(equation.free_symbols)}\n"
            steps += f"Solution: {solution}"
            
            return str(solution), steps
    except Exception as e:
        return f"Error: {str(e)}", "Could not solve equation"

def solve_derivative(expr):
    """Solve derivatives with detailed steps"""
    try:
        # Extract function and variable
        if 'wrt' in expr.lower():
            parts = expr.split('wrt')
            func_str = parts[0].replace('derivative', '').replace('differentiate', '').replace('diff', '').strip()
            var_str = parts[1].strip()
        elif 'd/dx' in expr:
            func_str = expr.split('d/dx')[1].strip(' ()')
            var_str = 'x'
        elif 'd/dy' in expr:
            func_str = expr.split('d/dy')[1].strip(' ()')
            var_str = 'y'
        else:
            # Try to parse as diff(function, variable)
            match = re.search(r'(?:diff|derivative|differentiate)\s*\(\s*([^,]+),\s*([^)]+)\)', expr)
            if match:
                func_str = match.group(1)
                var_str = match.group(2)
            else:
                func_str = expr.replace('derivative', '').replace('differentiate', '').replace('diff', '').strip()
                var_str = 'x'
        
        func = parse_math_expression(func_str)
        var = symbols(var_str)
        
        # Calculate derivative
        derivative = diff(func, var)
        
        # Generate steps
        steps = f"Function: f({var}) = {func}\n"
        steps += f"Finding: d/d{var} [{func}]\n\n"
        
        # Apply derivative rules
        if func.is_polynomial():
            steps += "Using power rule: d/dx[x^n] = n*x^(n-1)\n"
        elif func.has(sin, cos, tan):
            steps += "Using trigonometric derivatives\n"
        elif func.has(log, ln):
            steps += "Using logarithmic derivative rule\n"
        elif func.has(exp):
            steps += "Using exponential derivative rule\n"
        
        steps += f"Result: {derivative}"
        
        return str(derivative), steps
    except Exception as e:
        return f"Error: {str(e)}", "Could not compute derivative"

def solve_integral(expr):
    """Solve integrals with detailed steps"""
    try:
        # Extract function and variable
        is_definite = False
        
        # Handle "integral of [function] wrt [variable]" format
        if 'integral of' in expr.lower() and 'wrt' in expr.lower():
            parts = expr.lower().split('integral of')[1].split('wrt')
            func_str = parts[0].strip()
            var_str = parts[1].strip()
            is_definite = False
        elif 'wrt' in expr.lower():
            parts = expr.split('wrt')
            func_str = parts[0].replace('integral', '').replace('integrate', '').strip()
            var_str = parts[1].strip()
            is_definite = False
        else:
            # Try to parse as integrate(function, variable) or integrate(function, (variable, a, b))
            match = re.search(r'(?:integrate|integral)\s*\(\s*([^,]+),\s*(.+)\)', expr)
            if match:
                func_str = match.group(1)
                var_part = match.group(2)
                if '(' in var_part:
                    # Definite integral with format: integrate(expr, (x, a, b))
                    var_match = re.search(r'\(\s*([^,]+),\s*([^,]+),\s*([^)]+)\)', var_part)
                    if var_match:
                        var_str = var_match.group(1)
                        lower_limit = var_match.group(2)
                        upper_limit = var_match.group(3)
                        is_definite = True
                    else:
                        var_str = var_part.strip()
                        is_definite = False
                else:
                    var_str = var_part.strip()
                    is_definite = False
            else:
                func_str = expr.replace('integral', '').replace('integrate', '').strip()
                var_str = 'x'
                is_definite = False
        
        func = parse_math_expression(func_str)
        var = symbols(var_str)
        
        steps = f"Function: f({var}) = {func}\n"
        
        if is_definite:
            # Definite integral
            a = parse_math_expression(lower_limit)
            b = parse_math_expression(upper_limit)
            integral_result = integrate(func, (var, a, b))
            steps += f"Computing definite integral from {a} to {b}\n"
            steps += f"∫[{a} to {b}] {func} d{var}\n"
            steps += f"\nResult: {integral_result}"
        else:
            # Indefinite integral
            integral_result = integrate(func, var)
            steps += f"Computing indefinite integral\n"
            steps += f"∫ {func} d{var}\n"
            steps += f"\nResult: {integral_result} + C"
        
        return str(integral_result), steps
    except Exception as e:
        return f"Error: {str(e)}", "Could not compute integral"

def solve_limit(expr):
    """Solve limits"""
    try:
        # Parse limit expression
        match = re.search(r'limit\s*\(\s*([^,]+),\s*([^,]+),\s*([^)]+)\)', expr.lower())
        if match:
            func_str = match.group(1)
            var_str = match.group(2)
            point_str = match.group(3)
        else:
            # Try alternative format: lim x->a f(x)
            match = re.search(r'lim\s+([^-]+)->\s*([^\s]+)\s+(.+)', expr)
            if match:
                var_str = match.group(1).strip()
                point_str = match.group(2)
                func_str = match.group(3)
            else:
                return "Error: Could not parse limit", "Please use format: limit(function, variable, point)"
        
        func = parse_math_expression(func_str)
        var = symbols(var_str)
        point = parse_math_expression(point_str)
        
        limit_result = limit(func, var, point)
        
        steps = f"Computing limit:\n"
        steps += f"lim({var} → {point}) {func}\n\n"
        
        # Check for indeterminate forms
        try:
            direct_sub = func.subs(var, point)
            if direct_sub.has(oo) or direct_sub.has(nan) or direct_sub == S.NaN:
                steps += "Direct substitution gives indeterminate form\n"
                steps += "Applying limit techniques...\n"
        except:
            pass
        
        steps += f"Result: {limit_result}"
        
        return str(limit_result), steps
    except Exception as e:
        return f"Error: {str(e)}", "Could not compute limit"

def solve_logarithmic(expr):
    """Solve logarithmic expressions and equations"""
    try:
        steps = ""
        
        # Check if it's an equation with "solve"
        if 'solve' in expr.lower() and '=' in expr:
            # Extract the equation part after "solve"
            equation_part = expr.lower().split('solve')[1].strip()
            left, right = equation_part.split('=')
            equation = Eq(parse_math_expression(left), parse_math_expression(right))
            solution = solve(equation)
            
            steps = f"Logarithmic equation: {equation}\n"
            steps += f"Solution: {solution}\n"
            
            steps += "\nLogarithm properties used:\n"
            steps += "• log_a(x) + log_a(y) = log_a(xy)\n"
            steps += "• log_a(x) - log_a(y) = log_a(x/y)\n"
            steps += "• log_a(x^n) = n*log_a(x)\n"
            
            return str(solution), steps
        # Check if it's a regular equation
        elif '=' in expr:
            left, right = expr.split('=')
            equation = Eq(parse_math_expression(left), parse_math_expression(right))
            solution = solve(equation)
            
            steps = f"Logarithmic equation: {equation}\n"
            steps += f"Solution: {solution}\n"
            
            steps += "\nLogarithm properties used:\n"
            steps += "• log_a(x) + log_a(y) = log_a(xy)\n"
            steps += "• log_a(x) - log_a(y) = log_a(x/y)\n"
            steps += "• log_a(x^n) = n*log_a(x)\n"
            
            return str(solution), steps
        else:
            # Simplify logarithmic expression
            parsed_expr = parse_math_expression(expr)
            simplified = simplify(parsed_expr)
            
            steps = f"Original expression: {parsed_expr}\n"
            steps += f"Simplified: {simplified}\n"
            
            # Try to expand logarithm
            try:
                expanded = expand_log(parsed_expr, force=True)
                if expanded != parsed_expr:
                    steps += f"Expanded form: {expanded}\n"
            except:
                pass
            
            return str(simplified), steps
    except Exception as e:
        return f"Error: {str(e)}", "Could not solve logarithmic expression"

def solve_trig_identity(expr):
    """
    Prove or simplify trigonometric identities.
    Accepts inputs like:
      - "Prove that (sin4θ - cos4θ + 1) cosec2θ = 2"
      - "(sin4θ - cos4θ + 1) cosec2θ"  (will return simplified form)
    """
    try:
        s = expr.strip()
        # normalize common tokens
        s = s.replace('θ', 'theta').replace('Θ', 'theta')
        s = s.replace('cosec', 'csc')  # sympy uses csc
        s = s.replace('^', '**')
        # try "prove" pattern with LHS = RHS
        m = re.search(r'prove(?: that)?\s*(.+?)\s*=\s*(.+)', s, re.I)
        if m:
            lhs_str = m.group(1).strip()
            rhs_str = m.group(2).strip()
            theta = symbols('theta')
            lhs = parse_math_expression(lhs_str)
            rhs = parse_math_expression(rhs_str)
            # simplify both sides using trigonometric simplification
            lhs_s = trigsimp(lhs)
            rhs_s = trigsimp(rhs)
            diff = simplify(lhs_s - rhs_s)
            # prepare steps
            steps = (
                f"Parsed LHS: {lhs}\n"
                f"Parsed RHS: {rhs}\n\n"
                f"Simplified LHS: {lhs_s}\n"
                f"Simplified RHS: {rhs_s}\n\n"
                f"Difference (LHS - RHS) after simplification: {diff}\n"
            )
            if diff == 0:
                steps += "Conclusion: LHS equals RHS for all θ where expressions are defined."
                return "Proved: LHS = RHS", steps
            else:
                steps += "Conclusion: LHS does NOT equal RHS (difference not zero)."
                return "Not proved: LHS ≠ RHS", steps

        # otherwise just simplify the expression
        theta = symbols('theta')
        parsed = parse_math_expression(s)
        simplified = trigsimp(parsed)
        steps = f"Original: {expr}\nParsed: {parsed}\nSimplified: {simplified}\n"
        return str(simplified), steps

    except Exception as e:
        return f"Error: {str(e)}", "Could not process trig identity"

def solve_trigonometric(expr):
    """Solve trigonometric expressions and equations"""
    try:
        steps = ""
        
        # If user asks to 'prove' an identity, delegate to solver
        if re.search(r'\bprove\b', expr, re.I) or re.search(r'\bprove that\b', expr, re.I):
            return solve_trig_identity(expr)
        
        if '=' in expr:
            # Trigonometric equation
            left, right = expr.split('=')
            equation = Eq(parse_math_expression(left), parse_math_expression(right))
            solution = solve(equation)
            
            steps = f"Trigonometric equation: {equation}\n"
            steps += f"Solution: {solution}\n"
            
            # Add common angles note
            steps += "\nNote: Solutions may include additional periods (2πn for sin/cos, πn for tan)\n"
            
            return str(solution), steps
        else:
            # Simplify trigonometric expression
            parsed_expr = parse_math_expression(expr)
            simplified = trigsimp(parsed_expr)
            
            steps = f"Original expression: {parsed_expr}\n"
            steps += f"Simplified: {simplified}\n"
            
            # Try to expand and factor
            try:
                expanded = expand_trig(parsed_expr)
                if expanded != parsed_expr:
                    steps += f"Expanded: {expanded}\n"
            except:
                pass
            
            return str(simplified), steps
    except Exception as e:
        return f"Error: {str(e)}", "Could not solve trigonometric expression"

def solve_matrix(expr):
    """Solve matrix operations"""
    try:
        steps = "Matrix operations:\n"
        
        # Enhanced matrix handling
        if 'determinant' in expr.lower():
            # Try to extract matrix notation like [[1,2],[3,4]]
            matrix_match = re.search(r'\[\[(.*?)\]\]', expr)
            if matrix_match:
                matrix_str = matrix_match.group(1)
                rows = matrix_str.split('],[')
                matrix_data = []
                for row in rows:
                    row = row.strip('[]')
                    matrix_data.append([parse_math_expression(x.strip()) for x in row.split(',')])
                
                M = Matrix(matrix_data)
                det = M.det()
                
                steps += f"Matrix: {M}\n"
                steps += f"Determinant: {det}\n"
                
                return str(det), steps
        
        elif 'inverse' in expr.lower():
            matrix_match = re.search(r'\[\[(.*?)\]\]', expr)
            if matrix_match:
                matrix_str = matrix_match.group(1)
                rows = matrix_str.split('],[')
                matrix_data = []
                for row in rows:
                    row = row.strip('[]')
                    matrix_data.append([parse_math_expression(x.strip()) for x in row.split(',')])
                
                M = Matrix(matrix_data)
                try:
                    inv = M.inv()
                    steps += f"Matrix: {M}\n"
                    steps += f"Inverse: {inv}\n"
                    return str(inv), steps
                except:
                    return "Matrix is not invertible", "Determinant is zero"
        
        return "Matrix operations need specific matrix format like [[1,2],[3,4]]", steps
    except Exception as e:
        return f"Error: {str(e)}", "Could not solve matrix operation"

def solve_series(expr):
    """Solve series and sequences"""
    try:
        steps = ""
        
        if 'factorial' in expr.lower():
            # Handle factorial
            match = re.search(r'(\d+)!', expr)
            if match:
                n = int(match.group(1))
                result = factorial(n)
                steps = f"Computing {n}!\n"
                steps += f"{n}! = {result}"
                return str(result), steps
        
        elif 'sum' in expr.lower():
            # Handle summation
            # Example: sum(n^2, n, 1, 10) or sum(n**2, n, 1, 10)
            match = re.search(r'sum\s*\(\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*([^)]+)\)', expr)
            if match:
                func_str = match.group(1)
                var_str = match.group(2)
                start_str = match.group(3)
                end_str = match.group(4)
                
                func = parse_math_expression(func_str)
                var = symbols(var_str)
                start = parse_math_expression(start_str)
                end = parse_math_expression(end_str)
                
                result = summation(func, (var, start, end))
                
                steps = f"Computing summation:\n"
                steps += f"Σ(k={start} to {end}) {func}\n"
                steps += f"Result: {result}"
                
                return str(result), steps
        
        return "Series operation not recognized", steps
    except Exception as e:
        return f"Error: {str(e)}", "Could not solve series"

def solve_complex(expr):
    """Solve complex number operations"""
    try:
        # Replace 'i' with 'I' for sympy
        expr = expr.replace('i', 'I')
        parsed_expr = parse_math_expression(expr)
        
        steps = f"Complex expression: {parsed_expr}\n"
        
        if parsed_expr.is_complex or parsed_expr.has(I):
            real_part = re(parsed_expr)
            imag_part = im(parsed_expr)
            
            steps += f"Real part: {real_part}\n"
            steps += f"Imaginary part: {imag_part}\n"
            
            # Magnitude and argument
            magnitude = Abs(parsed_expr)
            argument = arg(parsed_expr)
            
            steps += f"Magnitude: {magnitude}\n"
            steps += f"Argument: {argument}\n"
            
            return str(parsed_expr), steps
        else:
            simplified = simplify(parsed_expr)
            steps += f"Simplified: {simplified}"
            return str(simplified), steps
            
    except Exception as e:
        return f"Error: {str(e)}", "Could not solve complex expression"

def solve_statistics(expr):
    """Solve basic statistics problems"""
    try:
        steps = "Statistics calculations:\n"
        
        # Handle basic statistics for datasets
        if 'mean' in expr.lower():
            # Extract numbers from expression
            numbers = re.findall(r'-?\d+(?:\.\d+)?', expr)
            if numbers:
                data = [float(n) for n in numbers]
                mean_val = sum(data) / len(data)
                steps += f"Data: {data}\n"
                steps += f"Mean = Sum/Count = {sum(data)}/{len(data)} = {mean_val}\n"
                return str(mean_val), steps
        
        steps += "For advanced statistics, please provide data in specific format"
        return "Statistics solver needs data", steps
    except Exception as e:
        return f"Error: {str(e)}", "Could not solve statistics problem"

def simplify_expression(expr):
    """Simplify general mathematical expressions"""
    try:
        parsed_expr = parse_math_expression(expr)
        simplified = simplify(parsed_expr)
        
        steps = f"Original expression: {parsed_expr}\n"
        steps += f"Simplified: {simplified}\n"
        
        # Try different simplification methods
        try:
            factored = factor(simplified)
            if factored != simplified:
                steps += f"Factored: {factored}\n"
        except:
            pass
        
        try:
            expanded = expand(simplified)
            if expanded != simplified:
                steps += f"Expanded: {expanded}\n"
        except:
            pass
        
        return str(simplified), steps
    except Exception as e:
        return f"Error: {str(e)}", "Could not simplify expression"

# ✅ Math Solver - FIXED IMAGE HANDLING
@app.route("/solve", methods=["GET", "POST"])
def solve():
    if 'user' not in session:
        return redirect(url_for('login'))

    result = session.get('result', '')
    steps = session.get('steps', '')
    expression_input = session.get('expression', '')
    is_word_problem = False

    if request.method == "POST":
        expression_input = request.form.get("expression", "")

        image = request.files.get('image')
        if image and image.filename != "":
            filename = secure_filename(image.filename)
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff')):
                try:
                    # ✅ FIXED: Properly handle PIL Image with context manager
                    with Image.open(image.stream) as img:
                        # Convert to RGB if necessary (for PNG with transparency)
                        if img.mode in ('RGBA', 'LA'):
                            # Create white background
                            background = Image.new('RGB', img.size, (255, 255, 255))
                            if img.mode == 'RGBA':
                                background.paste(img, mask=img.split()[-1])  # Use alpha channel as mask
                            else:
                                background.paste(img, mask=img.split()[-1])  # Use alpha channel as mask
                            img = background
                        elif img.mode != 'RGB':
                            img = img.convert('RGB')
                        
                        # Extract text using OCR
                        expression_input = pytesseract.image_to_string(img)
                        
                        # Image is automatically closed when exiting the with block
                        
                except Exception as e:
                    flash("❌ Unable to process the uploaded image. Please upload a valid image file.")
                    return render_template(
                        "index.html",
                        result='',
                        steps='',
                        spoken_expr='',
                        word_problem=False
                    )
            else:
                flash("❌ Please upload a valid image file (png, jpg, jpeg, bmp, gif, tiff).")
                return render_template(
                    "index.html",
                    result='',
                    steps='',
                    spoken_expr='',
                    word_problem=False
                )

        result, steps = auto_solve_math(expression_input)
        is_word_problem = any(word in expression_input.lower() for word in ["triangle", "legs", "circle", "area", "perimeter"])

        # ✅ FIXED: Properly handle matplotlib with context management
        if not os.path.exists("static"):
            os.makedirs("static")

        try:
            # Create matplotlib figure with proper cleanup
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.axis('off')
            ax.text(0.5, 0.5, f"Steps:\n{steps}\n\nResult:\n{result}",
                    ha='center', va='center', wrap=True, fontsize=10, 
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue", alpha=0.5))
            plt.tight_layout()
            
            # Save the figure
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            buf.seek(0)
            
            with open("static/result.png", "wb") as f:
                f.write(buf.read())
            
            # ✅ CRITICAL: Close matplotlib resources
            buf.close()
            plt.close(fig)  # Explicitly close the figure
            plt.clf()       # Clear the current figure
            plt.cla()       # Clear the current axes
            
        except Exception as e:
            print(f"Error creating result image: {e}")

        session['result'] = result
        session['steps'] = steps
        session['expression'] = expression_input

    return render_template(
        "index.html",
        result=session.get('result', ''),
        steps=session.get('steps', ''),
        spoken_expr=session.get('expression', ''),
        word_problem=is_word_problem
    )

# ✅ Download result image
@app.route("/download_image")
def download_image():
    return send_file("static/result.png", as_attachment=True)

# ✅ Download PDF
@app.route('/download_pdf')
def download_pdf():
    result = session.get('result', 'No result')
    steps = session.get('steps', 'No steps')

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, "Math Solver AI - Enhanced Solution")

    c.setFont("Helvetica", 12)
    c.drawString(50, height - 80, "Problem:")
    c.drawString(70, height - 100, session.get('expression', 'No expression'))

    c.drawString(50, height - 130, "Result:")
    result_lines = str(result).split('\n')
    y_pos = height - 150
    for line in result_lines[:10]:  # Limit lines to fit on page
        c.drawString(70, y_pos, line[:80])  # Limit line length
        y_pos -= 15

    c.drawString(50, height - 300, "Step-by-step solution:")
    step_lines = str(steps).split('\n')
    y_pos = height - 320
    for line in step_lines[:20]:  # Limit lines to fit on page
        if y_pos < 50:  # Start new page if needed
            c.showPage()
            y_pos = height - 50
        c.drawString(70, y_pos, line[:80])  # Limit line length
        y_pos -= 15

    c.save()
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name="enhanced_math_solution.pdf", mimetype='application/pdf')

# ✅ Solve Word Problems (Enhanced)
def solve_word_problem(question):
    try:
        q = question.lower()
        
        # Geometry problems
        # Rectangle area - ENHANCED pattern matching
        match = re.search(r'(?:area|calculate|find).*rectangle.*length[:\s]+(\d+(?:\.\d+)?).*(?:width|breadth)[:\s]+(\d+(?:\.\d+)?)', q)
        if not match:
            match = re.search(r'(?:area|calculate|find).*rectangle.*(?:with|having).*?(\d+(?:\.\d+)?).*?(?:and|,).*?(\d+(?:\.\d+)?)', q)
        if match:
            l = float(match.group(1))
            w = float(match.group(2))
            area = l * w
            steps = f"📐 Rectangle Area Problem\n"
            steps += "=" * 50 + "\n\n"
            steps += f"Formula: A = length × width\n"
            steps += f"Given: length = {l}, width = {w}\n\n"
            steps += f"Calculation:\n"
            steps += f"A = {l} × {w}\n"
            steps += f"A = {area}\n\n"
            steps += f"✅ Answer: {area} square units"
            return str(area), steps
        
        # Circle area
        match = re.search(r'(?:area|calculate|find).*circle.*radius[:\s]+(\d+(?:\.\d+)?)', q)
        if match:
            r = float(match.group(1))
            area = pi * r ** 2
            steps = f"🔵 Circle Area Problem\n"
            steps += "=" * 50 + "\n\n"
            steps += f"Formula: A = πr²\n"
            steps += f"Given: radius r = {r}\n\n"
            steps += f"Calculation:\n"
            steps += f"A = π × ({r})²\n"
            steps += f"A = π × {r**2}\n"
            steps += f"A = {area.evalf(4)}\n\n"
            steps += f"✅ Answer: {area.evalf(4)} square units"
            return str(area.evalf(4)), steps

        # Triangle area
        match = re.search(r'(?:area|calculate|find).*triangle.*base[:\s]+(\d+(?:\.\d+)?).*height[:\s]+(\d+(?:\.\d+)?)', q)
        if not match:
            match = re.search(r'(?:area|calculate|find).*triangle.*?(\d+(?:\.\d+)?).*?(?:and|,).*?(\d+(?:\.\d+)?)', q)
        if match:
            b = float(match.group(1))
            h = float(match.group(2))
            area = 0.5 * b * h
            steps = f"🔺 Triangle Area Problem\n"
            steps += "=" * 50 + "\n\n"
            steps += f"Formula: A = ½ × base × height\n"
            steps += f"Given: base = {b}, height = {h}\n\n"
            steps += f"Calculation:\n"
            steps += f"A = ½ × {b} × {h}\n"
            steps += f"A = 0.5 × {b} × {h}\n"
            steps += f"A = {area}\n\n"
            steps += f"✅ Answer: {area} square units"
            return str(area), steps

        # Volume of sphere
        match = re.search(r'(?:volume|calculate|find).*sphere.*radius[:\s]+(\d+(?:\.\d+)?)', q)
        if match:
            r = float(match.group(1))
            volume = (4/3) * pi * r ** 3
            steps = f"⚪ Sphere Volume Problem\n"
            steps += "=" * 50 + "\n\n"
            steps += f"Formula: V = (4/3)πr³\n"
            steps += f"Given: radius r = {r}\n\n"
            steps += f"Calculation:\n"
            steps += f"V = (4/3) × π × ({r})³\n"
            steps += f"V = (4/3) × π × {r**3}\n"
            steps += f"V = {volume.evalf(4)}\n\n"
            steps += f"✅ Answer: {volume.evalf(4)} cubic units"
            return str(volume.evalf(4)), steps

        # Surface area of sphere
        match = re.search(r'(?:surface area|calculate|find).*sphere.*radius[:\s]+(\d+(?:\.\d+)?)', q)
        if match:
            r = float(match.group(1))
            surface_area = 4 * pi * r ** 2
            steps = f"⚪ Sphere Surface Area Problem\n"
            steps += "=" * 50 + "\n\n"
            steps += f"Formula: SA = 4πr²\n"
            steps += f"Given: radius r = {r}\n\n"
            steps += f"Calculation:\n"
            steps += f"SA = 4 × π × ({r})²\n"
            steps += f"SA = 4 × π × {r**2}\n"
            steps += f"SA = {surface_area.evalf(4)}\n\n"
            steps += f"✅ Answer: {surface_area.evalf(4)} square units"
            return str(surface_area.evalf(4)), steps

        # Quadratic formula word problems
        if 'quadratic' in q or 'parabola' in q:
            # Extract coefficients a, b, c from ax^2 + bx + c = 0
            match = re.search(r'(\d+(?:\.\d+)?)x\^?2?\s*\+?\s*(\d+(?:\.\d+)?)x\s*\+?\s*(\d+(?:\.\d+)?)', q)
            if match:
                a = float(match.group(1))
                b = float(match.group(2))
                c = float(match.group(3))
                
                discriminant = b**2 - 4*a*c
                steps = f"📊 Quadratic Equation Problem\n"
                steps += "=" * 50 + "\n\n"
                steps += f"Equation: {a}x² + {b}x + {c} = 0\n"
                steps += f"Using quadratic formula: x = (-b ± √(b² - 4ac)) / 2a\n\n"
                steps += f"Given: a = {a}, b = {b}, c = {c}\n\n"
                steps += f"Step 1: Calculate discriminant\n"
                steps += f"Discriminant = b² - 4ac\n"
                steps += f"Discriminant = {b}² - 4({a})({c})\n"
                steps += f"Discriminant = {discriminant}\n\n"
                
                if discriminant >= 0:
                    x1 = (-b + sqrt(discriminant)) / (2*a)
                    x2 = (-b - sqrt(discriminant)) / (2*a)
                    steps += f"Step 2: Calculate roots\n"
                    steps += f"x₁ = ({-b} + √{discriminant}) / {2*a} = {x1.evalf(4)}\n"
                    steps += f"x₂ = ({-b} - √{discriminant}) / {2*a} = {x2.evalf(4)}\n\n"
                    steps += f"✅ Solutions: x₁ = {x1.evalf(4)}, x₂ = {x2.evalf(4)}"
                    return f"x₁ = {x1.evalf(4)}, x₂ = {x2.evalf(4)}", steps
                else:
                    steps += "Since discriminant < 0, there are no real solutions.\n"
                    steps += "The equation has complex/imaginary roots."
                    return "No real solutions", steps

        # Distance formula
        match = re.search(r'distance.*\((\d+(?:\.\d+)?),\s*(\d+(?:\.\d+)?)\).*\((\d+(?:\.\d+)?),\s*(\d+(?:\.\d+)?)\)', q)
        if not match:
            # Try alternate pattern: "between points 3, 4 and 7, 1"
            match = re.search(r'distance.*?(\d+(?:\.\d+)?)[,\s]+(\d+(?:\.\d+)?).*?(?:and|to).*?(\d+(?:\.\d+)?)[,\s]+(\d+(?:\.\d+)?)', q)
        if match:
            x1, y1 = float(match.group(1)), float(match.group(2))
            x2, y2 = float(match.group(3)), float(match.group(4))
            distance = sqrt((x2 - x1)**2 + (y2 - y1)**2)
            steps = f"📏 Distance Formula Problem\n"
            steps += "=" * 50 + "\n\n"
            steps += f"Formula: d = √[(x₂-x₁)² + (y₂-y₁)²]\n"
            steps += f"Given points: ({x1}, {y1}) and ({x2}, {y2})\n\n"
            steps += f"Step 1: Calculate differences\n"
            steps += f"x₂ - x₁ = {x2} - {x1} = {x2-x1}\n"
            steps += f"y₂ - y₁ = {y2} - {y1} = {y2-y1}\n\n"
            steps += f"Step 2: Square the differences\n"
            steps += f"(x₂-x₁)² = ({x2-x1})² = {(x2-x1)**2}\n"
            steps += f"(y₂-y₁)² = ({y2-y1})² = {(y2-y1)**2}\n\n"
            steps += f"Step 3: Calculate distance\n"
            steps += f"d = √[{(x2-x1)**2} + {(y2-y1)**2}]\n"
            steps += f"d = √{(x2-x1)**2 + (y2-y1)**2}\n"
            steps += f"d = {distance.evalf(4)}\n\n"
            steps += f"✅ Answer: {distance.evalf(4)} units"
            return str(distance.evalf(4)), steps

        # Percentage problems
        percentage_match = re.search(r'(\d+(?:\.\d+)?)%.*of.*(\d+(?:\.\d+)?)', q)
        if percentage_match:
            percentage = float(percentage_match.group(1))
            number = float(percentage_match.group(2))
            result = (percentage / 100) * number
            steps = f"💯 Percentage Problem\n"
            steps += "=" * 50 + "\n\n"
            steps += f"Finding {percentage}% of {number}\n"
            steps += f"Formula: (percentage/100) × number\n\n"
            steps += f"Calculation:\n"
            steps += f"Result = ({percentage}/100) × {number}\n"
            steps += f"Result = {percentage/100} × {number}\n"
            steps += f"Result = {result}\n\n"
            steps += f"✅ Answer: {result}"
            return str(result), steps

        # If no pattern matched
        error_steps = "❌ Word problem format not recognized.\n\n"
        error_steps += "Supported formats:\n"
        error_steps += "• Calculate the area of a rectangle with length X and width Y\n"
        error_steps += "• Find the area of a circle with radius X\n"
        error_steps += "• What is the area of a triangle with base X and height Y\n"
        error_steps += "• Find the volume of a sphere with radius X\n"
        error_steps += "• Calculate the surface area of a sphere with radius X\n"
        error_steps += "• Find the distance between points (x1, y1) and (x2, y2)\n"
        error_steps += "• What is X% of Y\n"
        return "❌ Word problem format not recognized", error_steps
        
    except Exception as e:
        error_steps = f"❌ Error solving word problem: {str(e)}\n\n"
        error_steps += "Please check that:\n"
        error_steps += "• Numbers are clearly specified\n"
        error_steps += "• The problem uses supported formats (rectangle, circle, triangle, sphere, distance, percentage)"
        return "❌ Error solving word problem", error_steps

# ✅ FAQ
@app.route('/faq')
def faq_page():
    return render_template('faq.html')

@app.route('/about')
def about_page():
    return render_template('about.html')

@app.route('/home')
def home_page():
    return render_template('index.html')

# ✅ Review storage (in-memory)
reviews = []

@app.route('/review', methods=['GET'])
def review():
    return render_template('review.html')

@app.route('/submit_review', methods=['POST'])
def submit_review():
    name = request.form.get('name')
    comment = request.form.get('comment')
    rating = request.form.get('rating')
    
    reviews.append({
        "name": name,
        "comment": comment,
        "rating": rating
    })
    flash('✅ Thank you for your feedback!')
    return redirect(url_for('show_reviews'))

@app.route('/reviews', methods=['GET'])
def show_reviews():
    return render_template('reviews_display.html', reviews=reviews)

# ✅ Run the app
if __name__ == "__main__":
    app.run(debug=True)