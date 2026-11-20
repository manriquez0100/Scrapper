with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# The correct line needs strip('"\\\'')
# In Python source: strip('"\\\\\'')
# In the file, this is written with escaped backslashes: strip('"\\\\\'')
# So the line should be:
#     query = " ".join(response.strip().strip('"\\\\\'')).split())
# Which in the source file is written as:
new_line = '        query = " ".join(response.strip().strip(\'"\\\\\\\'')).split())\n'

with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

lines[331] = new_line

with open('main.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Fixed!')