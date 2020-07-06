from ..base import BaseMonitor
from ..Utils import timestamp, writelog, addpushcolordic, getpushcolordic, pushall

from .YoutubeConstants import Headers

from datetime import datetime
import json
from pathlib import Path
import re
import requests
import time
from urllib.parse import quote


class YoutubeChat(BaseMonitor):
    @staticmethod
    def getyoutubechatcontinuation(video_id, proxy):
        try:
            url = f"https://www.youtube.com/live_chat?is_popout=1&v={video_id}"
            response = requests.get(url, headers=Headers, timeout=(3, 7), proxies=proxy)
            data = json.loads(
                re.findall(r"window\[\"ytInitialData\"\] = (.*?);", response.text)[0]
            )
            continuation = data["contents"]["liveChatRenderer"]["continuations"][0][
                "timedContinuationData"
            ]["continuation"]
            if continuation:
                return f"/live_chat/get_live_chat?commandMetadata=%5Bobject%20Object%5D&continuation={quote(continuation)}&hidden=false&pbj=1"
            else:
                raise Exception("Invalid continuation")
        except Exception as e:
            raise e

    @staticmethod
    def getyoutubechatlist(continuation, proxy):
        try:
            chatlist = []
            headers = {
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36",
                "accept-encoding": "gzip, deflate, br",
            }
            response = requests.get(
                f"https://www.youtube.com{continuation}",
                headers=headers,
                timeout=(3, 7),
                proxies=proxy,
            )
            data = json.loads(response.content)
            chatlist_json = data["response"]["continuationContents"][
                "liveChatContinuation"
            ]
            if "actions" in chatlist_json:
                for chat in chatlist_json["actions"]:
                    if "addChatItemAction" in chat:
                        if (
                            "liveChatTextMessageRenderer"
                            in chat["addChatItemAction"]["item"]
                        ):
                            chat_type = "message"
                            chat_dic = chat["addChatItemAction"]["item"][
                                "liveChatTextMessageRenderer"
                            ]
                        elif (
                            "liveChatPaidMessageRenderer"
                            in chat["addChatItemAction"]["item"]
                        ):
                            chat_type = "superchat"
                            chat_dic = chat["addChatItemAction"]["item"][
                                "liveChatPaidMessageRenderer"
                            ]
                        elif (
                            "liveChatPaidStickerRenderer"
                            in chat["addChatItemAction"]["item"]
                        ):
                            chat_type = "supersticker"
                            chat_dic = chat["addChatItemAction"]["item"][
                                "liveChatPaidStickerRenderer"
                            ]
                        elif (
                            "liveChatMembershipItemRenderer"
                            in chat["addChatItemAction"]["item"]
                        ):
                            chat_type = "membership"
                            chat_dic = chat["addChatItemAction"]["item"][
                                "liveChatMembershipItemRenderer"
                            ]
                        else:
                            chat_type = ""
                            chat_dic = {}

                        if chat_dic:
                            chat_timestamp_float = (
                                int(chat_dic["timestampUsec"]) / 1000000
                            )
                            chat_username = chat_dic["authorName"]["simpleText"]
                            chat_userchannel = chat_dic["authorExternalChannelId"]
                            chat_text = ""
                            if "message" in chat_dic:
                                for chat_text_run in chat_dic["message"]["runs"]:
                                    if "text" in chat_text_run:
                                        chat_text += chat_text_run["text"]
                                    elif "emoji" in chat_text_run:
                                        chat_text += chat_text_run["emoji"][
                                            "shortcuts"
                                        ][0]
                            if "purchaseAmountText" in chat_dic:
                                chat_type += (
                                    f" {chat_dic['purchaseAmountText']['simpleText']} "
                                )
                            chatlist.append(
                                {
                                    "chat_timestamp_float": chat_timestamp_float,
                                    "chat_username": chat_username,
                                    "chat_userchannel": chat_userchannel,
                                    "chat_type": chat_type,
                                    "chat_text": chat_text,
                                }
                            )
            return chatlist, data["url"]
        except Exception as e:
            raise e

    def __init__(self, name, tgt, tgt_name, cfg, **config_mod):
        super().__init__(name, tgt, tgt_name, cfg, **config_mod)

        logpath = Path(f"./log/{self.__class__.__name__}/{self.tgt_name}")
        self.logpath = logpath / f"{self.name}.txt"
        self.chatpah = logpath / f"{self.name}_chat.txt"
        if not logpath.exists():
            logpath.mkdir(parents=True)

        # continuation为字符
        self.continuation = False
        self.pushpunish = {}
        self.regen_time = 0
        self.tgt_channel = getattr(self, "tgt_channel", "")
        self.regen = getattr(self, "regen", "False")
        self.regen_amount = getattr(self, "regen_amount", 1)

    def run(self):
        while not self.stop_now:
            # 获取continuation
            if not self.continuation:
                try:
                    self.continuation = YoutubeChat.getyoutubechatcontinuation(
                        self.tgt, self.proxy
                    )
                    writelog(
                        self.logpath,
                        f'[Info] "{self.name}" getyoutubechatcontinuation {self.tgt}: {self.continuation}',
                    )
                    writelog(
                        self.logpath,
                        f'[Success] "{self.name}" getyoutubechatcontinuation {self.tgt}',
                    )
                except Exception as e:
                    writelog(
                        self.logpath,
                        f'[Error] "{self.name}" getyoutubechatcontinuation {self.tgt}: {e}',
                    )
                    time.sleep(5)
                    continue

            # 获取直播评论列表
            if self.continuation:
                try:
                    chatlist, self.continuation = YoutubeChat.getyoutubechatlist(
                        self.continuation, self.proxy
                    )
                    for chat in chatlist:
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
                    writelog(
                        self.logpath,
                        f'[Error] "{self.name}" getyoutubechatlist {self.continuation}: {e}',
                    )
            time.sleep(self.interval)

    def push(self, chat):
        writelog(
            self.chatpath,
            f'{chat["chat_timestamp_float"]}\t{chat["chat_username"]}\t{chat["chat_userchannel"]}\t{chat["chat_type"]}\t{chat["chat_text"]}',
        )

        pushcolor_vipdic = getpushcolordic(chat["chat_userchannel"], self.vip_dic)
        pushcolor_worddic = getpushcolordic(chat["chat_text"], self.word_dic)
        pushcolor_dic = addpushcolordic(pushcolor_vipdic, pushcolor_worddic)

        if pushcolor_dic:
            pushcolor_dic = self.punish(pushcolor_dic)

            pushtext = f'【{self.__class__.__name__} {self.tgt_name} 直播评论】\n用户：{chat["chat_username"]}\n内容：{chat["chat_text"]}\n类型：{chat["chat_type"]}\n时间：{datetime.utcfromtimestamp(chat["chat_timestamp_float"]):"%Y-%m-%d %H:%M:%S %Z"}\n网址：https://www.youtube.com/watch?v={self.tgt}'
            pushall(pushtext, pushcolor_dic, self.push_list)
            writelog(
                self.logpath,
                f'[Info] "{self.name}" pushall {str(pushcolor_dic)}\n{pushtext}',
            )

    def punish(self, pushcolor_dic):
        # 推送惩罚恢复
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

        # 去除来源频道的相关权重
        if self.tgt_channel in self.vip_dic:
            for color in self.vip_dic[self.tgt_channel]:
                if color in pushcolor_dic and "vip" not in color:
                    pushcolor_dic[color] -= self.vip_dic[self.tgt_channel][color]

        # 只对pushcolor_dic存在的键进行修改，不同于addpushcolordic
        for color in self.pushpunish:
            if color in pushcolor_dic and "vip" not in color:
                pushcolor_dic[color] -= self.pushpunish[color]

        # 更新pushpunish
        for color in pushcolor_dic:
            if pushcolor_dic[color] > 0 and "vip" not in color:
                if color in self.pushpunish:
                    self.pushpunish[color] += 1
                else:
                    self.pushpunish[color] = 1
        return pushcolor_dic
