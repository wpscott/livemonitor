from ..base import BaseMonitor
from ..Utils import DateTimeFormat, now, getpushcolordic, pushall

from .TwitterConstants import Headers

import requests
import time

# vip=tgt, no_increase="True"/"False"
class TwitterUser(BaseMonitor):
    @staticmethod
    def gettwitteruser(user_screenname, cookies, proxy):
        try:
            headers = {
                **Headers,
                "x-csrf-token": cookies["ct0"],
            }
            params = {
                "variables": f'{{"screen_name":"{user_screenname}","withHighlightedLabel":false}}',
            }
            response = requests.get(
                "https://api.twitter.com/graphql/G6Lk7nZ6eEKd7LBBZw9MYw/UserByScreenName",
                headers=headers,
                params=params,
                cookies=cookies,
                timeout=(3, 7),
                proxies=proxy,
            )

            user_data = response.json()["data"]["user"]
            userdata_dic = user_data
            for key in user_data["legacy"]:
                userdata_dic[key] = user_data["legacy"][key]
            userdata_dic.pop("legacy")

            userdata_dic.pop("followers_count")
            userdata_dic.pop("normal_followers_count")
            userdata_dic.pop("listed_count")
            userdata_dic.pop("notifications")
            userdata_dic.pop("muting")
            userdata_dic.pop("blocked_by")
            userdata_dic.pop("blocking")
            userdata_dic.pop("follow_request_sent")
            userdata_dic.pop("followed_by")
            userdata_dic.pop("following")

            return userdata_dic
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
        self.userdata_dic = {}
        # 是否不推送推文和媒体数量的增加
        self.no_increase = getattr(self, "no_increase", "False")

    def run(self):
        while not self.stop_now:
            # 获取用户信息
            try:
                user_datadic_new = TwitterUser.gettwitteruser(
                    self.tgt, self.cookies, self.proxy
                )
                if self.is_firstrun:
                    self.userdata_dic = user_datadic_new
                    self.log_info(
                        f'"{self.name}" gettwitteruser {self.tgt}: {user_datadic_new}',
                    )
                    self.is_firstrun = False
                else:
                    pushtext_body = ""
                    for key in user_datadic_new:
                        if key not in self.userdata_dic:
                            pushtext_body += (
                                f"新键：{key}\n值：{str(user_datadic_new[key])}\n"
                            )
                            self.userdata_dic[key] = user_datadic_new[key]
                        elif self.userdata_dic[key] != user_datadic_new[key]:
                            if self.no_increase == "True" and (
                                key == "statuses_count" or key == "media_count"
                            ):
                                if self.userdata_dic[key] < user_datadic_new[key]:
                                    self.userdata_dic[key] = user_datadic_new[key]
                                    continue
                            pushtext_body += f"键：{key}\n原值：{str(self.userdata_dic[key])}\n现值：{str(user_datadic_new[key])}\n"
                            self.userdata_dic[key] = user_datadic_new[key]

                    if pushtext_body:
                        self.push(pushtext_body)
                self.log_success(f'"{self.name}" gettwitteruser {self.tgt}')
            except Exception as e:
                self.log_error(f'"{self.name}" gettwitteruser {self.tgt}: {e}',)
            time.sleep(self.interval)

    def push(self, pushtext_body):
        pushcolor_vipdic = getpushcolordic(self.tgt, self.vip_dic)
        pushcolor_dic = pushcolor_vipdic

        if pushcolor_dic:
            pushtext = f"【{self.__class__.__name__} {self.tgt_name} 数据改变】\n{pushtext_body}\n时间：{now():DateTimeFormat}\n网址：https://twitter.com/{self.tgt}"
            pushall(pushtext, pushcolor_dic, self.push_list)
            self.log_info(
                self.logpath, f'"{self.name}" pushall {str(pushcolor_dic)}\n{pushtext}',
            )
