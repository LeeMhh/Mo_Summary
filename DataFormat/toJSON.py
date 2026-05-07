import json
import re
import sys

"""
终极方案：不再依赖 { } 结构，而是直接扫描字段并重建 JSON 对象
适用于 “内容碎片化严重 / JSON 已经不存在 / 必须提取字段” 情况
"""

def reconstruct_from_text(text):
    # 匹配 t 字段，例如:  "t": "xxx"
    t_pattern = re.compile(r'"?t"?\s*:\s*"([^"]*)"')
    # 匹配 s 字段
    s_pattern = re.compile(r'"?s"?\s*:\s*"([^"]*)"')

    # 扫描所有 t 和 s 的出现位置
    t_matches = list(t_pattern.finditer(text))
    s_matches = list(s_pattern.finditer(text))

    print(f"找到 t 字段: {len(t_matches)}")
    print(f"找到 s 字段: {len(s_matches)}")

    results = []

    # 将它们按顺序组装
    # 假设 t 与 s 在文件中依次出现（这是最常见格式）
    count = min(len(t_matches), len(s_matches))

    for i in range(count):
        t_val = t_matches[i].group(1)
        s_val = s_matches[i].group(1)

        results.append({
            "t": t_val,
            "s": s_val
        })

    return results


def process_file(input_path, output_path):
    print("📖 读取 TXT 文件...")
    with open(input_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    print("🔍 扫描字段并重建 JSON ...")
    data = reconstruct_from_text(text)

    print(f"✅ 成功重建 {len(data)} 条 JSON 对象")

    print("💾 写入输出...")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("🎉 完成！输出文件:", output_path)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: python 变JSON.py merged_R4.txt output.json")
        sys.exit(1)

    process_file(sys.argv[1], sys.argv[2])
