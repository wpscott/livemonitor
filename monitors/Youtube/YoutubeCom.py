from ..base import BaseMonitor

from .YoutubeConstants import Headers

import json
import re
import requests
import time


# vip=tgt, word=text
class YoutubeCom(BaseMonitor):
    @staticmethod
    def getyoutubepostdic(user_id, cookies, proxy):
        try:
            postlist = {}
            url = f"https://www.youtube.com/channel/{user_id}/community"
            response = requests.get(
                url, headers=Headers, cookies=cookies, timeout=(3, 7), proxies=proxy
            )
            postpage_json = json.loads(
                re.findall(r"window\[\"ytInitialData\"\] = (.*?);", response.text)[0]
            )
            postlist_json = postpage_json["contents"]["twoColumnBrowseResultsRenderer"][
                "tabs"
            ][3]["tabRenderer"]["content"]["sectionListRenderer"]["contents"][0][
                "itemSectionRenderer"
            ][
                "contents"
            ]
            for post in postlist_json:
                if "backstagePostThreadRenderer" in post:
                    post_info = post["backstagePostThreadRenderer"]["post"][
                        "backstagePostRenderer"
                    ]
                    post_id = post_info["postId"]
                    post_time = ""
                    for post_time_run in post_info["publishedTimeText"]["runs"]:
                        post_time += post_time_run["text"]
                    post_text = ""
                    for post_text_run in post_info["contentText"]["runs"]:
                        post_text += post_text_run["text"]
                    postlist[post_id] = {"post_time": post_time, "post_text": post_text}
            return postlist
        except Exception as e:
            raise e

    def __init__(self, name, tgt, tgt_name, cfg, **config_mod):
        super().__init__(name, tgt, tgt_name, cfg, **config_mod)

        # logpath = Path(f"./log/{self.__class__.__name__}")
        # self.logpath = logpath / f"{self.name}.txt"
        # if not logpath.exists():
        #     logpath.mkdir(parents=True)
        self.initialize_log(self.__class__.__name__, False, False)

        self.is_firstrun = True
        # post_id为字符
        self.postlist = []

    def run(self):
        while not self.stop_now:
            # 获取帖子列表
            try:
                postdic_new = YoutubeCom.getyoutubepostdic(
                    self.tgt, self.cookies, self.proxy
                )
                for post_id in postdic_new:
                    if post_id not in self.postlist:
                        self.postlist.append(post_id)
                        if not self.is_firstrun:
                            self.push(post_id, postdic_new)
                if self.is_firstrun:
                    self.log_info(
                        f'"{self.name}" getyoutubepostdic {self.tgt}: {postdic_new}',
                    )
                    self.is_firstrun = False
                self.log_success(f'"{self.name}" getyoutubepostdic {self.tgt}',)
            except Exception as e:
                self.log_error(f'"{self.name}" getyoutubepostdic {self.tgt}: {e}',)
            time.sleep(self.interval)

    def push(self, post_id, postdic):
        pushcolor_vipdic = BaseMonitor.getpushcolordic(self.tgt, self.vip_dic)
        pushcolor_worddic = BaseMonitor.getpushcolordic(
            postdic[post_id]["post_text"], self.word_dic
        )
        pushcolor_dic = BaseMonitor.addpushcolordic(pushcolor_vipdic, pushcolor_worddic)

        # 进行推送
        if pushcolor_dic:
            pushtext = f"【{self.__class__.__name__} {self.tgt_name} 社区帖子】\n内容：{postdic[post_id]['post_text'][0:3000]}\n时间：{postdic[post_id]['post_time']}\n网址：https://www.youtube.com/post/{post_id}"
            self.pushall(pushtext, pushcolor_dic, self.push_list)
            self.log_info(f'"{self.name}" pushall {str(pushcolor_dic)}\n{pushtext}',)
