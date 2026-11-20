with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the problematic strip with double-quoted version
# Old: strip('"\\\\\\\'') - uses single quotes, has escaping issues
# New: strip("\"\\\\") - uses double quotes, avoids single quote escaping
# This strips double quote and backslash, which is the main intent

old = 'strip(\'"\\\\\\\'")'
new = 'strip("\"\\\\\\\\")'

if old in content:
    content = content.replace(old, new)
    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Replaced successfully!')
else:
    print('Pattern not found')
    # Find the actual pattern
    idx = content.find('strip(')
    if idx >= 0:
        print(repr(content[idx:idx+80]))