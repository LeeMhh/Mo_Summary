import json
import re

with open('更新摘要后的数据集/26257条强化.json', 'r', encoding='utf-8') as f:
    data = json.load(f)


# 定义要删除的各种空格和不可见字符
def clean_text(text):
    if not isinstance(text, str):
        return text

    # 替换各种空格和不可见字符
    text = text.replace('\r\n', '')  # 换行符
    text = text.replace('\n', '')  # 换行符
    text = text.replace('\r', '')  # 回车符
    text = text.replace('\t', '')  # 制表符
    text = text.replace('\u00A0', '')  # 非断空格 (NBSP)
    text = text.replace('\u200B', '')  # 零宽度空格
    text = text.replace('\u200C', '')  # 零宽度非连接符
    text = text.replace('\u200D', '')  # 零宽度连接符
    text = text.replace('\uFEFF', '')  # 零宽度无断空格

    # 使用正则表达式删除所有不可见控制字符
    text = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', text)

    return text


# 处理每个条目
for item in data:
    if isinstance(item, dict) and item:  # 确保是字典且不为空
        # 处理output字段
        if 'output' in item:
            item['output'] = clean_text(item['output'])

        # 处理instruction字段
        if 'instruction' in item:
            item['instruction'] = clean_text(item['instruction'])

        # 处理input字段
        if 'input' in item:
            item['input'] = clean_text(item['input'])

# 保存处理后的数据
with open('蒙文_clean.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("处理完成！清理了各种空格和不可见字符。")