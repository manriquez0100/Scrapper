with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# The correct line needs strip('"\\\'')
# In Python source, to represent the string '"\\\'':
# We write: strip('"\\\\\'')
# Because: ' " \\ \\ \' ' - the backslash is escaped as \\, the single quote is escaped as \'
new_line = '        query = " ".join(response.strip().strip(\'"\\\\\\\'")).split())\n'

with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

lines[331] = new_line

with open('main.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Fixed line 332!')