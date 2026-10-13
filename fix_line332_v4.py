with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix line 332 - the strip should be strip('"\'')
# The string literal '"\\\'') in Python source:
# - starts with single quote
# - escaped double quote: \"
# - escaped backslash: \\
# - escaped single quote: \'
# - ends with single quote and closing paren

lines[331] = '        query = " ".join(response.strip().strip(\'"\\\\\\\'')).split())\n'

with open('main.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Fixed line 332!')