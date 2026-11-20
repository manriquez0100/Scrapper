with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the problematic pattern
# The problematic pattern: strip('"\\\\\\\'') - single quotes with escaped single quote
# Change to double quotes to avoid the escaping issue
content = content.replace(
    'strip(\'"\\\\\\\'")',
    'strip("\\"\\\\\\\\")'
)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed!')