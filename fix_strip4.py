with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix line 332 - the strip should be strip('"\'')
# Current: strip('"\'\'') - wrong
# Should be: strip('"\'') - which in source is: strip('"\\\'')
# The literal string is: " \ '  (double quote, backslash, single quote)
# In Python source: '"\\\'')  -- single quote starts, then escaped double quote, escaped backslash, escaped single quote, ends with single quote

for i, line in enumerate(lines):
    if "strip('\"\\'')" in line:
        # Replace the problematic strip with correct one
        lines[i] = line.replace("strip('\"\\'')", "strip('\"\\\\')")
        print(f"Fixed line {i+1}: {repr(lines[i])}")

with open('main.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Fixed!')