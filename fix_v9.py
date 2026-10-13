with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix line 332 directly
# The correct line should be:
# query = " ".join(response.strip().strip('"\\\'')).split())
# In source file: strip('"\\\'')
# This avoids the escaping nightmare by using the correct escape sequence

# The correct line (index 331):
lines[331] = '        query = " ".join(response.strip().strip(\'"\\\\\\\'')).split())\n'

with open('main.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Fixed line 332!')