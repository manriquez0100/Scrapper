# Fix the strip string literal on line 332
with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# The correct line should have strip('\"\\\'')
# In Python source code, this is written as:
# strip('\"\\\'')  -- which means the string literal contains: " \ '
# In the source file, this is written as: strip('\"\\\'')
# But in the actual file bytes, it's stored with proper escaping

# The current broken line has: strip('"\\') which is missing the escaped single quote
# We need to fix it to have the proper escaped single quote

# The correct line should be:
#     query = " ".join(response.strip().strip('\"\\\'').split())
# In the source file, this is represented as:
# lines[331] = '        query = " ".join(response.strip().strip(\'"\\\\\\\'')).split())\n'

# Let's write the exact bytes needed:
# The string literal in Python source: '"\\\'')
# This is written in the source file as: '"\\\'') 
# Which in the file bytes is the characters: ' " \ \ ' ) 

# In Python code, to write this line in the source file:
# We need to escape the backslashes for the outer string
# The outer string uses single quotes, so we can use double quotes inside

new_line = '        query = " ".join(response.strip().strip(\'"\\\\\\\'")).split())\n'

with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

lines[331] = new_line

with open('main.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Fixed line 332!')