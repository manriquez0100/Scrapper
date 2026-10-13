with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# The correct line: strip('"\\\'')
# In Python source: strip('"\\\\\'')
# In the file (as bytes): strip('"\\\'')
# So in the source code we write: strip('"\\\\\'')
# Which in the fix script we write as: strip('"\\\\\'')
# Wait, the outer string uses single quotes, so we need to escape the double quotes inside

# The line in the file should be:
#     query = " ".join(response.strip().strip('"\\\\\'')).split())
# In the source code of our fix script, we write:
# new_line = '        query = " ".join(response.strip().strip(\'"\\\\\\\'")).split())\n'
# Because:
# - outer string uses single quotes
# - inside we have double quotes: "
# - then backslashes: \\\\ (two backslashes in source = one in string)
# - then escaped single quote: \'
# - then close

new_line = '        query = " ".join(response.strip().strip(\'"\\\\\\\'")).split())\n'

with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

lines[331] = new_line

with open('main.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Fixed!')