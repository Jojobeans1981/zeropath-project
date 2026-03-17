from app.scanner.taint_analyzer import analyze_file_taint, get_pre_findings


def test_sql_injection_detection():
    code = '''
from flask import Flask, request
import sqlite3

app = Flask(__name__)

@app.route('/users')
def get_users():
    name = request.args.get('name')
    conn = sqlite3.connect('db.sqlite')
    cursor = conn.cursor()
    query = "SELECT * FROM users WHERE name = '" + name + "'"
    cursor.execute(query)
    return str(cursor.fetchall())
'''
    result = analyze_file_taint(code, 'app.py')
    findings = get_pre_findings(result)
    assert len(findings) >= 1
    assert any(f["vulnerability_type"] == "SQL Injection" for f in findings)
    assert any(f["cwe"] == "CWE-89" for f in findings)


def test_command_injection_detection():
    code = '''
from flask import Flask, request
import os

app = Flask(__name__)

@app.route('/ping')
def ping():
    host = request.args.get('host')
    os.system('ping ' + host)
    return 'done'
'''
    result = analyze_file_taint(code, 'app.py')
    findings = get_pre_findings(result)
    assert len(findings) >= 1
    assert any(f["vulnerability_type"] == "Command Injection" for f in findings)
    assert any(f["cwe"] == "CWE-78" for f in findings)


def test_ssti_detection():
    code = '''
from fastapi import FastAPI, Request
import jinja2

app = FastAPI()

@app.get('/')
async def root(request: Request):
    username = request.query_params.get('username', 'World')
    output = jinja2.from_string('Welcome ' + username + '!').render()
    return output
'''
    result = analyze_file_taint(code, 'main.py')
    findings = get_pre_findings(result)
    assert len(findings) >= 1
    assert any(f["vulnerability_type"] == "Server-Side Template Injection" for f in findings)


def test_no_false_positive_on_safe_code():
    code = '''
from flask import Flask, request, render_template

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return 'About page'
'''
    result = analyze_file_taint(code, 'app.py')
    findings = get_pre_findings(result)
    assert len(findings) == 0


def test_ssrf_detection():
    code = '''
from flask import Flask, request
import requests

app = Flask(__name__)

@app.route('/fetch')
def fetch():
    url = request.args.get('url')
    resp = requests.get(url)
    return resp.text
'''
    result = analyze_file_taint(code, 'app.py')
    findings = get_pre_findings(result)
    assert len(findings) >= 1
    assert any(f["vulnerability_type"] == "Server-Side Request Forgery (SSRF)" for f in findings)


def test_deserialization_detection():
    code = '''
from flask import Flask, request
import pickle

app = Flask(__name__)

@app.route('/load')
def load():
    data = request.data
    obj = pickle.loads(data)
    return str(obj)
'''
    result = analyze_file_taint(code, 'app.py')
    findings = get_pre_findings(result)
    assert len(findings) >= 1
    assert any(f["vulnerability_type"] == "Insecure Deserialization" for f in findings)


def test_eval_injection_detection():
    code = '''
from flask import Flask, request

app = Flask(__name__)

@app.route('/calc')
def calc():
    expr = request.args.get('expr')
    result = eval(expr)
    return str(result)
'''
    result = analyze_file_taint(code, 'app.py')
    findings = get_pre_findings(result)
    assert len(findings) >= 1
    assert any(f["vulnerability_type"] == "Code Injection" for f in findings)


def test_syntax_error_handled():
    code = "def broken(:\n    pass"
    result = analyze_file_taint(code, 'broken.py')
    assert result.parse_error is not None
    assert len(result.paths) == 0


def test_cwe_ids_present():
    code = '''
from flask import Flask, request
import os

app = Flask(__name__)

@app.route('/run')
def run():
    cmd = request.args.get('cmd')
    os.system(cmd)
    return 'done'
'''
    result = analyze_file_taint(code, 'app.py')
    findings = get_pre_findings(result)
    assert all("cwe" in f for f in findings)
    assert findings[0]["cwe"] == "CWE-78"
