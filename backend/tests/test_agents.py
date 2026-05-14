"""
test_agents.py — Evaluation Tests for CodeSense Agents
========================================================

These tests validate that each AI agent can actually catch known bugs.
Each test feeds a crafted diff containing an intentional vulnerability
and checks that the agent identifies it correctly.

How to run:
    cd d:\CodeSence\backend
    pytest tests/test_agents.py -v

NOTE: These tests make REAL API calls to Groq. You need a valid GROQ_API_KEY
in your .env file. Each test costs ~1-2 cents in API usage.
"""

import pytest
import sys
import os
from pathlib import Path

# Add the backend directory to sys.path so imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

# Load env before importing agents (they need GROQ_API_KEY)
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from agents.security import security_agent
from agents.performance import performance_agent
from agents.logic import logic_agent
from agents.style import style_agent


# ============================================================
# Test Diffs — each contains a known, obvious bug
# ============================================================

DIFF_HARDCODED_SECRET = """
diff --git a/config.py b/config.py
new file mode 100644
--- /dev/null
+++ b/config.py
@@ -0,0 +1,12 @@
+import os
+
+class Config:
+    DATABASE_URL = "postgresql://admin:admin123@localhost/mydb"
+    SECRET_KEY = "super_secret_key_12345"
+    AWS_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
+    AWS_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
+    DEBUG = True
+
+    def get_db_url(self):
+        return self.DATABASE_URL
"""

DIFF_SQL_INJECTION = """
diff --git a/api/users.py b/api/users.py
--- a/api/users.py
+++ b/api/users.py
@@ -10,6 +10,15 @@
 from flask import request
 import sqlite3

+def get_user(username):
+    conn = sqlite3.connect("app.db")
+    cursor = conn.cursor()
+    query = "SELECT * FROM users WHERE username = '" + username + "'"
+    cursor.execute(query)
+    result = cursor.fetchone()
+    conn.close()
+    return result
+
"""

DIFF_N_PLUS_1_QUERY = """
diff --git a/services/report.py b/services/report.py
--- a/services/report.py
+++ b/services/report.py
@@ -5,6 +5,18 @@
 from models import Order, Product
 from database import db

+def generate_sales_report():
+    orders = Order.query.all()
+    report = []
+    for order in orders:
+        product = Product.query.filter_by(id=order.product_id).first()
+        customer = Customer.query.filter_by(id=order.customer_id).first()
+        report.append({
+            "order_id": order.id,
+            "product_name": product.name,
+            "customer_name": customer.name,
+        })
+    return report
"""

DIFF_MISSING_NULL_CHECK = """
diff --git a/utils/parser.py b/utils/parser.py
--- a/utils/parser.py
+++ b/utils/parser.py
@@ -1,6 +1,14 @@
 import json

+def parse_user_input(data):
+    email = data.get("email")
+    parts = email.split("@")
+    domain = parts[1]
+    username = parts[0]
+    return {"username": username, "domain": domain}
+
+def process_config(config_str):
+    config = json.loads(config_str)
+    db_host = config["database"]["host"]
+    return db_host
"""

DIFF_BAD_STYLE = """
diff --git a/handlers/process.py b/handlers/process.py
--- a/handlers/process.py
+++ b/handlers/process.py
@@ -1,3 +1,40 @@
+def processUserDataAndValidateAndSendEmailAndLogResults(d, x, flag1, flag2):
+    r = []
+    for i in range(len(d)):
+        tmp = d[i]
+        if flag1:
+            if tmp > 100:
+                r.append(tmp * 2)
+            else:
+                if flag2:
+                    r.append(tmp + 1)
+                else:
+                    r.append(tmp)
+        else:
+            r.append(0)
+    print("DEBUG: result =", r)
+    print("TODO: remove this later")
+    q = 0
+    for j in r:
+        q = q + j
+    if q > 1000:
+        print("big number!")
+        x = x + 1
+    elif q > 500:
+        print("medium")
+        x = x + 2
+    elif q > 100:
+        print("small")
+        x = x + 3
+    else:
+        print("tiny")
+    a = q * 0.15
+    b = q * 0.85
+    print(f"tax: {a}, net: {b}")
+    return {"total": q, "tax": a, "net": b, "count": x}
"""


# ============================================================
# Test Cases
# ============================================================

@pytest.mark.asyncio
async def test_security_catches_hardcoded_secrets():
    """
    EVAL 1: The security agent should catch hardcoded API keys and passwords.
    The diff has AWS keys, a database password, and a secret key in plain text.
    """
    state = {"diff": DIFF_HARDCODED_SECRET}
    result = await security_agent(state)
    
    findings = result["findings"]
    assert len(findings) >= 1, "Security agent should find at least 1 issue in hardcoded secrets diff"
    
    # Check that at least one finding mentions secrets/credentials/key
    texts = " ".join([f.title.lower() + " " + f.explanation.lower() for f in findings])
    assert any(word in texts for word in ["secret", "hardcoded", "credential", "key", "password"]), \
        f"Findings should mention secrets/credentials. Got: {[f.title for f in findings]}"
    
    # Should be critical severity
    severities = [f.severity.value for f in findings]
    assert "critical" in severities, f"Hardcoded secrets should be critical. Got: {severities}"
    
    print(f"✅ Security agent found {len(findings)} issues in hardcoded secrets diff")


@pytest.mark.asyncio
async def test_security_catches_sql_injection():
    """
    EVAL 2: The security agent should catch SQL injection via string concatenation.
    """
    state = {"diff": DIFF_SQL_INJECTION}
    result = await security_agent(state)
    
    findings = result["findings"]
    assert len(findings) >= 1, "Security agent should find SQL injection"
    
    texts = " ".join([f.title.lower() + " " + f.explanation.lower() for f in findings])
    assert any(word in texts for word in ["sql", "injection", "concatenat", "parameterize"]), \
        f"Findings should mention SQL injection. Got: {[f.title for f in findings]}"
    
    print(f"✅ Security agent found {len(findings)} issues in SQL injection diff")


@pytest.mark.asyncio
async def test_performance_catches_n_plus_1():
    """
    EVAL 3: The performance agent should catch N+1 query pattern —
    database queries inside a for loop.
    """
    state = {"diff": DIFF_N_PLUS_1_QUERY}
    result = await performance_agent(state)
    
    findings = result["findings"]
    assert len(findings) >= 1, "Performance agent should find N+1 query pattern"
    
    texts = " ".join([f.title.lower() + " " + f.explanation.lower() for f in findings])
    assert any(word in texts for word in ["n+1", "loop", "query", "database"]), \
        f"Findings should mention N+1 or query in loop. Got: {[f.title for f in findings]}"
    
    print(f"✅ Performance agent found {len(findings)} issues in N+1 query diff")


@pytest.mark.asyncio
async def test_logic_catches_missing_null_check():
    """
    EVAL 4: The logic agent should catch that email.split("@") will crash
    if email is None (data.get("email") can return None).
    """
    state = {"diff": DIFF_MISSING_NULL_CHECK}
    result = await logic_agent(state)
    
    findings = result["findings"]
    assert len(findings) >= 1, "Logic agent should find missing null check"
    
    texts = " ".join([f.title.lower() + " " + f.explanation.lower() for f in findings])
    assert any(word in texts for word in ["null", "none", "check", "attributeerror", "nonetype"]), \
        f"Findings should mention null/None check. Got: {[f.title for f in findings]}"
    
    print(f"✅ Logic agent found {len(findings)} issues in missing null check diff")


@pytest.mark.asyncio
async def test_style_catches_bad_practices():
    """
    EVAL 5: The style agent should catch: extremely long function name,
    single-letter variable names, debug print statements, magic numbers,
    and a function over 30 lines.
    """
    state = {"diff": DIFF_BAD_STYLE}
    result = await style_agent(state)
    
    findings = result["findings"]
    assert len(findings) >= 1, "Style agent should find style issues in messy code"
    
    texts = " ".join([f.title.lower() + " " + f.explanation.lower() for f in findings])
    assert any(word in texts for word in ["name", "naming", "print", "debug", "long", "readab"]), \
        f"Findings should mention naming/debug/style issues. Got: {[f.title for f in findings]}"
    
    # Style findings should be info severity
    severities = [f.severity.value for f in findings]
    assert "info" in severities, f"Style findings should be 'info' severity. Got: {severities}"
    
    print(f"✅ Style agent found {len(findings)} issues in bad style diff")
