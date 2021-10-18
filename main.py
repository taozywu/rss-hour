import feedparser
import time
import os
import re
import pytz
from datetime import datetime
import yagmail
import requests
import markdown
import json
import shutil
from urllib.parse import urlparse
from multiprocessing import Pool,  Manager


def get_rss_info(feed_url, index, rss_info_list):
    result = {"result": []}
    request_success = False
    # 如果请求出错,则重新请求,最多五次
    for i in range(3):
        if(request_success == False):
            try:
                headers = {
                    # 设置用户代理头(为狼披上羊皮)
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36",
                    "Content-Encoding": "gzip"
                }
                # 三次分别设置8, 16, 24秒钟超时
                feed_url_content = requests.get(feed_url,  timeout= (i+1)*8 ,headers = headers).content
                feed = feedparser.parse(feed_url_content)
                feed_entries = feed["entries"]
                feed_entries_length = len(feed_entries)
                print("==feed_url=>>", feed_url, "==len=>>", feed_entries_length)
                for entrie in feed_entries[0: feed_entries_length-1]:
                    title = entrie["title"]
                    link = entrie["link"]
                    date = time.strftime("%Y-%m-%d", entrie["published_parsed"])

                    title = title.replace("\n", "")
                    title = title.replace("\r", "")

                    result["result"].append({
                        "title": title,
                        "link": link,
                        "date": date
                    })
                request_success = True
            except Exception as e:
                print(feed_url+"第+"+str(i)+"+次请求出错==>>",e)
                pass
        else:
            pass

    rss_info_list[index] = result["result"]
    print("本次爬取==》》", feed_url, "<<<===", index, result["result"])
    # 剩余数量
    remaining_amount = 0

    for tmp_rss_info_atom in rss_info_list:
        if(isinstance(tmp_rss_info_atom, int)):
            remaining_amount = remaining_amount + 1
            
    print("当前进度 | 剩余数量", remaining_amount, "已完成==>>", len(rss_info_list)-remaining_amount)
    return result["result"]
    
def send_mail(email, title, contents):
    # 判断secret.json是否存在
    user = ""
    password = ""
    host = ""
    try:
        if(os.environ["USER"]):
            user = os.environ["USER"]
        if(os.environ["PASSWORD"]):
            password = os.environ["PASSWORD"]
        if(os.environ["HOST"]):
            host = os.environ["HOST"]
    except:
        print("无法获取github的secrets配置信息,开始使用本地变量")
        if(os.path.exists(os.path.join(os.getcwd(),"secret.json"))):
            with open(os.path.join(os.getcwd(),"secret.json"),'r') as load_f:
                load_dict = json.load(load_f)
                user = load_dict["user"]
                password = load_dict["password"]
                host = load_dict["host"]
        else:
            print("无法获取发件人信息")
    
    # 连接邮箱服务器
    yag = yagmail.SMTP(user = user, password = password, host=host)
    # 发送邮件
    yag.send(email, title, contents)

def replace_readme():
    new_edit_readme_md = ["", ""]
    current_date_news_index = [""]
    
    # 读取EditREADME.md
    print("replace_readme")
    new_num = 0
    with open(os.path.join(os.getcwd(),"EditREADME.md"),'r') as load_f:
        edit_readme_md = load_f.read();
        new_edit_readme_md[0] = edit_readme_md
        #print("ddd=="+edit_readme_md)
        before_info_list =  re.findall(r'\[订阅地址\]\((.*)\)' ,edit_readme_md);
        # 填充统计RSS数量
        new_edit_readme_md[0] = new_edit_readme_md[0].replace("{{rss_num}}", str(len(before_info_list)))
        # 填充统计时间
        ga_rss_datetime = datetime.fromtimestamp(int(time.time()),pytz.timezone('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S')
        new_edit_readme_md[0] = new_edit_readme_md[0].replace("{{ga_rss_datetime}}", str(ga_rss_datetime))

        # 使用进程池进行数据获取，获得rss_info_list
        before_info_list_len = len(before_info_list)
        rss_info_list = Manager().list(range(before_info_list_len))
        print('初始化完毕==》', rss_info_list)

        
        # 创建一个最多开启8进程的进程池
        po = Pool(8)

        for index, before_info in enumerate(before_info_list):
            # 获取link
            link = before_info
            po.apply_async(get_rss_info,(link, index, rss_info_list))


        # 关闭进程池,不再接收新的任务,开始执行任务
        po.close()

        # 主进程等待所有子进程结束
        po.join()
        print("----结束----", rss_info_list)


        for index, before_info in enumerate(before_info_list):
            # 获取link
            link = before_info
            # 生成超链接
            rss_info = rss_info_list[index]
            wx_content = ""
            parse_result = urlparse(link)
            scheme_netloc_url = str(parse_result.scheme)+"://"+str(parse_result.netloc)

            # 加入到索引
            try:
                for rss_info_atom in rss_info:
                    if (rss_info_atom["date"] == datetime.today().strftime("%Y-%m-%d")):
                        if new_num > 0 and new_num % 14 == 0:
                            send_qyweixin(wx_content)
                            wx_content = ""
                         
                        wx_content = wx_content + rss_info_atom["title"] + rss_info_atom["link"] + "<br/>\n"
                        new_num = new_num + 1
                        current_date_news_index[0] = current_date_news_index[0] + rss_info_atom["title"] + rss_info_atom["link"] + "<br/>\n"

            except:
                print("An exception occurred")
           
    
    # 替换EditREADME中的索引
    new_edit_readme_md[0] = new_edit_readme_md[0].replace("{{news}}", current_date_news_index[0])
    # 替换EditREADME中的新文章数量索引
    new_edit_readme_md[0] = new_edit_readme_md[0].replace("{{new_num}}", str(new_num))
        
    # 将新内容
    with open(os.path.join(os.getcwd(),"README.md"),'w') as load_f:
        load_f.write(new_edit_readme_md[0])
    
    new_edit_readme_md[1] = current_date_news_index[0]

    return new_edit_readme_md


def get_email_list():
    email_list = []
    with open(os.path.join(os.getcwd(),"tasks.json"),'r') as load_f:
        load_dic = json.load(load_f)
        for task in load_dic["tasks"]:
            email_list.append(task["email"])
    return email_list

def send_qyweixin(content):
    url = "https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token=" + get_qyweixin_token(os.environ["GROUP_ID"], os.environ["GROUP_APP_SECRET"])
    values = {
               "touser"  : "@all",
               "msgtype" : "text",
               "agentid" : 1000002,
               "text"    : {
                            "content" : content
               },
               "safe"    :"0"
    }
    send_data = json.dumps(values)
    r = requests.post(url, send_data)
    
    if r.json().get('errcode') == 0:
        print('发送消息成功')
    
def get_qyweixin_token(corpid, corpsecret):
    url = 'https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid=%s&corpsecret=%s' % (corpid, corpsecret)
    r = requests.get(url)
    return r.json().get('access_token')

def main():
    readme_md = replace_readme()
    email_list = get_email_list()

    mail_re = r'邮件内容区开始>([.\S\s]*)<邮件内容区结束'
    reResult = re.findall(mail_re, readme_md[0])

    try:
        send_mail(email_list, "Rss", readme_md[1])
    except Exception as e:
        print("==发送邮件失败==》》", e)

if __name__ == "__main__":
    main()
