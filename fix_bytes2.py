with open('main.py', 'rb') as f:
    lines = f.readlines()

# Fix line 332 (index 331) - write the correct line directly as bytes
# The correct strip should strip double quote and backslash
# In Python source: strip("\"\\\\")
# In the file bytes: strip("\"\\\\")
# The string literal in the file should be: strip("\"\\\\")
# In bytes: b'strip("\\\\\\\\")'

# The line should be:
#     query = " ".join(response.strip().strip("\"\\\\")).split())
# In bytes for the fix script:
new_line = b'        query = " ".join(response.strip().strip("\\"\\\\\\\\")).split())\n'

with open('main.py', 'rb') as f:
    lines = f.readlines()

lines[331] = new_line

with open('main.py', 'wb') as f:
    f.writelines(lines)
print('Fixed with bytes!')