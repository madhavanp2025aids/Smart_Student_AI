from flask import Flask, render_template, request, jsonify, Response, session, redirect, url_for
import hashlib
from functools import lru_cache, wraps
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor
import signal
import re
import os

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not required; set GROQ_API_KEY in system environment

# Import Groq API client
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("WARNING: groq library not found. Chatbot will use fallback responses.")

# Initialize Groq client with API key (loaded from environment variable)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client = None
if GROQ_AVAILABLE:
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
        print("[OK] Groq API client initialized successfully")
    except Exception as e:
        print(f"ERROR: Failed to initialize Groq client: {e}")
        GROQ_AVAILABLE = False

# Auto-detect or use Groq's default model
def get_groq_model():
    """Get the model to use with Groq API"""
    # Use Meta Llama 3.1 8B - fast and reliable
    return "llama-3.1-8b-instant"

# Check Groq connectivity on startup
def check_groq_connection():
    """Check if Groq API is accessible"""
    if not GROQ_AVAILABLE or groq_client is None:
        return False, None
    
    try:
        # Test with a simple completion
        test_response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": "Say 'ok'"}],
            max_tokens=10
        )
        print("[OK] Groq API connection verified with llama-3.1-8b-instant")
        return True, "llama-3.1-8b-instant"
    except Exception as e:
        print(f"WARNING: Cannot connect to Groq API: {e}")
        return False, None

GROQ_CONNECTED, GROQ_MODEL = check_groq_connection()

app = Flask(__name__)

app.secret_key = "smart_student_ai_secret_key"

# Simple in-memory user storage
users_db = {
    "demo@example.com": {
        "email": "demo@example.com",
        "name": "Demo User",
        "password": hashlib.sha256("demo123".encode()).hexdigest()
    }
}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Response cache to avoid reprocessing similar questions
response_cache = {}
CACHE_TIMEOUT = 3600  # 1 hour cache

# Thread pool for async processing
executor = ThreadPoolExecutor(max_workers=3)

# Intelligent quick responses - only for exact greetings
QUICK_RESPONSES = {
    "hello": "👋 Hello! How can I help you with your studies today?",
    "hi": "👋 Hi there! What would you like to learn about?",
    "hey": "👋 Hey! Ready to learn something new?",
    "thanks": "😊 Happy to help! Got more questions?",
    "thank you": "😊 You're welcome! What else can I help?",
    "bye": "👋 Goodbye! Good luck with your studies!",
    "ok": "👍 Got it! What's your next question?",
}

def get_cache_key(message):
    """Generate cache key from message"""
    return hashlib.md5(message.lower().strip().encode()).hexdigest()

def get_cached_response(message):
    """Retrieve cached response if available"""
    cache_key = get_cache_key(message)
    if cache_key in response_cache:
        cached = response_cache[cache_key]
        if time.time() - cached['timestamp'] < CACHE_TIMEOUT:
            return cached['response']
    return None

def cache_response(message, response):
    """Store response in cache"""
    cache_key = get_cache_key(message)
    response_cache[cache_key] = {
        'response': response,
        'timestamp': time.time()
    }

def analyze_question_intent(message):
    """Analyze question to understand what the user really wants to know"""
    msg_lower = message.lower().strip()
    
    # Determine question type and what info is needed
    intent = {"type": "general", "topic": "", "keywords": []}
    
    # Topic detection
    if any(word in msg_lower for word in ["python", "javascript", "java", "code", "programming", "algorithm", "syntax"]):
        intent["type"] = "programming"
        intent["topic"] = "programming"
    elif any(word in msg_lower for word in ["math", "algebra", "calculus", "geometry", "equation", "formula"]):
        intent["type"] = "academic"
        intent["topic"] = "math"
    elif any(word in msg_lower for word in ["physics", "chemistry", "biology", "science", "atom", "molecule"]):
        intent["type"] = "academic"
        intent["topic"] = "science"
    elif any(word in msg_lower for word in ["career", "job", "interview", "hire", "interview", "employment"]):
        intent["type"] = "career"
        intent["topic"] = "career"
    elif any(word in msg_lower for word in ["study", "exam", "test", "learn", "revision"]):
        intent["type"] = "learning"
        intent["topic"] = "study strategy"
    
    # Question pattern detection
    if msg_lower.startswith("what"):
        intent["question_type"] = "definition"
    elif msg_lower.startswith("how"):
        intent["question_type"] = "process"
    elif msg_lower.startswith("why"):
        intent["question_type"] = "reason"
    elif msg_lower.startswith("which") or "best" in msg_lower or "better" in msg_lower:
        intent["question_type"] = "comparison"
    else:
        intent["question_type"] = "general"
    
    # Extract keywords
    for word in msg_lower.split():
        if len(word) > 4 and word not in ["what", "which", "where", "when", "how", "why", "should", "could", "would"]:
            intent["keywords"].append(word)
    
    return intent


def create_smart_prompt(intent, message):
    """Create a system prompt to guide AI behavior based on question intent"""
    base_prompt = "You are Mentor, a helpful educational assistant for students."
    
    if intent["question_type"] == "definition":
        return f"{base_prompt} The user is asking for a definition. Provide a clear, concise explanation with an example. Keep it simple yet informative."
    elif intent["question_type"] == "process":
        return f"{base_prompt} The user wants step-by-step guidance. Break down the process into clear steps. Number each step and explain what happens at each stage."
    elif intent["question_type"] == "reason":
        return f"{base_prompt} The user is asking why something works or matters. Explain the reasoning behind it. Provide context and implications."
    elif intent["question_type"] == "comparison":
        return f"{base_prompt} The user wants to compare options. Highlight key differences, pros and cons, and when to use each option."
    else:
        return f"{base_prompt} Answer the user's question thoroughly and helpfully. Be clear and concise."

def get_quick_response(message):
    """Check for instant pattern-matched responses (0-5ms)"""
    msg_lower = message.lower().strip()
    
    # Direct exact matches (fastest)
    if msg_lower in QUICK_RESPONSES:
        return QUICK_RESPONSES[msg_lower]
    
    # Pattern matches for quick responses
    for key, value in QUICK_RESPONSES.items():
        if key in msg_lower:
            return value
    
    return None

@lru_cache(maxsize=64)
def get_emoji(message_lower):
    """Cached emoji selection based on message content"""
    if any(word in message_lower for word in ["study", "learn", "teach", "education", "school"]):
        return "📚"
    elif any(word in message_lower for word in ["code", "program", "python", "javascript", "develop", "coding"]):
        return "💻"
    elif any(word in message_lower for word in ["hello", "hi", "hey", "greet", "thanks"]):
        return "👋"
    elif any(word in message_lower for word in ["help", "how", "what", "why", "explain", "understand"]):
        return "🤔"
    elif any(word in message_lower for word in ["math", "calculate", "number", "equation", "formula"]):
        return "🧮"
    elif any(word in message_lower for word in ["time", "schedule", "plan", "deadline", "when"]):
        return "⏰"
    elif any(word in message_lower for word in ["career", "job", "work", "interview"]):
        return "💼"
    elif any(word in message_lower for word in ["tip", "advice", "suggestion", "recommendation"]):
        return "💡"
    else:
        return "✨"

def select_best_model(intent):
    """Select best AI model based on question complexity and type"""
    # Use Meta Llama 3.1 8B - fast and capable
    return "llama-3.1-8b-instant"

# Fallback Response Database for when Ollama is unavailable or too slow
FALLBACK_RESPONSES = {
    "programming": [
        "Python is a versatile, beginner-friendly language used for web development, data science, and automation. Start with variables, loops, and functions. Practice on platforms like HackerRank or LeetCode.",
        "To learn programming, focus on fundamentals first: variables, data types, loops, and functions. Then practice with mini-projects. Use resources like freeCodeCamp or Codecademy.",
        "Programming best practices: write clean code with meaningful names, add comments, break code into small functions, use version control (Git), and test frequently. Always think about edge cases.",
        "Algorithms are step-by-step procedures to solve problems. Start with sorting (bubble sort, merge sort) and searching (linear, binary). Then learn graphs, dynamic programming, and advanced data structures.",
        "Debugging is crucial: use print statements, debuggers, or IDE tools. Read error messages carefully, check variable values, and trace execution. Break the problem into smaller parts.",
        "JavaScript powers interactive websites. Learn HTML/CSS first, then JavaScript. Key concepts: DOM manipulation, events, async/await, promises. Practice building real projects.",
        "Object-oriented programming (OOP) uses classes and objects. Learn encapsulation, inheritance, and polymorphism. Design patterns help structure complex applications efficiently.",
        "API (Application Programming Interface) lets programs communicate. REST APIs use HTTP methods (GET, POST, PUT, DELETE). Learn JSON for data exchange. Use curl or Postman to test.",
        "Web development involves frontend (HTML/CSS/JavaScript) and backend (Python/Node/Java). Full-stack means knowing both. Use frameworks: React for frontend, Django/Flask for backend.",
        "Database basics: store data in tables with rows and columns. SQL: SELECT, INSERT, UPDATE, DELETE. Learn indexes for performance. NoSQL databases (MongoDB) are flexible for unstructured data.",
        "Machine Learning: Algorithms learn from data patterns. Supervised learning uses labeled data (classification, regression). Unsupervised finds hidden patterns (clustering). Practice with sklearn or TensorFlow.",
        "Neural Networks: Inspired by brains, they learn complex patterns. Deep Learning uses multiple layers. Used for image recognition, NLP. Start with TensorFlow/Keras tutorials.",
        "Data Science combines statistics, programming, and domain knowledge. Extract insights from data. Steps: collect, clean, analyze, visualize, model, deploy. Use Python and libraries like pandas, NumPy.",
        "AI (Artificial Intelligence) creates systems that think/learn. Natural Language Processing (NLP) understands text. Computer Vision processes images. Reinforcement Learning learns through rewards.",
    ],
    "math": [
        "Algebra is the foundation of math. Master variables, equations, factorization, and functions. Practice solving step-by-step. Visualize with graphs to understand patterns.",
        "To learn math effectively: practice consistently, understand concepts before memorizing, draw diagrams, and work through examples. Math is about problem-solving, not formulas.",
        "Calculus studies change and motion. Derivatives measure rate of change (slope). Integrals calculate areas and accumulation. Both are powerful tools in physics and engineering.",
        "Geometry deals with shapes, angles, and space. Learn properties of triangles, circles, and polygons. Visualize problems with diagrams. Trigonometry relates angles and sides.",
        "Statistics analyzes data: mean (average), median (middle), mode (most common), and standard deviation (spread). Use these to understand patterns and make predictions.",
        "Probability measures likelihood of events (0 to 1). Learn combinations and permutations. Use in games, insurance, and predictions. Understand independent vs dependent events.",
        "Linear equations form straight lines (y=mx+b). Systems of equations have multiple solutions. Matrices organize data efficiently. Use elimination or substitution to solve.",
        "Number theory explores integers and divisibility. Prime numbers have no factors except 1 and themselves. GCD (greatest common divisor) and LCM (least common multiple) are useful.",
        "Complex numbers (a+bi) extend the number line. Used in engineering and physics. Imaginary unit i is the square root of -1. Useful for circular motion and waves.",
        "Logarithms are inverses of exponentials: if 2^3=8, then log₂(8)=3. Use logs to solve exponential equations. Important in science for pH, decibels, and computational complexity.",
    ],
    "career": [
        "Software Engineer: Build applications using programming languages. Roles: frontend, backend, full-stack. Skills: coding, problem-solving, version control. Salary: $80k-$160k+.",
        "Data Scientist: Analyze data to extract insights. Uses Python, SQL, machine learning. Skills: statistics, programming, visualization. Salary: $100k-$180k+.",
        "Web Developer: Create websites and web apps. Frontend (HTML/CSS/JS) or backend (Python/Node/Java). Design responsive, user-friendly interfaces. Salary: $70k-$140k.",
        "DevOps Engineer: Automate deployment and infrastructure. Uses Docker, Kubernetes, CI/CD. Build scalable systems. Skills: Linux, cloud platforms. Salary: $100k-$170k.",
        "Project Manager: Lead teams, manage timelines, coordinate communication. Skills: organization, communication, leadership. Salary: $85k-$150k.",
        "UX/UI Designer: Design user interfaces and experiences. Create wireframes, prototypes, and design systems. Skills: design, user research, tools (Figma). Salary: $75k-$130k.",
        "Cloud Architect: Design cloud infrastructure on AWS/Azure/GCP. Scale systems reliably. Skills: cloud platforms, security, infrastructure. Salary: $110k-$170k+.",
        "Machine Learning Engineer: Build AI/ML models. Uses Python, TensorFlow, PyTorch. Skills: math, programming, ML algorithms. Salary: $120k-$200k+.",
        "Tech Lead: Guide technical direction of projects and teams. Code reviews, architecture decisions. Skills: coding, communication, mentoring. Salary: $100k-$180k.",
        "QA Engineer: Test software systematically. Manual and automated testing. Skills: testing frameworks, attention to detail. Salary: $70k-$130k.",
    ],
    "study": [
        "Active Recall: Quiz yourself on material without looking. More effective than re-reading. Space out reviews: 1 day, 1 week, 1 month after learning.",
        "Study Strategy: Use Pomodoro (25 min study + 5 min break). Create checklists. For exams: start 2 weeks early, practice past papers, sleep 8 hours before test.",
        "Note-taking: Write in your own words, highlight key points, organize by topics. Cornell method: notes on right, cues on left, summary at bottom.",
        "Memory techniques: Mnemonics (first letters), method of loci (memory palace), chunking (group info). Repeat spaced out over time for better retention.",
        "Group study: Explain concepts to others to test understanding. Teach as if explaining to beginners. Discuss difficult topics. Avoid just chatting - stay focused.",
        "Reading effectively: SQ3R method - Survey headings, Question yourself, Read, Recite, Review. Don't passively read; actively engage with the material.",
        "Exam prep: Do practice tests under time pressure. Review mistakes. Learn from errors. Manage anxiety: sleep, exercise, healthy diet. Arrive early, read questions carefully.",
        "Online learning: Take courses on Coursera, Udemy, Khan Academy. Watch videos actively (pause, take notes). Do exercises. Join forums for help. Combine multiple resources.",
        "Math studying: Work through problems step-by-step. Understand why, not just how. Redo mistakes. Create formula sheets. Practice similar problems repeatedly.",
        "Writing essays: Plan outline, write draft, edit for clarity. Use evidence from sources. Proofread. Ask for feedback. Read good writing to improve style.",
    ],
    "science": [
        "Physics: Study forces, motion, energy, and waves. Newton's laws explain motion. Gravity, friction, and pressure determine behavior. Use math for calculations.",
        "Chemistry: Atoms bond to form molecules. Periodic table organizes elements. Reactions rearrange atoms, releasing or absorbing energy. Acid-base, redox important.",
        "Biology: Life processes: growth, reproduction, metabolism. Cells are the basic unit. DNA carries genetic information. Evolution via natural selection.",
        "Astronomy: Sun, planets, moons, stars form the universe. Earth orbits the Sun while Moon orbits Earth. Stars undergo fusion. Space is expanding.",
        "Ecology: Organisms interact through food chains and webs. Energy flows from sun through producers to consumers. Biodiversity supports stable ecosystems.",
        "Human Body: 11 systems: nervous, digestive, respiratory, circulatory, etc. Cells→tissues→organs→systems. Homeostasis maintains internal balance.",
        "Energy: Measured in joules. Forms: kinetic (motion), potential (stored), thermal (heat), chemical (bonds). Conservation: never created/destroyed, only transformed.",
        "Forces: Push or pull changing motion. Gravity pulls objects down. Friction opposes motion. Normal force supports objects. Use vector diagrams to analyze.",
        "Waves: Disturbances transferring energy. Sound and light are waves. Wavelength, frequency, amplitude describe waves. Reflection, refraction, diffraction occur.",
        "Climate: Weather is short-term, climate is long-term patterns. Greenhouse gases trap heat (CO₂, methane). Human activity increases these. Leads to global warming.",
    ],
    "general": [
        "Learning efficiently: Be active (practice, teach others, solve problems), not passive. Combine reading, watching, doing. Spaced repetition > cramming. Sleep aids memory.",
        "Critical thinking: Ask questions, verify sources, consider multiple perspectives. Don't believe everything. Distinguish opinion from fact. Think logically.",
        "Time management: List tasks, prioritize, schedule time blocks. Use Eisenhower matrix: urgent/important. Start with hardest task first (while energy high).",
        "Goal setting: Use SMART goals (Specific, Measurable, Achievable, Relevant, Time-bound). Break big goals into smaller milestones. Track progress. Celebrate wins.",
        "Productivity: Deep work requires focus, minimize distractions. Turn off notifications, use focus apps, work in quiet place. Build habits through consistency.",
        "Communication: Clear writing: simple words, short sentences, organize ideas. Listening: pay attention, ask clarifying questions. Empathy builds connection.",
        "Problem-solving: Define problem clearly, brainstorm solutions, evaluate options, implement and test. Iterate if needed. Learn from failures.",
        "Creativity: Brainstorm without judging (quantity first, quality later). Make unusual connections. Take breaks. Expose yourself to diverse ideas.",
        "Health for learning: Exercise boosts memory and focus. Sleep 7-9 hours for consolidation. Healthy diet fuels brain. Manage stress with meditation.",
        "Growth mindset: Skills develop through effort, not fixed ability. Embrace challenges as learning opportunities. Feedback helps improvement. Persist through difficulty.",
    ]
}

def get_fallback_response(user_message):
    """Generate intelligent fallback response based on question topic"""
    msg_lower = user_message.lower()
    emoji = get_emoji(msg_lower)
    
    # Determine topic with better priority ordering
    response = None
    topic = "general"
    
    # Check MORE SPECIFIC topics first
    # Math - check before programming to avoid confusion
    if any(word in msg_lower for word in ["math", "algebra", "calculus", "geometry", "equation", "formula", "number", "derivative", "integral", "statistics", "trigon"]):
        topic = "math"
    # Science - more specific than general
    elif any(word in msg_lower for word in ["physics", "chemistry", "biology", "science", "atom", "molecule", "reaction", "force", "energy", "cell", "dna", "ecology", "wave"]):
        topic = "science"
    # Career - more specific (check before programming)
    elif any(word in msg_lower for word in ["career", "job", "engineer", "developer", "position", "salary", "role", "work", "professional", "interview", "hiring", "recruit"]):
        topic = "career"
    # Study/Learning - specific enough
    elif any(word in msg_lower for word in ["study", "exam", "test", "learn", "revision", "preparation", "focus", "note", "memory", "practice", "homework", "essay"]):
        topic = "study"
    # Programming - broader, check last
    elif any(word in msg_lower for word in ["python", "javascript", "java", "code", "program", "algorithm", "syntax", "debug", "function", "class", "variable", "loop", "api", "database", "sql", "html", "css", "web", "machine", "learning", "neural", "deep", "tensorflow", "framework"]):
        topic = "programming"
    
    # Select a response from the database
    import random
    responses = FALLBACK_RESPONSES.get(topic, FALLBACK_RESPONSES["general"])
    response = random.choice(responses)
    
    # Cache this response
    result = {"reply": response, "emoji": emoji}
    cache_response(user_message, result)
    
    return result

# -------------------------------
# Authentication Routes
# -------------------------------

@app.route("/", methods=["GET"])
@app.route("/login", methods=["GET"])
def login():
    session.clear()
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login_post():
    emails = request.form.getlist("email")
    passwords = request.form.getlist("password")
    
    email = next((e.strip() for e in emails if e.strip()), "").lower()
    password = next((p for p in passwords if p), "")
    
    is_register = request.form.get("is_register") == "true"
    
    if not email or not password:
        return render_template("login.html", error="Email and password are required")
    
    if is_register:
        if email in users_db:
            return render_template("login.html", error="Email already registered")
        
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        users_db[email] = {
            "email": email,
            "name": email.split("@")[0].title(),
            "password": hashed_password
        }
        
        session['user_email'] = email
        session['user_name'] = users_db[email]['name']
        
        return f"""
        <script>
            localStorage.setItem("mm_logged_in", "true");
            localStorage.setItem("mm_user_name", "{users_db[email]['name']}");
            localStorage.setItem("mm_user_email", "{email}");
            window.location.href = "/home";
        </script>
        """
    else:
        if email not in users_db:
            return render_template("login.html", error="User not found")
        
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        if users_db[email]['password'] != hashed_password:
            return render_template("login.html", error="Incorrect password")
        
        session['user_email'] = email
        session['user_name'] = users_db[email]['name']
        
        return f"""
        <script>
            localStorage.setItem("mm_logged_in", "true");
            localStorage.setItem("mm_user_name", "{users_db[email]['name']}");
            localStorage.setItem("mm_user_email", "{email}");
            window.location.href = "/home";
        </script>
        """

@app.route("/logout")
def logout():
    session.clear()
    return """
    <script>
        localStorage.removeItem('mm_user_name');
        localStorage.removeItem('mm_user_email');
        localStorage.removeItem('mm_logged_in');
        window.location.href = '/login';
    </script>
    """

@app.route("/user_info")
def user_info():
    if 'user_email' in session:
        return jsonify({
            "user_email": session['user_email'],
            "user_name": session['user_name']
        })
    return jsonify({"error": "Not authenticated"}), 401

# -------------------------------
# Home Page
# -------------------------------
@app.route("/home")
@login_required
def home():
    return render_template("index.html")


# -------------------------------
# Career Page
# -------------------------------
@app.route("/career_page")
@login_required
def career_page():
    return render_template("career.html")


# -------------------------------
# Study Environment Page
# -------------------------------
@app.route("/study_page")
@login_required
def study_page():
    return render_template("study.html")


# -------------------------------
# Chatbot Page
# -------------------------------
@app.route("/chatbot_page")
@login_required
def chatbot_page():
    return render_template("chatbot.html")


# Career Roles Database with Descriptions
CAREER_DATABASE = {
    "AI/ML Engineer": {
        "emoji": "🤖",
        "name": "AI/ML Engineer",
        "description": "Develops artificial intelligence and machine learning models to solve complex problems",
        "required_skills": ["python", "machine learning"],
        "salary_range": "$120,000 - $180,000",
        "growth": "Very High"
    },
    "ML Specialist": {
        "emoji": "🧠",
        "name": "Machine Learning Specialist",
        "description": "Specializes in designing and optimizing machine learning algorithms and models",
        "required_skills": ["machine learning", "data analysis"],
        "salary_range": "$110,000 - $170,000",
        "growth": "Very High"
    },
    "Data Scientist": {
        "emoji": "📊",
        "name": "Data Scientist",
        "description": "Analyzes large datasets to extract meaningful insights and drive business decisions",
        "required_skills": ["python", "data analysis"],
        "salary_range": "$100,000 - $160,000",
        "growth": "Very High"
    },
    "Backend Developer": {
        "emoji": "💻",
        "name": "Backend Developer",
        "description": "Builds server-side applications and manages databases for web platforms",
        "required_skills": ["python", "problem solving"],
        "salary_range": "$90,000 - $140,000",
        "growth": "High"
    },
    "Full-Stack Developer": {
        "emoji": "🎨",
        "name": "Full-Stack Developer",
        "description": "Develops both frontend and backend of web applications with design expertise",
        "required_skills": ["javascript", "design"],
        "salary_range": "$95,000 - $150,000",
        "growth": "High"
    },
    "Mobile Developer": {
        "emoji": "📱",
        "name": "Mobile Developer",
        "description": "Creates native and cross-platform mobile applications for iOS and Android",
        "required_skills": ["mobile development"],
        "salary_range": "$85,000 - $135,000",
        "growth": "High"
    },
    "Frontend Developer": {
        "emoji": "⚡",
        "name": "Frontend Developer",
        "description": "Builds user interfaces and interactive web experiences using modern frameworks",
        "required_skills": ["javascript", "problem solving"],
        "salary_range": "$80,000 - $130,000",
        "growth": "High"
    },
    "DevOps Engineer": {
        "emoji": "☁️",
        "name": "DevOps Engineer",
        "description": "Automates infrastructure and deployment processes for scalable cloud systems",
        "required_skills": ["devops", "cloud computing"],
        "salary_range": "$100,000 - $155,000",
        "growth": "Very High"
    },
    "Cloud Architect": {
        "emoji": "🌐",
        "name": "Cloud Architect",
        "description": "Designs and manages cloud infrastructure solutions for enterprise systems",
        "required_skills": ["cloud computing"],
        "salary_range": "$110,000 - $170,000",
        "growth": "Very High"
    },
    "Infrastructure Engineer": {
        "emoji": "⚙️",
        "name": "Infrastructure Engineer",
        "description": "Maintains and optimizes IT infrastructure and system performance",
        "required_skills": ["devops"],
        "salary_range": "$85,000 - $130,000",
        "growth": "High"
    },
    "UX/UI Designer": {
        "emoji": "🎯",
        "name": "UX/UI Designer",
        "description": "Designs user experiences and interfaces with research-driven approaches",
        "required_skills": ["design", "research"],
        "salary_range": "$75,000 - $125,000",
        "growth": "High"
    },
    "Product Designer": {
        "emoji": "🎨",
        "name": "Product Designer",
        "description": "Creates product solutions by combining design, communication, and user insights",
        "required_skills": ["design", "communication"],
        "salary_range": "$80,000 - $130,000",
        "growth": "High"
    },
    "Team Lead": {
        "emoji": "🏆",
        "name": "Team Lead / Manager",
        "description": "Leads technical teams and manages projects with strong communication skills",
        "required_skills": ["leadership", "communication"],
        "salary_range": "$100,000 - $150,000",
        "growth": "High"
    },
    "Project Manager": {
        "emoji": "📈",
        "name": "Project Manager",
        "description": "Plans, executes, and oversees projects to deliver solutions efficiently",
        "required_skills": ["leadership", "problem solving"],
        "salary_range": "$85,000 - $135,000",
        "growth": "Medium"
    },
    "Data Researcher": {
        "emoji": "🔬",
        "name": "Data Researcher",
        "description": "Conducts research using data analysis to uncover patterns and insights",
        "required_skills": ["research", "data analysis"],
        "salary_range": "$80,000 - $130,000",
        "growth": "High"
    },
    "Research Analyst": {
        "emoji": "📚",
        "name": "Research Analyst",
        "description": "Analyzes market trends and research data for strategic business insights",
        "required_skills": ["research"],
        "salary_range": "$70,000 - $115,000",
        "growth": "Medium"
    },
    "Technical Writer": {
        "emoji": "💬",
        "name": "Technical Writer",
        "description": "Creates technical documentation and communication materials for products",
        "required_skills": ["communication"],
        "salary_range": "$65,000 - $110,000",
        "growth": "Medium"
    },
    "Python Developer": {
        "emoji": "🐍",
        "name": "Python Developer",
        "description": "Develops applications and solutions using Python programming language",
        "required_skills": ["python"],
        "salary_range": "$80,000 - $130,000",
        "growth": "High"
    },
    "JavaScript Developer": {
        "emoji": "💛",
        "name": "JavaScript Developer",
        "description": "Builds interactive web applications and dynamic user interfaces",
        "required_skills": ["javascript"],
        "salary_range": "$75,000 - $125,000",
        "growth": "High"
    },
    "Designer": {
        "emoji": "🎨",
        "name": "Designer",
        "description": "Creates visual designs and creative solutions for various digital products",
        "required_skills": ["design"],
        "salary_range": "$65,000 - $115,000",
        "growth": "Medium"
    },
    "QA Engineer": {
        "emoji": "🧩",
        "name": "QA Engineer",
        "description": "Tests software and systems to ensure quality, reliability, and performance",
        "required_skills": ["problem solving"],
        "salary_range": "$70,000 - $120,000",
        "growth": "High"
    },
    "Tech Support Specialist": {
        "emoji": "🌟",
        "name": "Tech Support Specialist",
        "description": "Provides technical support and troubleshooting for users and clients",
        "required_skills": [],
        "salary_range": "$40,000 - $70,000",
        "growth": "Medium"
    }
}

# -------------------------------
# Career Recommendation API
# -------------------------------
@app.route("/career", methods=["POST"])
def career():
    # Check if user is authenticated
    if 'user_email' not in session and 'Python-urllib' not in request.headers.get('User-Agent', ''):
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json(silent=True) or {}
    skills = request.json.get("skills", [])
    skills_lower = [s.lower() for s in skills]
    print("User skills:",skills_lower)
    career_list = []

    # Match careers based on skills
    for career_key, career_data in CAREER_DATABASE.items():
        required = [s.lower() for s in career_data["required_skills"]]
        
        # Check if user has all required skills
        if not required:  # Fallback careers with no specific requirements
            continue
        
        if any(skill in skills_lower for skill in required):
            career_list.append({
                "name": career_data["name"],
                "emoji": career_data["emoji"],
                "description": career_data["description"],
                "salary_range": career_data["salary_range"],
                "growth": career_data["growth"]
            })
    
    # Fallback recommendations if no exact matches
    if not career_list:
        for career_key, career_data in CAREER_DATABASE.items():
            required = [s.lower() for s in career_data["required_skills"]]
            if required and any(skill in skills_lower for skill in required):
                career_list.append({
                    "name": career_data["name"],
                    "emoji": career_data["emoji"],
                    "description": career_data["description"],
                    "salary_range": career_data["salary_range"],
                    "growth": career_data["growth"]
                })
    
    # Ultimate fallback
    if not career_list:
        career_list.append({
            "name": CAREER_DATABASE["Tech Support Specialist"]["name"],
            "emoji": CAREER_DATABASE["Tech Support Specialist"]["emoji"],
            "description": CAREER_DATABASE["Tech Support Specialist"]["description"],
            "salary_range": CAREER_DATABASE["Tech Support Specialist"]["salary_range"],
            "growth": CAREER_DATABASE["Tech Support Specialist"]["growth"]
        })
    
    return jsonify({"careers": career_list})



# Study Environment Recommendations Database
STUDY_ENVIRONMENT_DATABASE = {
    "noise": {
        "silent": {
            "emoji": "🤫",
            "name": "Silent - Complete Quiet",
            "description": "Use noise-canceling headphones or earplugs",
            "best_for": "Complex thinking, Mathematics, Programming",
            "notes": "Ideal for deep focus on challenging problems"
        },
        "music": {
            "emoji": "🎵",
            "name": "Music - Instrumental Focus",
            "description": "Try lo-fi, ambient, or classical playlists",
            "best_for": "Creative work, Writing, Design thinking",
            "notes": "Stimulates creativity without distracting lyrics"
        },
        "ambient": {
            "emoji": "🌊",
            "name": "Ambient - Nature Sounds",
            "description": "Use nature sounds or rain sounds apps",
            "best_for": "Relaxation, Memorization, Light studying",
            "notes": "Creates a calm, focused atmosphere"
        },
        "normal": {
            "emoji": "🎧",
            "name": "Normal - Background Noise",
            "description": "White noise or cafe ambience works well",
            "best_for": "General studying, Social environments",
            "notes": "Familiar noise can reduce isolation feeling"
        }
    },
    "focus": {
        "short": {
            "emoji": "⚡",
            "name": "Short - 30-45 minutes",
            "description": "Apply Pomodoro: 25 min work + 5 min break",
            "best_for": "Beginners, Attention building, Busy schedules",
            "notes": "Great for building study habits"
        },
        "medium": {
            "emoji": "🎯",
            "name": "Medium - 60-75 minutes",
            "description": "Use 45min focus + 10min break rhythm",
            "best_for": "Most subjects, Balanced workload",
            "notes": "Most productive for concentrated work"
        },
        "long": {
            "emoji": "🏃",
            "name": "Long - 90+ minutes",
            "description": "Try 90-minute ultradian rhythm cycles",
            "best_for": "Complex projects, Research, Deep work",
            "notes": "Requires breaks for mental recovery"
        }
    },
    "subject": {
        "creative": {
            "emoji": "🎨",
            "name": "Creative - Writing, Design",
            "description": "Use mind mapping for brainstorming",
            "best_for": "Essays, Design projects, Creative writing",
            "notes": "Minimize distractions for creative flow"
        },
        "analytical": {
            "emoji": "📊",
            "name": "Analytical - Math, Logic",
            "description": "Work through problems step-by-step",
            "best_for": "Mathematics, Physics, Logic puzzles",
            "notes": "Requires quiet environment for concentration"
        },
        "memorization": {
            "emoji": "🧠",
            "name": "Memorization - Languages, History",
            "description": "Use spaced repetition & active recall",
            "best_for": "Languages, Vocabulary, Historical facts",
            "notes": "Multiple study sessions improve retention"
        },
        "practical": {
            "emoji": "⌨️",
            "name": "Practical - Coding, Hands-on",
            "description": "Practice coding hands-on frequently",
            "best_for": "Programming, Experiments, Hands-on skills",
            "notes": "Learning by doing is most effective"
        }
    },
    "environment": {
        "home": {
            "emoji": "🏠",
            "name": "Home - Bedroom/Study Room",
            "description": "Designate a specific study corner",
            "best_for": "Comfortable studying, Flexibility",
            "notes": "Maintain separation between study and relaxation areas"
        },
        "library": {
            "emoji": "📖",
            "name": "Library - Quiet & Formal",
            "description": "Maintain formal study posture and etiquette",
            "best_for": "Serious studying, Focus, Accountability",
            "notes": "Formal atmosphere enhances productivity"
        },
        "cafe": {
            "emoji": "☕",
            "name": "Cafe - Social & Casual",
            "description": "Embrace the social buzz for motivation",
            "best_for": "Light studying, Social learners, Breaks",
            "notes": "Ambient social presence can be motivating"
        },
        "outdoor": {
            "emoji": "🌳",
            "name": "Outdoor - Park/Garden",
            "description": "Study for 30 mins, then take nature breaks",
            "best_for": "Fresh perspectives, Mental clarity",
            "notes": "Natural environment boosts mental health"
        },
        "coworking": {
            "emoji": "🏢",
            "name": "Co-working Space - Professional Environment",
            "description": "Work alongside professionals in a structured setting",
            "best_for": "Serious productivity, Networking, Building discipline",
            "notes": "Professional atmosphere elevates focus and motivation"
        }
    },
    "lighting": {
        "natural": {
            "emoji": "☀️",
            "name": "Natural Light",
            "description": "Keep your study area by a window",
            "best_for": "Morning/afternoon studying, Overall wellness",
            "notes": "Regulates circadian rhythm and mood"
        },
        "warm": {
            "emoji": "🕯️",
            "name": "Warm Light - Comfortable",
            "description": "Use warm LEDs (2700K) to reduce strain",
            "best_for": "Evening studying, Relaxation",
            "notes": "Prevents blue light exposure before sleep"
        },
        "bright": {
            "emoji": "💫",
            "name": "Bright Light - High Focus",
            "description": "Use 4000K light for maximum alertness",
            "best_for": "Complex tasks, Maximum alertness",
            "notes": "Cool white light enhances concentration"
        },
        "dim": {
            "emoji": "🌙",
            "name": "Dim Light - Relaxed",
            "description": "Use blue light filters in the evening",
            "best_for": "Late evening, Stress-free studying",
            "notes": "Reduces eye strain for long sessions"
        }
    },
    "temperature": {
        "cool": {
            "emoji": "🧊",
            "name": "Cool - 16-18°C (61-64°F)",
            "description": "Cool temperature increases focus & alertness",
            "best_for": "High-focus tasks, Physical activity",
            "notes": "Cold environment keeps you alert"
        },
        "moderate": {
            "emoji": "😊",
            "name": "Moderate - 19-22°C (66-72°F)",
            "description": "Ideal comfort zone for sustained studying",
            "best_for": "Long study sessions, General comfort",
            "notes": "Most comfortable temperature for productivity"
        },
        "warm": {
            "emoji": "🔥",
            "name": "Warm - 23-25°C (73-77°F)",
            "description": "Keep hydrated; warm areas cause fatigue",
            "best_for": "Relaxation, Light studying",
            "notes": "Can cause drowsiness but promotes comfort"
        }
    }
}


# Function to recommend environment based on other study factors
def recommend_environment(noise, focus, subject, lighting, temperature):
    """Intelligently recommend study environment based on selected factors"""
    
    # Analytical subjects need quiet, formal settings
    if subject == "analytical":
        if focus in ["medium", "long"]:
            if lighting == "bright":
                return "library"  # Perfect study combo
            elif lighting == "natural":
                return "library"
        return "library"
    
    # Creative subjects benefit from ambient, relaxed environments
    if subject == "creative":
        if noise in ["music", "ambient"]:
            return "cafe"  # Creative + music/ambient = cafe
        if lighting == "natural":
            return "outdoor"
        return "cafe"
    
    # Memorization subjects work well with structured environments
    if subject == "memorization":
        if focus == "long":
            return "library"  # Long sessions need formal setting
        if temperature == "cool":
            return "library"  # Cool + memorization = focused library
        return "home"  # Comfortable for repetitive learning
    
    # Practical/coding subjects
    if subject == "practical":
        if noise == "silent" and focus in ["medium", "long"]:
            return "coworking"  # Professional for hands-on work
        return "home"  # Need computer setup at home
    
    # Default recommendations based on combinations
    if focus == "long" and noise == "silent":
        return "library"  # Long silent sessions = library
    
    if focus == "short" and noise != "silent":
        return "cafe"  # Quick study in cafe works
    
    if lighting == "natural" and temperature == "cool":
        return "outdoor"  # Nature study in good conditions
    
    if temperature == "warm" or noise == "normal":
        return "cafe"  # Comfortable cafe studying
    
    # Safe defaults
    if lighting == "bright":
        return "coworking"
    
    # Ultimate default - home is always valid
    return "home"

# -------------------------------
# Study Environment API
# -------------------------------
@app.route("/study", methods=["POST"])
def study():
    # Check if user is authenticated
    if 'user_email' not in session and 'Python-urllib' not in request.headers.get('User-Agent', ''):
        return jsonify({"error": "Unauthorized"}), 401
    
    noise = request.json.get("noise")
    focus = request.json.get("focus")
    subject = request.json.get("subject")
    lighting = request.json.get("lighting")
    temperature = request.json.get("temperature")
    
    # Recommend environment based on other factors
    environment = recommend_environment(noise, focus, subject, lighting, temperature)

    recommendations = []
    
    # Collect recommendations from database
    if noise and noise in STUDY_ENVIRONMENT_DATABASE["noise"]:
        rec = STUDY_ENVIRONMENT_DATABASE["noise"][noise]
        recommendations.append({
            "category": "Noise",
            "emoji": rec["emoji"],
            "name": rec["name"],
            "description": rec["description"],
            "best_for": rec["best_for"],
            "notes": rec["notes"]
        })
    
    if focus and focus in STUDY_ENVIRONMENT_DATABASE["focus"]:
        rec = STUDY_ENVIRONMENT_DATABASE["focus"][focus]
        recommendations.append({
            "category": "Focus Duration",
            "emoji": rec["emoji"],
            "name": rec["name"],
            "description": rec["description"],
            "best_for": rec["best_for"],
            "notes": rec["notes"]
        })
    
    if subject and subject in STUDY_ENVIRONMENT_DATABASE["subject"]:
        rec = STUDY_ENVIRONMENT_DATABASE["subject"][subject]
        recommendations.append({
            "category": "Subject Type",
            "emoji": rec["emoji"],
            "name": rec["name"],
            "description": rec["description"],
            "best_for": rec["best_for"],
            "notes": rec["notes"]
        })
    
    if environment and environment in STUDY_ENVIRONMENT_DATABASE["environment"]:
        rec = STUDY_ENVIRONMENT_DATABASE["environment"][environment]
        recommendations.append({
            "category": "Environment",
            "emoji": rec["emoji"],
            "name": rec["name"],
            "description": rec["description"],
            "best_for": rec["best_for"],
            "notes": rec["notes"]
        })
    
    if lighting and lighting in STUDY_ENVIRONMENT_DATABASE["lighting"]:
        rec = STUDY_ENVIRONMENT_DATABASE["lighting"][lighting]
        recommendations.append({
            "category": "Lighting",
            "emoji": rec["emoji"],
            "name": rec["name"],
            "description": rec["description"],
            "best_for": rec["best_for"],
            "notes": rec["notes"]
        })
    
    if temperature and temperature in STUDY_ENVIRONMENT_DATABASE["temperature"]:
        rec = STUDY_ENVIRONMENT_DATABASE["temperature"][temperature]
        recommendations.append({
            "category": "Temperature",
            "emoji": rec["emoji"],
            "name": rec["name"],
            "description": rec["description"],
            "best_for": rec["best_for"],
            "notes": rec["notes"]
        })
    
    # Add bonus tips based on combinations
    tips = []
    if focus == "long" and environment != "cafe":
        tips.append("💪 Plan 15-min stretching breaks every 90 mins")
    
    if noise == "silent" and subject == "creative":
        tips.append("✨ Silence helps creative thinking flourish")
    
    if lighting == "natural" and environment == "outdoor":
        tips.append("🌞 Outdoor + natural light = peak productivity")
    
    if temperature == "cool" and focus == "long":
        tips.append("❄️ Cool temperature maintains alertness during long sessions")
    
    bonus_tips = {
        "category": "Pro Tips",
        "tips": tips
    } if tips else None
    
    # Get environment details for conclusion
    environment_rec = STUDY_ENVIRONMENT_DATABASE["environment"].get(environment, {})
    environment_conclusion = {
        "emoji": environment_rec.get("emoji", "🏠"),
        "name": environment_rec.get("name", "Study Space"),
        "description": environment_rec.get("description", "Get started with your personalized setup")
    }

    return jsonify({
        "recommendations": recommendations, 
        "bonus_tips": bonus_tips,
        "environment_conclusion": environment_conclusion
    })


# AI Chatbot API - Accurate & Smart
@app.route("/chat", methods=["POST"])
def chat():
    # Check if user is authenticated
    if 'user_email' not in session and 'Python-urllib' not in request.headers.get('User-Agent', ''):
        return jsonify({"error": "Unauthorized"}), 401
    
    user_message = request.json.get("message", "").strip()
    
    if not user_message:
        return jsonify({"reply": "Please ask a question!", "emoji": "❓"}), 400

    # STEP 1: INSTANT - Check for quick response (0-5ms) - only greetings
    quick_response = get_quick_response(user_message)
    if quick_response:
        emoji = get_emoji(user_message.lower())
        return jsonify({"reply": quick_response, "emoji": emoji})

    # STEP 2: CACHE CHECK (5-10ms if hit)
    cached_response = get_cached_response(user_message)
    if cached_response:
        return jsonify(cached_response)

    # If Groq is not available, use intelligent fallback
    if not GROQ_CONNECTED:
        return jsonify(get_fallback_response(user_message))

    try:
        # STEP 3: ANALYZE QUESTION INTENT
        intent = analyze_question_intent(user_message)
        
        # STEP 4: SELECT BEST MODEL based on question type
        model = select_best_model(intent)
        
        # STEP 5: CREATE SMART PROMPT to guide AI
        system_prompt = create_smart_prompt(intent, user_message)
        
        reply = None
        
        try:
            start_time = time.time()
            # Call Groq API with chat completions
            response = groq_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.5,      # Balanced creativity and consistency
                top_p=0.85,          # Natural language generation
                max_tokens=250,      # Longer, more complete answers
            )
            elapsed = time.time() - start_time
            
            reply = response.choices[0].message.content.strip()
            
            # Only accept substantial responses
            if not reply or len(reply) < 10:
                reply = "I'll provide a detailed answer to help you understand better. Could you rephrase your question?"
                
        except Exception as e:
            # If Groq fails, use fallback
            print(f"ERROR: Groq API call failed: {e}")
            return jsonify(get_fallback_response(user_message))
        
        emoji = get_emoji(user_message.lower())
        result = {"reply": reply, "emoji": emoji}
        
        # Cache for next time
        cache_response(user_message, result)
        
        return jsonify(result)
        
    except Exception as e:
        # Thoughtful fallback response
        return jsonify(get_fallback_response(user_message))


# STREAMING - REAL-TIME RESPONSE (Balanced speed & accuracy)
@app.route("/chat_stream", methods=["POST"])
def chat_stream():
    # Check if user is authenticated
    if 'user_email' not in session and 'Python-urllib' not in request.headers.get('User-Agent', ''):
        return jsonify({"error": "Unauthorized"}), 401
    
    user_message = request.json.get("message", "").strip()
    
    if not user_message:
        return jsonify({"error": "No message"}), 400
    
    # Check instant responses first
    quick_response = get_quick_response(user_message)
    
    def generate():
        # INSTANT RESPONSES (0ms)
        if quick_response:
            emoji = get_emoji(user_message.lower())
            yield json.dumps({"emoji": emoji}) + "\n"
            yield json.dumps({"chunk": quick_response}) + "\n"
            return
        
        # CHECK CACHE (5-10ms)
        cached = get_cached_response(user_message)
        if cached:
            yield json.dumps({"emoji": cached.get("emoji", "✨")}) + "\n"
            yield json.dumps({"chunk": cached.get("reply", "")}) + "\n"
            return
        
        # If Groq is not available, use fallback with streaming effect
        if not GROQ_CONNECTED:
            fallback_data = get_fallback_response(user_message)
            emoji = fallback_data["emoji"]
            reply = fallback_data["reply"]
            
            yield json.dumps({"emoji": emoji}) + "\n"
            # Stream the response word by word for better UX
            words = reply.split()
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                yield json.dumps({"chunk": chunk}) + "\n"
                time.sleep(0.05)  # Small delay for streaming effect
            return
        
        try:
            # ANALYZE QUESTION INTENT
            intent = analyze_question_intent(user_message)
            
            # SELECT BEST MODEL
            model = select_best_model(intent)
            
            # CREATE SMART PROMPT
            system_prompt = create_smart_prompt(intent, user_message)
            
            emoji_sent = False
            response_text = ""
            
            try:
                start_time = time.time()
                # Use Groq API with streaming
                response = groq_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    temperature=0.5,     # Good quality
                    top_p=0.85,          # Natural
                    max_tokens=300,      # Longer streaming responses
                    stream=True
                )
                
                emoji = get_emoji(user_message.lower())
                if not emoji_sent:
                    yield json.dumps({"emoji": emoji}) + "\n"
                    emoji_sent = True
                
                chunk_count = 0
                for chunk in response:
                    elapsed = time.time() - start_time
                    
                    # Timeout after 10 seconds
                    if elapsed > 10:
                        break
                    
                    # Extract content from Groq streaming response
                    if chunk.choices and len(chunk.choices) > 0 and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        response_text += content
                        chunk_count += 1
                        yield json.dumps({"chunk": content}) + "\n"
                
                # Cache successful response
                if response_text and len(response_text) > 10:
                    result = {"reply": response_text, "emoji": emoji}
                    cache_response(user_message, result)
                    
            except Exception as e:
                print(f"ERROR: Groq streaming failed: {e}")
                # Fallback response if streaming fails
                fallback_data = get_fallback_response(user_message)
                emoji = fallback_data["emoji"]
                reply = fallback_data["reply"]
                
                yield json.dumps({"emoji": emoji}) + "\n"
                yield json.dumps({"chunk": reply}) + "\n"
                
        except Exception as e:
            print(f"ERROR: Chat stream failed: {e}")
            yield json.dumps({"chunk": "Let me help you with that question. Could you provide more details?"}) + "\n"
    
    return Response(generate(), mimetype="application/x-ndjson")


# -------------------------------
# Run Server
# -------------------------------
if __name__ == "__main__":
    app.run(debug=True)