with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix line 332 - the strip should be strip('"\'')
# Current: strip('"\'\'') 
# Should be: strip('"\'')  -- which in source is: strip('"\'')
# In Python source: the string literal is '"\\\''
# So the line should be: strip('"\\\'')

for i, line in enumerate(lines):
    if "strip('\"\\'')" in line:
        lines[i] = line.replace("strip('\"\\'')", 'strip(\'"\\\\\')')
        print(f"Fixed line {i+1}")

with open('main.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Fixed!')