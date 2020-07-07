from ..base import BaseMonitor
from ..Utils import DateTimeFormat

from .FanboxConstants import Headers

from datetime import datetime
import requests
import time

# vip=tgt, word=text
class FanboxPost(BaseMonitor):
    @staticmethod
    def getfanboxpostdic(user_id, cookies, proxy):
        try:
            post_dic = {}
            headers = {
                **Headers,
                "Origin": f"https://{user_id}.fanbox.cc",
                "Referer": f"https://{user_id}.fanbox.cc/",
            }
            response = requests.get(
                f"https://api.fanbox.cc/post.listCreator?creatorId={user_id}&limit=10",
                headers=headers,
                cookies=cookies,
                timeout=(3, 7),
                proxies=proxy,
            )

            post_list = response.json()["body"]["items"]
            for post in post_list:
                post_id = post["id"]
                post_title = post["title"]
                # python3.6无法识别+00:00格式，只能识别+0000格式
                try:
                    post_publishtimestamp = datetime.strptime(
                        post["publishedDatetime"], "%Y-%m-%dT%H:%M:%S%z"
                    ).timestamp()
                except:
                    post_publishtimestamp = datetime.strptime(
                        post["publishedDatetime"].replace(":", ""), "%Y-%m-%dT%H%M%S%z"
                    ).timestamp()
                post_type = post["type"]
                post_text = ""
                if isinstance(post["body"], dict):
                    if "text" in post["body"]:
                        post_text = post["body"]["text"]
                    elif "blocks" in post["body"]:
                        for block in post["body"]["blocks"]:
                            post_text += f"{block['text']}\n"
                post_fee = post["feeRequired"]
                post_dic[post_id] = {
                    "post_title": post_title,
                    "post_publishtimestamp": post_publishtimestamp,
                    "post_type": post_type,
                    "post_text": post_text,
                    "post_fee": post_fee,
                }
            return post_dic
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
        self.postlist = []

    def run(self):
        while not self.stop_now:
            # 获取帖子列表
            try:
                postdic_new = FanboxPost.getfanboxpostdic(
                    self.tgt, self.cookies, self.proxy
                )
                for post_id in postdic_new:
                    if post_id not in self.postlist:
                        self.postlist.append(post_id)
                        if not self.is_firstrun:
                            self.push(post_id, postdic_new)
                if self.is_firstrun:
                    self.log_info(
                        f'"{self.name}" getfanboxpostdic {self.tgt}: {postdic_new}',
                    )
                    self.is_firstrun = False
                self.log_success(f'"{self.name}" getfanboxpostdic {self.tgt}')
            except Exception as e:
                self.log_error(f'"{self.name}" getfanboxpostdic {self.tgt}: {e}',)
            time.sleep(self.interval)

    def push(self, post_id, postdic):
        post = postdic[post_id]
        pushcolor_vipdic = BaseMonitor.getpushcolordic(self.tgt, self.vip_dic)
        pushcolor_worddic = BaseMonitor.getpushcolordic(
            post["post_text"], self.word_dic
        )
        pushcolor_dic = BaseMonitor.addpushcolordic(pushcolor_vipdic, pushcolor_worddic)

        if pushcolor_dic:
            pushtext = f"【{self.__class__.__name__} {self.tgt_name} 社区帖子】\n标题：{post['post_title']}\n内容：{post['post_text'][0:2500]}\n类型：{post['post_type']}\n档位：{post['post_fee']}\n时间：{datetime.utcfromtimestamp(post['post_publishtimestamp']):DateTimeFormat}\n网址：https://{self.tgt}.fanbox.cc/posts/{post_id}"
            self.pushall(pushtext, pushcolor_dic, self.push_list)
            self.log_info(f'"{self.name}" pushall {str(pushcolor_dic)}\n{pushtext}',)
