from . import LogLevel
import threading
import time
from pathlib import Path
import json
from urllib.parse import quote
import requests

from ..Utils import now

# 仅从cfg和cfg_mod中获取参数，不会启动子监视器
class BaseMonitor(threading.Thread):
    def __init__(self, name: str, tgt: str, tgt_name: str, cfg: dict, **cfg_mod):
        super().__init__()
        self.name = name
        self.tgt = tgt
        self.tgt_name = tgt_name

        self.interval = 60
        self.vip_dic = {}
        self.word_dic = {}
        self.cookies = {}
        self.proxy = {}
        self.push_list = []
        # 不要直接修改通过cfg引用传递定义的列表和变量，请deepcopy后再修改
        for var in cfg:
            setattr(self, var, cfg[var])
        for var in cfg_mod:
            setattr(self, var, cfg_mod[var])

        self.stop_now = False

    def initialize_log(
        self, cls_name: str, sub_dir: bool = False, has_chat: bool = False
    ):
        logpath = Path(f"./log/{cls_name}")
        if sub_dir:
            logpath = logpath / self.tgt_name

        self.logpath = logpath / f"{self.name}.txt"
        if has_chat:
            self.chatpath = logpath / f"{self.name}_chat.txt"
        if not logpath.exists():
            logpath.mkdir(parents=True)

    def checksubmonitor(self):
        pass

    def run(self):
        while not self.stop_now:
            time.sleep(self.interval)

    def stop(self):
        self.stop_now = True

    def push(self, text: str, dic: dict, lst: list):
        self.pushall(text, dic, lst)
        self.log(self.logpath, f'[Info] "{self.name}" pushall {str(dic)}\n{text}')

    @staticmethod
    # 修改暂停力度
    def modifypause(pause_json: list, type, id, pausepower) -> list:
        for pause in pause_json:
            if pause["type"] == type and pause["id"] == id:
                pause["pausepower"] = pausepower
                return pause_json
        pause_json.append({"type": type, "id": id, "pausepower": pausepower})
        return pause_json

    @staticmethod
    # 查询或修改暂停力度
    def checkpause(pause_json: list, type, id) -> int:
        for pause in pause_json:
            if pause["type"] == type and pause["id"] == id:
                return pause["pausepower"]
        return None

    # 判断是否推送
    def pushall(self, pushtext, pushcolor_dic: dict, push_list: list):
        with open("./pause.json", "r", encoding="utf-8") as f:
            pause_json = json.load(f)
        for push in push_list:
            pausepower = (
                BaseMonitor.checkpause(pause_json, push["type"], push["id"]) or 0
            )
            for color in push["color_dic"]:
                if color in pushcolor_dic:
                    if int(pushcolor_dic[color]) - int(pausepower) >= int(
                        push["color_dic"][color]
                    ):
                        push_thread = threading.Thread(
                            args=(pushtext, push), target=self.pushtoall
                        )
                        push_thread.start()
                        break

    # 推送
    def pushtoall(self, pushtext: str, push: dict):
        url, headers, data = None, None, None
        port, id, bot_id, text = (
            push.get("port", None),
            push["id"],
            push.get("bot_id", None),
            quote(str(pushtext)),
        )
        if push["type"] == "qq_user":
            url = (
                f"http://127.0.0.1:{port}/send_private_msg?user_id={id}&message={text}"
            )
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
        self.pushtourl(url, headers, json.dumps(data))

    # 推送到url
    def pushtourl(self, url: str, headers: dict = {}, data: dict = {}):
        # if data is None:
        #     data = {}
        # if headers is None:
        #     headers = {}
        for retry in range(1, 5):
            status_code = "fail"
            try:
                response = requests.post(
                    url, headers=headers, data=data, timeout=(3, 7)
                )
                status_code = response.status_code
            except:
                time.sleep(5)
            finally:
                self.log_info(
                    f"pushtourl：第{retry}次-结果{status_code} ({url})", save=False,
                )
                if status_code == 200 or status_code == 204:
                    break

    def log(
        self,
        level: LogLevel,
        text: str,
        output_to_console: bool = True,
        is_chat: bool = False,
        save: bool = True,
    ):
        message = f"[{now():%Y-%m-%d %H:%M:%S}] [{level.name}] {text}"
        if output_to_console:
            print(message)
        if save:
            with open(
                self.chatpath if is_chat else self.logpath, "a", encoding="utf-8"
            ) as logs:
                logs.write(message)
                logs.write("\r\n")

    def log_error(
        self,
        text: str,
        output_to_console: bool = True,
        is_chat: bool = False,
        save: bool = True,
    ):
        self.log(LogLevel.Error, text, output_to_console, is_chat, save)

    def log_info(
        self,
        text: str,
        output_to_console: bool = True,
        is_chat: bool = False,
        save: bool = True,
    ):
        self.log(LogLevel.Info, text, output_to_console, is_chat, save)

    def log_success(
        self,
        text: str,
        output_to_console: bool = True,
        is_chat: bool = False,
        save: bool = True,
    ):
        self.log(LogLevel.Success, text, output_to_console, is_chat, save)
