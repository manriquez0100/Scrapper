# Fix the strip string literal issue
with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# The problematic line has: strip('"\\\\\\\'') 
# The issue is the escaped single quote \' which terminates the string early
# We need to change it to use a different approach

# Option 1: Use double quotes for the strip argument
# strip("""\\\\") - this strips double quote and backslash
# This avoids the single quote escaping issue

# Find the problematic line and fix it
import re

# Pattern to find the problematic line
pattern = r'(query = " ".join\(response\.strip\(\)\.strip\().*?(\.split\(\))'

def fix_strip(match):
    before = match.group(1)
    after = match.group(2)
    return before + 'strip("\\"\\\\\\\\")' + after

# Try a simpler approach - just replace the specific problematic pattern
content = content.replace(
    'strip(\'"\\\\\\\'")',
    'strip("\"\\\\\\\\")'
)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed!')