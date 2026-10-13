with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix line 332 (index 331) - directly replace the line
# Current: strip('"\'\'') -> should be strip('"\'')
# The correct strip string literal: '"\\\''
# In source: 'strip(\'"\\\\\')')  -- wait, let me think
# The string literal we want is: double quote, backslash, single quote
# In Python source: '"\\\'')  (single quote, escaped double quote, escaped backslash, escaped single quote, close paren, single quote)
# So the line should be: strip('"\\\'')  which in source is written as: strip('"\\\'')

lines[331] = '        query = " ".join(response.strip().strip(\'"\\\\\')).split())\n'

with open('main.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Fixed line 332!')