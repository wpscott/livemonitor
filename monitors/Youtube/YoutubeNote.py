from ..base import BaseMonitor
from ..Utils import getpushcolordic, pushall

from .YoutubeConstants import Headers

import re
import json
import requests
import time

# word=text
class YoutubeNote(BaseMonitor):
    @staticmethod
    def getyoutubetoken(cookies, proxy):
        try:
            response = requests.get(
                "https://www.youtube.com",
                headers=Headers,
                cookies=cookies,
                proxies=proxy,
            )
            token = re.findall('"XSRF_TOKEN":"([^"]*)"', response.text)[0]
            if token:
                return token
            else:
                raise Exception("Invalid token")
        except Exception as e:
            raise e

    @staticmethod
    def getyoutubenotedic(token, cookies, proxy):
        try:
            youtubenotedic = {}
            params = {
                "name": "signalServiceEndpoint",
                "signal": "GET_NOTIFICATIONS_MENU",
            }
            data = {
                "sej": '{"clickTrackingParams":"CAkQovoBGAIiEwi9tvfcj5vnAhVUQ4UKHYyoBeQ=","commandMetadata":{"webCommandMetadata":{"url":"/service_ajax","sendPost":true,"apiUrl":"/youtubei/v1/notification/get_notification_menu"}},"signalServiceEndpoint":{"signal":"GET_NOTIFICATIONS_MENU","actions":[{"openPopupAction":{"popup":{"multiPageMenuRenderer":{"trackingParams":"CAoQ_6sBIhMIvbb33I-b5wIVVEOFCh2MqAXk","style":"MULTI_PAGE_MENU_STYLE_TYPE_NOTIFICATIONS","showLoadingSpinner":true}},"popupType":"DROPDOWN","beReused":true}}]}}',
                "session_token": token,
            }
            response = requests.post(
                "https://www.youtube.com/service_ajax",
                headers=Headers,
                params=params,
                data=data,
                cookies=cookies,
                timeout=(3, 7),
                proxies=proxy,
            )
            notesec_json = json.loads(response.text)["data"]["actions"][0][
                "openPopupAction"
            ]["popup"]["multiPageMenuRenderer"]["sections"][0]
            if "multiPageMenuNotificationSectionRenderer" in notesec_json:
                for note in notesec_json["multiPageMenuNotificationSectionRenderer"][
                    "items"
                ]:
                    if "notificationRenderer" in note:
                        note_id = int(note["notificationRenderer"]["notificationId"])
                        note_text = note["notificationRenderer"]["shortMessage"][
                            "simpleText"
                        ]
                        note_time = note["notificationRenderer"]["sentTimeText"][
                            "simpleText"
                        ]
                        note_videoid = note["notificationRenderer"][
                            "navigationEndpoint"
                        ]["commandMetadata"]["webCommandMetadata"]["url"].replace(
                            "/watch?v=", ""
                        )
                        youtubenotedic[note_id] = {
                            "note_text": note_text,
                            "note_time": note_time,
                            "note_videoid": note_videoid,
                        }
            return youtubenotedic
        except Exception as e:
            raise e

    def __init__(self, name, tgt, tgt_name, cfg, **config_mod):
        super().__init__(name, tgt, tgt_name, cfg, **config_mod)

        # logpath = Path(f"./log/{self.__class__.__name__}")
        # self.logpath = logpath / f"{self.name}.txt"
        # if not logpath.exists():
        #     logpath.mkdir(parents=True)
        super().initialize_log(self.__class__.__name__, False, False)

        self.is_firstrun = True
        self.token = False
        # note_id为整数
        self.note_id_old = 0

    def run(self):
        while not self.stop_now:
            # 获取token
            if not self.token:
                try:
                    self.token = YoutubeNote.getyoutubetoken(self.cookies, self.proxy)
                    self.log_info(
                        f'"{self.name}" getyoutubetoken {self.tgt}: {self.token}',
                    )
                    self.log_success(f'"{self.name}" getyoutubetoken {self.tgt}',)
                except Exception as e:
                    self.log_error(f'"{self.name}" getyoutubetoken {self.tgt}: {e}',)
                    time.sleep(5)
                    continue

            # 获取订阅通知列表
            if self.token:
                try:
                    notedic_new = YoutubeNote.getyoutubenotedic(
                        self.token, self.cookies, self.proxy
                    )
                    if self.is_firstrun:
                        if notedic_new:
                            self.note_id_old = sorted(notedic_new, reverse=True)[0]
                        self.log_info(
                            f'"{self.name}" getyoutubenotedic {self.tgt}: {notedic_new}',
                        )
                        self.is_firstrun = False
                    else:
                        for note_id in notedic_new:
                            if note_id > self.note_id_old:
                                self.push(note_id, notedic_new)
                        if notedic_new:
                            self.note_id_old = sorted(notedic_new, reverse=True)[0]
                    self.log_success(f'"{self.name}" getyoutubenotedic {self.tgt}',)
                except Exception as e:
                    self.log_error(f'"{self.name}" getyoutubenotedic {self.tgt}: {e}',)
            time.sleep(self.interval)

    def push(self, note_id, notedic):
        pushcolor_worddic = getpushcolordic(
            notedic[note_id]["note_text"], self.word_dic
        )
        pushcolor_dic = pushcolor_worddic

        if pushcolor_dic:
            pushtext = f"【{self.__class__.__name__} {self.tgt_name} 订阅通知】\n内容：{notedic[note_id]['note_text']}\n时间：{notedic[note_id]['note_time']}\n网址：https://www.youtube.com/watch?v={notedic[note_id]['note_videoid']}"
            pushall(pushtext, pushcolor_dic, self.push_list)
            self.log_info(f'"{self.name}" pushall {str(pushcolor_dic)}\n{pushtext}',)
