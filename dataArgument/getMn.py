import json
import re

import aiohttp
import asyncio

from bs4 import BeautifulSoup

headers = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
}


# 编码处理函数
async def decode_response_content(content_bytes, url=""):
    """处理响应内容的编码问题"""
    encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'big5', 'iso-8859-1']
    response_text = None

    for encoding in encodings:
        try:
            response_text = content_bytes.decode(encoding)
            break  # 如果解码成功，跳出循环
        except UnicodeDecodeError:
            continue  # 如果解码失败，尝试下一种编码

    # 如果所有编码都失败，使用替换错误字符的方式
    if response_text is None:
        response_text = content_bytes.decode('utf-8', errors='replace')
        if url:
            print(f"警告: 使用错误替换方式处理URL: {url}")

    return response_text


def remove(text):
    # 过滤 xx记者摄、图为xx、xx供图、新华社xx
    pattern = r'''
        [^\s,。]+ᠰᠤᠷᠪᠤᠯᠵᠢᠯᠠᠭᠴᠢᠰᠡᠭᠦᠳᠡᠷᠯᠡᠪᠡ 
        |ᠵᠢᠷᠤᠭ[^,。\s]+
        |[^,。\s]+ᠵᠢᠷᠤᠭᠬᠠᠩᠭᠠᠬᠤ
        |ᠰᠢᠨᠬᠤᠸᠠ ᠬᠣᠷᠢᠶᠠᠨ᠎ᠤ᠋ᠡᠳᠡᠭᠡ
    '''
    result = re.sub(pattern, '', text, flags=re.VERBOSE | re.UNICODE)
    result = re.sub(r'\s+', ' ', result).strip()
    return result


firstUrl = ''
listUrlList = []
# 数据的url地址 集合
with open('./bbb', 'r', encoding='utf-8') as f:
    listUrlList = [line.strip() for line in f.readlines()]

# 所有的子链接
allChildUrls = set()


async def dealURL(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            try:
                print(url)
                resp = await resp.read()
                response_text = await decode_response_content(resp, url)
                json_str = response_text.split('(')[1].replace(')', '') if '(' in response_text else response_text
                data = json.loads(json_str)
                if 'mk_Contents' in data:
                    for item in data['mk_Contents']:
                        mk_url = item.get('mk_URL')
                        if mk_url:
                            full_url = f"https://www.mgyxw.cn/{mk_url}"
                            allChildUrls.add(full_url)
            except Exception as e:
                print(f"获取遗落页面失败 {url}: {e}")


async def dealNewsInfo(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            try:
                content_bytes = await resp.read()
                response_text = await decode_response_content(content_bytes, url)

                soup = BeautifulSoup(response_text, 'html.parser')
                # 解析API返回的JSON
                title_tag = soup.select_one('.mkh_lrtb')
                if not title_tag:
                    return None
                cleaned_title = remove(title_tag.text)
                if not cleaned_title:  # 跳过空标题
                    return None
                # 提取内容
                content_tags = soup.select('.mkh_ctt p')
                content = '\n\n'.join([p.text for p in content_tags]) if content_tags else ""
                if 4000 >= len(content) > 200 and len(cleaned_title) >= 40:
                    # 限制长度范围
                    return cleaned_title, content
            except Exception as e:
                print(f"获取文章内容失败 {url}: {e}")
                return None


allData = []


async def main():
    print("开始收集链接...")

    # 更保守的并发控制
    semaphore = asyncio.Semaphore(3)  # 同时最多3个请求

    async def bounded_dealURL(url):
        async with semaphore:
            return await dealURL(url)

    # 处理列表URL
    for i, url in enumerate(listUrlList):
        print(f"处理列表URL {i + 1}/{len(listUrlList)}")
        await bounded_dealURL(url)

    print(f"共收集到 {len(allChildUrls)} 个链接")
    print("开始爬取文章内容...")

    # 逐个处理文章URL，避免并发过高
    for i, url in enumerate(allChildUrls):
        print(f"处理文章 {i + 1}/{len(allChildUrls)}: {url}")
        result = await dealNewsInfo(url)
        if result:
            title, content = result
            dist = {
                'instruction': content,
                'input': "",
                'output': title
            }
            allData.append(dist)
        # 每五条
        if (i + 1) % 5 == 0:
            # 睡眠五秒
            await asyncio.sleep(5)

    # 保存数据
    with open('../数据4.json', 'w', encoding='utf-8') as f:
        json.dump(allData, f, ensure_ascii=False, indent=2)

    print(f"爬取完成，共获取 {len(allData)} 篇有效文章")


if __name__ == '__main__':
    asyncio.run(main())
