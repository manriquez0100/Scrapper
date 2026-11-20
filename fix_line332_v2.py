with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# The issue is the extra closing parenthesis
# Current: strip('"\\')) -- has extra )
# Should be: strip('"\\\')  -- wait, let me think
# The strip argument should be the string: " \ '  (3 chars: double quote, backslash, single quote)
# In Python source: '"\\\'')  -- that's the literal string + closing paren
# Wait, the line is: response.strip().strip('"\\\'').split()
# The strip argument is '"\\\'' (the string literal inside strip)
# In source code: strip('"\\\'')  -- single quote, escaped double, escaped backslash, escaped single quote, close single quote
# Then .split() follows

lines[331] = '        query = " ".join(response.strip().strip(\'"\\\\\')).split())\n'

with open('main.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Fixed!')