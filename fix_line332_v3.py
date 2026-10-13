with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# The correct line should be:
# query = " ".join(response.strip().strip('"\\\'').split())
# In the source file, this line is written as:
#     query = " ".join(response.strip().strip('"\\\'').split())
# The string literal '"\\\'') is represented in the source file as:
#   single quote, escaped double quote, escaped backslash, escaped single quote, close paren
#   which in the file is: '"\\\'')
# But the actual line in the file shows: strip('"\'') - which is wrong

# The correct Python source for the strip argument '"\\\'':
# - Starts with single quote: '
# - Escaped double quote: \"
# - Escaped backslash: \\
# - Escaped single quote: \'
# - Ends with single quote: '
# So in the source file it's written as: '"\\\'')
# And in the actual file it appears as: strip('"\\\'')

# The current broken line is: strip('"\\')
# Which in repr is: 'strip(\'"\\\\')'
# We need: strip('"\\\'')  which in repr is: strip('"\\\\\'')

lines[331] = '        query = " ".join(response.strip().strip(\'"\\\\\\\'')).split())\n'

with open('main.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Fixed line 332!')