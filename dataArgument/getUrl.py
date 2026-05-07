with open('./url.txt','w', encoding='utf-8') as f:
    pn = 1
    for url in range(32, 83):
        #后面唯一会变的就只是pn={other}，和后两位的{url}

        str = f'https://edit.mgyxw.cn/mdls/am/amList.ashx?call=ArticleMore&st=_H&mid=9396&ct=mk&mh=345&cnt=39&pn={pn}&_=17621689914{url}'
        f.write(str)
        f.write('\n')
        pn += 1

# 如果， 第一页url后两位是 44，我要爬取全部76页所有的内容
# for  url in range(44, 44+76):


# 网址还在读取的时候，不要运行，等下面爬完在弄
# 这里的url有时有坑，这边要注意 &pn={other}&_=17621398595{url}
# {url}过了100以后会再从00 01 这样不会101,102 并且{url}前面的5会变为6 这个要算一下
#    这里注意下, 分俩步走  手动-1


# 数据采集完后会有一个save.json文件，里面全是数据，再执行这个clearData这个脚本清除一下数据，清除之后会有个save_cleaned.json的文件，里面有你想要的数据


