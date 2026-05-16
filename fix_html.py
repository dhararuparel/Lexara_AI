content = open('templates/index.html', encoding='utf-8').read()
# Truncate at first </html>
idx = content.find('</html>')
clean = content[:idx+7]
open('templates/index.html', 'w', encoding='utf-8').write(clean)
print('Fixed. Length:', len(clean))
