import json

# 读取 JSON 文件
with open('13132去重.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 假设你的 JSON 数据是一个列表，每个元素是包含 instruction 和 title 的字典
# 这里根据实际 JSON 结构调整遍历逻辑
filtered_data = []
for item in data:
    instruction = item.get('instruction', '')
    title = item.get('output', '')  # 假设存在 title 字段，若结构不同需调整
    if 4000 >= len(instruction) > 200 and len(title) >= 40:
        filtered_data.append(item)

# 将处理后的数据写入新文件
with open('13132条去重压缩.json', 'w', encoding='utf-8') as f:
    json.dump(filtered_data, f, ensure_ascii=False, indent=2)

print("筛选前的数据条数：", len(data))
print("过滤完成，结果已保存到 13132条去重压缩.json")
print("筛选后的数据条数：", len(filtered_data))