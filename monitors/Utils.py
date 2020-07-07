from datetime import datetime
import json
import threading
import requests
import time
from urllib.parse import quote

DateTimeFormat = "%Y-%m-%d %H:%M:%S %Z"


def now() -> datetime:
    return datetime.utcnow()


def timestamp() -> float:
    return now().timestamp()

# 检测推送力度
def getpushcolordic(text: str, dic: dict) -> dict:
    pushcolor_dic = {}
    for word in dic.keys():
        if word in text:
            for color in dic[word]:
                if color in pushcolor_dic:
                    pushcolor_dic[color] += int(dic[word][color])
                else:
                    pushcolor_dic[color] = int(dic[word][color])
    return pushcolor_dic


# 求和推送力度，注意传入subdics必须为tuple类型
def addpushcolordic(*adddics, **kwargs) -> dict:
    pushcolor_dic = {}
    for adddic in adddics:
        for color in adddic.keys():
            if color in pushcolor_dic:
                pushcolor_dic[color] += adddic[color]
            else:
                pushcolor_dic[color] = adddic[color]
    if "subdics" in kwargs:
        for subdic in kwargs["subdics"]:
            for color in subdic.keys():
                if color in pushcolor_dic:
                    pushcolor_dic[color] -= subdic[color]
                else:
                    pushcolor_dic[color] = -subdic[color]
    return pushcolor_dic


def waittime(timestamp: float):
    td = datetime.utcfromtimestamp(timestamp) - timestamp()
    days = td.days
    hours, rem = divmod(td.total_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return (
        f"{days}天{hours}小时{minutes}分{seconds}秒"
        if days > 0
        else f"{hours}小时{minutes}分{seconds}秒"
        if hours > 0
        else f"{minutes}分{seconds}秒"
    )


def modifypause(pause_json: list, type, id, pausepower) -> list:
    for pause in pause_json:
        if pause["type"] == type and pause["id"] == id:
            pause["pausepower"] = pausepower
            return pause_json
    pause_json.append({"type": type, "id": id, "pausepower": pausepower})
    return pause_json


# 查询暂停力度
def checkpause(pause_json: list, type, id) -> int:
    for pause in pause_json:
        if pause["type"] == type and pause["id"] == id:
            return pause["pausepower"]
    return None


# 判断是否推送
def pushall(pushtext, pushcolor_dic: dict, push_list: list):
    with open("./pause.json", "r", encoding="utf-8") as f:
        pause_json = json.load(f)
    for push in push_list:
        pausepower = checkpause(pause_json, push["type"], push["id"]) or 0
        for color in push["color_dic"]:
            if color in pushcolor_dic:
                if int(pushcolor_dic[color]) - int(pausepower) >= int(
                    push["color_dic"][color]
                ):
                    push_thread = threading.Thread(
                        args=(pushtext, push), target=pushtoall
                    )
                    push_thread.start()
                    break


# 推送
def pushtoall(pushtext: str, push: dict):
    url, headers, data = None, None, None
    port, id, bot_id, text = (
        push.get("port", None),
        push["id"],
        push.get("bot_id", None),
        quote(str(pushtext)),
    )
    # 不论windows还是linux都是127.0.0.1
    if push["type"] == "qq_user":
        url = f"http://127.0.0.1:{port}/send_private_msg?user_id={id}&message={text}"
    elif push["type"] == "qq_group":
        url = f"http://127.0.0.1:{port}/send_group_msg?group_id={id}&message={text}"
    elif push["type"] == "miaotixing":
        # 带文字推送可能导致语音和短信提醒失效
        url = f"https://miaotixing.com/trigger?id={id}&text={text}"
    elif push["type"] == "miaotixing_simple":
        url = f"https://miaotixing.com/trigger?id={id}"
    elif push["type"] == "discord":
        url = id
        headers = {"Content-Type": "application/json"}
        data = {"content": pushtext}
    elif push["type"] == "telegram":
        url = f"https://api.telegram.org/bot{bot_id}/sendMessage?chat_id=@{id}&text={text}"
    else:
        return
    pushtourl(url, headers, json.dumps(data))


# 推送到url
def pushtourl(url: str, headers: dict = None, data: dict = None):
    # if data is None:
    #     data = {}
    # if headers is None:
    #     headers = {}
    for retry in range(1, 5):
        status_code = "fail"
        try:
            response = requests.post(url, headers=headers, data=data, timeout=(3, 7))
            status_code = response.status_code
        except:
            time.sleep(5)
        finally:
            Log(f"[Info] pushtourl：第{retry}次-结果{status_code} ({url})")
            if status_code == 200 or status_code == 204:
                break
