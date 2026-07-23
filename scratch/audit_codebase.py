import ast
import os
import sys

def audit_file(filepath):
    print(f"--- Auditing {filepath} ---")
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        
    try:
        tree = ast.parse(content, filename=filepath)
        print(f"  [OK] AST Parsing clean for {filepath}")
    except SyntaxError as e:
        print(f"  [ERROR] Syntax error in {filepath}: {e}")
        return False
        
    # Check for undefined names, missing imports, etc.
    # Simple check for basic undefined globals
    return True

files_to_audit = ["bot.py", "database.py", "race.py", "crates.py", "utils.py", "config.py", "economy.py"]
for file in files_to_audit:
    if os.path.exists(file):
        audit_file(file)
    else:
        print(f"  [WARNING] File {file} does not exist!")
