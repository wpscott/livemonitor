from ..base import BaseMonitor
from ..Utils import (
    DateTimeFormat,
    timestamp,
    addpushcolordic,
    getpushcolordic,
    pushall,
)

from datetime import datetime
import requests
import time

# vip=chat_screenname, word=text, punish=tgt+push(不包括含有'vip'的类型)
class TwitcastChat(BaseMonitor):
    @staticmethod
    def gettwitcastchatlist(live_id, proxy):
        try:
            twitcastchatlist = []
            url = f"https://twitcasting.tv/userajax.php?c=listall&m={live_id}&n=10&f=0k=0&format=json"
            response = requests.get(url, timeout=(3, 7), proxies=proxy)
            for i in range(len(response.json()["comments"])):
                chat = response.json()["comments"][i]
                chat_id = chat["id"]
                chat_screenname = chat["author"]["screenName"]
                chat_name = chat["author"]["name"]
                chat_timestamp_float = float(chat["createdAt"]) / 1000
                chat_text = chat["message"]
                twitcastchatlist.append(
                    {
                        "chat_id": chat_id,
                        "chat_screenname": chat_screenname,
                        "chat_name": chat_name,
                        "chat_timestamp_float": chat_timestamp_float,
                        "chat_text": chat_text,
                    }
                )
            return twitcastchatlist
        except Exception as e:
            raise e

    def __init__(self, name, tgt, tgt_name, cfg, **config_mod):
        super().__init__(name, tgt, tgt_name, cfg, **config_mod)

        # logpath = Path(f"./log/{self.__class__.__name__}/{self.tgt_name}")
        # self.logpath = logpath / f"{self.name}.txt"
        # self.chatpah = logpath / f"{self.name}_chat.txt"
        # if not logpath.exists():
        #     logpath.mkdir(parents=True)
        super().initialize_log(self.__class__.__name__, True, True)

        self.chat_id_old = 0
        self.pushpunish = {}
        self.regen_time = 0
        self.tgt_channel = getattr(self, "tgt_channel", "")
        self.regen = getattr(self, "regen", "False")
        self.regen_amount = getattr(self, "regen_amount", 1)

    def run(self):
        while not self.stop_now:
            # 获取直播评论列表
            try:
                chatlist = TwitcastChat.gettwitcastchatlist(self.tgt, self.proxy)
                for chat in chatlist:
                    # chatlist默认从小到大排列
                    if self.chat_id_old < chat["chat_id"]:
                        self.chat_id_old = chat["chat_id"]
                        self.push(chat)

                # 目标每次请求获取5条评论，间隔时间应在0.1~2秒之间
                if len(chatlist) > 0:
                    self.interval = self.interval * 5 / len(chatlist)
                else:
                    self.interval = 2
                if self.interval > 2:
                    self.interval = 2
                if self.interval < 0.1:
                    self.interval = 0.1
            except Exception as e:
                self.log_error(
                    f'"{self.name}" gettwitcastchatlist {self.chat_id_old}: {e}',
                )
            time.sleep(self.interval)

    def push(self, chat):
        self.log_info(
            f"{chat['chat_timestamp_float']}\t{chat['chat_name']}\t{chat['chat_screenname']}\t{chat['chat_text']}",
            output_to_console=False,
            is_chat=True,
        )

        pushcolor_vipdic = getpushcolordic(chat["chat_screenname"], self.vip_dic)
        pushcolor_worddic = getpushcolordic(chat["chat_text"], self.word_dic)
        pushcolor_dic = addpushcolordic(pushcolor_vipdic, pushcolor_worddic)

        if pushcolor_dic:
            pushcolor_dic = self.punish(pushcolor_dic)

            pushtext = f"【{self.__class__.__name__} {self.tgt_name} 直播评论】\n用户：{chat['chat_name']}({chat['chat_screenname']})\n内容：{chat['chat_text']}\n时间：{datetime.utcfromtimestamp(chat['chat_timestamp_float']):DateTimeFormat}\n网址：https://twitcasting.tv/{self.tgt_channel}"
            pushall(pushtext, pushcolor_dic, self.push_list)
            self.log_info(f'"{self.name}" pushall {str(pushcolor_dic)}\n{pushtext}',)

    def punish(self, pushcolor_dic):
        if self.regen != "False":
            time_now = timestamp()
            regen_amt = int(
                int((time_now - self.regen_time) / float(self.regen))
                * float(self.regen_amount)
            )
            if regen_amt:
                self.regen_time = time_now
                for color in list(self.pushpunish):
                    if self.pushpunish[color] > regen_amt:
                        self.pushpunish[color] -= regen_amt
                    else:
                        self.pushpunish.pop(color)

        if self.tgt_channel in self.vip_dic:
            for color in self.vip_dic[self.tgt_channel]:
                if color in pushcolor_dic and "vip" not in color:
                    pushcolor_dic[color] -= self.vip_dic[self.tgt_channel][color]

        for color in self.pushpunish:
            if color in pushcolor_dic and "vip" not in color:
                pushcolor_dic[color] -= self.pushpunish[color]

        for color in pushcolor_dic:
            if pushcolor_dic[color] > 0 and "vip" not in color:
                if color in self.pushpunish:
                    self.pushpunish[color] += 1
                else:
                    self.pushpunish[color] = 1
        return pushcolor_dic
