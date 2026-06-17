from PIL import Image
import os

os.makedirs('test_data', exist_ok=True)

test_files = [
    ('[人物][草稿]_test1.jpg', (1920, 1080)),
    ('[风景]_test2.jpg', (1920, 1080)),
    ('[草稿]_test3.png', (1920, 1080)),
    ('test4.jpg', (1920, 1080)),
    ('test5.jpg', (1920, 1080)),
]

for filename, size in test_files:
    img = Image.new('RGB', size, color='red')
    img.save(f'test_data/{filename}')

with open('test_data/brush1.abr', 'wb') as f:
    f.write(b'fake brush data 1')
with open('test_data/brush2.abr', 'wb') as f:
    f.write(b'fake brush data 2')

print('测试数据创建完成！')
