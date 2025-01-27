import traceback
from turtle import ht
import requests
from urllib.parse import quote
from settings import *
from bs4 import BeautifulSoup
import json
import sys
import time
import random
import csv
from datetime import timedelta
from requests_cache import CachedSession
import os
from selenium import webdriver

webapi = None

global_cookies = [
    "Hm_lvt_78c58f01938e4d85eaf619eae71b4ed1=1655366646"
    "spversion=20130314"
    "Hm_lpvt_78c58f01938e4d85eaf619eae71b4ed1=1655366803"
    "historystock=300192%7C*%7C300360"
    "v=AwkcCSLfjxI2inPm_teXwxyRGD5mVvmwZ0khEat-h40uFSeg86YNWPeaMfs4"
]


def reset_webapi(proxy=None):
    global webapi
    if webapi is not None:
        webapi.close()
    # 进入浏览器设置
    # webapi = webdriver.Edge()
    chrome_options = webdriver.ChromeOptions()
    if proxy is not None:
        chrome_options.add_argument('--proxy-server=%s' % proxy)
    webapi = webdriver.Chrome(chrome_options=chrome_options)
    # 全局等待
    webapi.implicitly_wait(10)
    webapi.get(URL_START)
    for cookie in global_cookies:
        webapi.add_cookie(
            {'name': cookie.split("=")[0], 'value': cookie.split("=")[1]}
        )


reset_webapi()


def cache_filter(response: requests.Response):
    text = response.text
    return "window.location.href=" not in text


session = CachedSession(
    os.path.join(os.path.join(os.environ.get('userprofile', '~'),
                 '.requests_cache'), 'ths_cache'),
    use_cache_dir=True,  # Save files in the default user cache dir
    cache_control=False,  # Use Cache-Control headers for expiration, if available
    expire_after=timedelta(days=3),  # Otherwise expire responses after one day
    allowable_methods=['GET', 'POST'],
    # Cache POST requests to avoid sending the same data twice
    # Cache 400 responses as a solemn reminder of your failures
    allowable_codes=[200, 400],
    # Don't match this param or save it in the cache
    ignored_parameters=['api_key', '.pdf'],
    match_headers=False,  # Match all request headers
    filter_fn=cache_filter,
    stale_if_error=True  # In case of request errors, use stale cache data if possible)
)


class crawl(object):

    def __init__(self):
        self.MAX_PAGE = MAX_PAGE
        self.PAGE_TRACK = PAGE_TRACK  # 跟踪次数
        self.FLAG = FLAG  # 设置标志位
        self.PAGE_LIST = PAGE_LIST  # 第一次获取失败的 html 的 列表
        self.URL_START = URL_START  # 初始链接
        self.PARAMS = PARAMS  # url 构造参数
        # self.PROXY_POOL_API = "http://127.0.0.1:5555/random"
        self.PROXY_POOL_API = "http://localhost:8889/get/"
        self.proxy_save = None  # 用于存储代理
        self.proxy_con = 0  # 用于控制代理什么时候更换
        self.fieldnames = ['代码', '名称', '现价', '涨跌幅']
        self.file = open("ths.csv", 'a', newline='')  # 打开文件
        self.writer = csv.DictWriter(self.file, fieldnames=self.fieldnames)
        self.writer.writeheader()
        self.basic_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Cookie": "; ".join(global_cookies),
            "hexin-v": "AwkcCSLfjxI2inPm_teXwxyRGD5mVvmwZ0khEat-h40uFSeg86YNWPeaMfs4",
            "Host": "q.10jqka.com.cn",
            "Pragma": "no-cache",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.5005.63 Safari/537.36 Edg/102.0.1245.39",
            "X-Requested-With": "XMLHttpRequest"
        }

    def proxy_get(self, num_retries=2):
        """
        #代理获取模块

        """
        # return {
        #     "http": "http://router.chiro.work:7890",
        #     "https": "http://router.chiro.work:7890"
        # }
        try:
            r_proxy = requests.get(self.PROXY_POOL_API, timeout=5)
            proxy_text = r_proxy.text  # 指定代理
            print(f"proxy_text: {proxy_text}")
            proxy = json.loads(proxy_text)
            print("代理是", proxy)
            proxies = {
                "http": 'http://' + proxy['proxy'],
                "https": 'https://' + proxy['proxy'],
            }
            return proxies
        except Exception as e:
            raise e
            if num_retries > 0:
                print("代理获取失败，重新获取")
                self.proxy_get(num_retries-1)

    def url_yield(self):
        """
        :func 用于生成url
        :yield items
        """
        for i in range(1, self.MAX_PAGE + 1):
            self.PAGE_TRACK = i  # 页面追踪
            self.FLAG += 1  # 每次加1
            print('FLAG 是：', self.FLAG)
            url = "{}{}{}".format(self.URL_START, i, self.PARAMS)
            yield url

    def url_omi(self):
        print("开始补漏")
        length_pl = len(self.PAGE_LIST)
        if length_pl != 0:  # 判断是否为空
            for i in range(length_pl):
                self.PAGE_TRACK = self.PAGE_LIST.pop(0)  # 构造一个动态列表, 弹出第一个元素
                url = "{}{}{}".format(
                    self.URL_START, self.PAGE_TRACK, self.PARAMS)
                yield url

    def downloader(self, url, num_retries=3):
        if self.proxy_con == 0:
            proxies = self.proxy_get()  # 获取代理
        else:
            proxies = self.proxy_save  # 继续使用代理
        self.proxy_save = proxies  # 更换代理值
        headers_list = [
            {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
                'Accept-Encoding': 'gzip, deflate',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
                'Connection': 'keep-alive',
                'Cookie': 'Hm_lvt_78c58f01938e4d85eaf619eae71b4ed1=1655366646; spversion=20130314; historystock=300192%7C*%7C300360; vvvv=1; v=A-P2u4zRhWGODElVKubuSD0iciyI2HcasWy7ThVAP8K5VA3SnagHasE8S58m',
                # 'hexin-v': 'AiDRI3i0b1qEZNNemO_FOZlE8SXqKQQBpg9Y4Jox7pbOH8oZQjnUg_YdKIHp',
                'Host': 'q.10jqka.com.cn',
                'Referer': 'http://q.10jqka.com.cn/',
                "Upgrade-Insecure-Requests": "1",
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.5005.124 Safari/537.36 Edg/102.0.1245.41',
            },
            # {'Accept': 'text/html, */*; q=0.01',
            #     'Accept-Encoding': 'gzip, deflate, sdch',
            #     'Accept-Language': 'zh-CN,zh;q=0.8',
            #     'Connection': 'keep-alive',
            #     'Cookie': 'user=MDq62tH9NUU6Ok5vbmU6NTAwOjQ2OTU0MjA4MDo3LDExMTExMTExMTExLDQwOzQ0LDExLDQwOzYsMSw0MDs1LDEsNDA7MSwxLDQwOzIsMSw0MDszLDEsNDA7NSwxLDQwOzgsMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDEsNDA6Ojo6NDU5NTQyMDgwOjE1MzM5OTg4OTc6OjoxNTMzOTk4ODgwOjg2NDAwOjA6MTEwOTNhMzBkNTAxMWFlOTg0OWM1MzVjODA2NjQyMThmOmRlZmF1bHRfMjox; userid=459542080; u_name=%BA%DA%D1%FD5E; escapename=%25u9ed1%25u59965E; ticket=658289e5730da881ef99b521b65da6af; log=; Hm_lvt_78c58f01938e4d85eaf619eae71b4ed1=1533992361,1533998469,1533998895,1533998953; Hm_lpvt_78c58f01938e4d85eaf619eae71b4ed1=1533998953; v=AibgksC3Qd-feBV7t0kbK7PCd5e-B2rBPEueJRDPEskkk8xLeJe60Qzb7jDj', 'hexin-v': 'AiDRI3i0b1qEZNNemO_FOZlE8SXqKQQBpg9Y4Jox7pbOH8oZQjnUg_YdKIHp',
            #     'Host': 'q.10jqka.com.cn',
            #             'Referer': 'http://q.10jqka.com.cn/',
            #             'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36',
            #  },
            # {'Accept': 'text/html, */*; q=0.01', 'Accept-Encoding': 'gzip, deflate, sdch', 'Accept-Language': 'zh-CN,zh;q=0.8', 'Connection': 'keep-alive', 'Cookie': 'user=MDq62sm9wM%2FR%2FVk6Ok5vbmU6NTAwOjQ2OTU0MTY4MTo3LDExMTExMTExMTExLDQwOzQ0LDExLDQwOzYsMSw0MDs1LDEsNDA7MSwxLDQwOzIsMSw0MDszLDEsNDA7NSwxLDQwOzgsMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDEsNDA6Ojo6NDU5NTQxNjgxOjE1MzM5OTg0NjI6OjoxNTMzOTk4NDYwOjg2NDAwOjA6MTAwNjE5YWExNjc2NDQ2MGE3ZGYxYjgxNDZlNzY3ODIwOmRlZmF1bHRfMjox; userid=459541681; u_name=%BA%DA%C9%BD%C0%CF%D1%FDY; escapename=%25u9ed1%25u5c71%25u8001%25u5996Y; ticket=4def626a5a60cc1d998231d7730d2947; log=; Hm_lvt_78c58f01938e4d85eaf619eae71b4ed1=1533992361,1533998469; Hm_lpvt_78c58f01938e4d85eaf619eae71b4ed1=1533998496; v=AvYwAjBHsS9PCEXLZexL20PSRyfuFzpQjFtutWDf4ll0o5zbyKeKYVzrvsAz',
            #  'hexin-v': 'AiDRI3i0b1qEZNNemO_FOZlE8SXqKQQBpg9Y4Jox7pbOH8oZQjnUg_YdKIHp', 'Host': 'q.10jqka.com.cn', 'Referer': 'http://q.10jqka.com.cn/', 'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36', 'X-Requested-With': 'XMLHttpRequest'},
            # {'Accept': 'text/html, */*; q=0.01', 'Accept-Encoding': 'gzip, deflate, sdch', 'Accept-Language': 'zh-CN,zh;q=0.8', 'Connection': 'keep-alive', 'Cookie': 'Hm_lvt_78c58f01938e4d85eaf619eae71b4ed1=1533992361; Hm_lpvt_78c58f01938e4d85eaf619eae71b4ed1=1533992361; user=MDq62sm9SnpsOjpOb25lOjUwMDo0Njk1NDE0MTM6NywxMTExMTExMTExMSw0MDs0NCwxMSw0MDs2LDEsNDA7NSwxLDQwOzEsMSw0MDsyLDEsNDA7MywxLDQwOzUsMSw0MDs4LDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAxLDQwOjo6OjQ1OTU0MTQxMzoxNTMzOTk4MjA5Ojo6MTUzMzk5ODE2MDo4NjQwMDowOjFlYTE2YTBjYTU4MGNmYmJlZWJmZWExODQ3ODRjOTAxNDpkZWZhdWx0XzI6MQ%3D%3D; userid=459541413; u_name=%BA%DA%C9%BDJzl; escapename=%25u9ed1%25u5c71Jzl; ticket=b909a4542156f3781a86b8aaefce3007; v=ApheKMKxdxX9FluRdtjNUdGcac08gfwLXuXQj9KJ5FOGbTKxepHMm671oBoh',
            #  'hexin-v': 'AiDRI3i0b1qEZNNemO_FOZlE8SXqKQQBpg9Y4Jox7pbOH8oZQjnUg_YdKIHp', 'Host': 'q.10jqka.com.cn', 'Referer': 'http://q.10jqka.com.cn/', 'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36', 'X-Requested-With': 'XMLHttpRequest'},

            # self.basic_headers
        ]

        try:
            time.sleep(random.random()*5)  # 设置延时
            headers = random.choice(headers_list)
            # r = requests.get(url, headers=headers, proxies=proxies, timeout=4)
            r = session.get(url, headers=headers, proxies=proxies, timeout=4)
        except KeyboardInterrupt as e:
            raise e
        except Exception as e:
            if num_retries > 0:
                print("重新下载")
                self.proxy_con = 0  # 更换代理
                self.downloader(url, num_retries-1)
            else:
                if not self.PAGE_TRACK in self.PAGE_LIST:  # 首先应该判断 该页是否存在列表中，如果不存在， 则将其加入其中
                    # 将获取失败的url保存起来，后面再次循环利用，将元素添加在末尾，
                    self.PAGE_LIST.append(self.PAGE_TRACK)
        else:
            return r.text

    def items_return(self):
        sys.setrecursionlimit(5000)
        count = 0
        while True:
            if self.FLAG < self.MAX_PAGE:
                url_list = self.url_yield()  # 获取url
            else:
                url_list = self.url_omi()
                if len(PAGE_LIST) == 0:
                    break
            print("执行到了获取模块")

            for url in url_list:
                # html = self.downloader(url)
                if self.proxy_con == 0:
                    proxies = self.proxy_get()  # 获取代理
                else:
                    proxies = self.proxy_save  # 继续使用代理
                self.proxy_save = proxies  # 更换代理值
                reset_webapi(proxy=proxies['http'])
                webapi.get(url)
                html = webapi.execute_script(
                    "return document.documentElement.outerHTML")
                # 打印提示信息
                print('URL is:', url)
                items = {}  # 建立一个空字典，用于信息存储
                try:
                    soup = BeautifulSoup(html, 'lxml')
                    for tr in soup.find('tbody').find_all('tr'):
                        td_list = tr.find_all('td')
                        items['代码'] = td_list[1].string
                        items['名称'] = td_list[2].string
                        items['现价'] = td_list[3].string
                        items['涨跌幅'] = td_list[4].string
                        self.writer.writerow(items)
                        print(items)
                        print("保存成功")
                        # 如果保存成功，则继续使用代理
                        self.proxy_con = 1
                        # print("解析成功")
                        # yield items          #将结果返回
                except KeyboardInterrupt as e:
                    raise e
                except Exception as e:
                    print(f"解析失败: {e}")
                    print(html)
                    # # 尝试用 Edge 打开，更新 Cookie
                    # webapi.delete_all_cookies()  # 删除selenium侧的所有cookies
                    # for k, v in session.cookies.items():  # 获取requests侧的cookies
                    #     print(f"will add cookie({k}: {v})")
                    #     # 向selenium侧传入以requests侧cookies的name为键value为值的字典
                    #     webapi.add_cookie({'name': k, 'value': v})
                    # webapi.get(url)
                    # html = webapi.execute_script(
                    #     "return document.documentElement.outerHTML")
                    # print(f"html on edge: {html}")
                    # sel_cookies = webapi.get_cookies()  # 获取selenium侧的cookies
                    # print(sel_cookies)
                    # jar = requests.cookies.RequestsCookieJar()  # 先构建RequestsCookieJar对象
                    # for i in sel_cookies:
                    #     # 将selenium侧获取的完整cookies的每一个cookie名称和值传入RequestsCookieJar对象
                    #     # domain和path为可选参数，主要是当出现同名不同作用域的cookie时，为了防止后面同名的cookie将前者覆盖而添加的
                    #     jar.set(i['name'], i['value'],
                    #             domain=i['domain'], path=i['path'])
                    # session.cookies.update(jar)
                    # html = self.downloader(url)
                    # print(f"html after update: {html}")
                    raise e
                    # 解析失败，则将代理换掉
                    self.proxy_con = 0
                    if not self.PAGE_TRACK in self.PAGE_LIST:
                        self.PAGE_LIST.append(self.PAGE_TRACK)
                    else:
                        count += 1
                time.sleep(5)

            if count == 2:
                break


if __name__ == '__main__':
    app = crawl()
    try:
        app.items_return()  # 打印最后的结果
    except Exception as e:
        # webapi.close()
        raise e
