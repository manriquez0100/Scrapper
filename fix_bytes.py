with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Write the correct line directly using a raw string approach
# The target line in the file should be:
#     query = " ".join(response.strip().strip('"\\\'')).split())
# In the Python source file, this is written with proper escaping

# Use a bytes approach to write the exact line
line_bytes = b'        query = " ".join(response.strip().strip(\'"\\\\\\\'")).split())\n'
new_line = line_bytes.decode('utf-8')

with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

lines[331] = new_line

with open('main.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Fixed!')