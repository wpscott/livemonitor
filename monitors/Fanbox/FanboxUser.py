from ..base import BaseMonitor
from ..Utils import DateTimeFormat, now, getpushcolordic, pushall

from .FanboxConstants import Headers

import requests
import time

# vip=tgt
class FanboxUser(BaseMonitor):
    @staticmethod
    def getfanboxuser(user_id, proxy):
        try:
            headers = {
                **Headers,
                "Origin": f"https://{user_id}.fanbox.cc",
                "Referer": f"https://{user_id}.fanbox.cc/",
            }
            response = requests.get(
                f"https://api.fanbox.cc/creator.get?creatorId={user_id}",
                headers=headers,
                timeout=(3, 7),
                proxies=proxy,
            )

            user_data = response.json()["body"]
            userdata_dic = user_data
            for key in user_data["user"]:
                userdata_dic[key] = user_data["user"][key]
            userdata_dic.pop("user")

            userdata_dic.pop("isFollowed")
            userdata_dic.pop("isSupported")

            return userdata_dic
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
        self.userdata_dic = {}

    def run(self):
        while not self.stop_now:
            # 获取用户信息
            try:
                user_datadic_new = FanboxUser.getfanboxuser(self.tgt, self.proxy)
                if self.is_firstrun:
                    self.userdata_dic = user_datadic_new
                    self.log_info(
                        f'"{self.name}" getfanboxuser {self.tgt}: {user_datadic_new}',
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
                            pushtext_body += f"键：{key}\n原值：{str(self.userdata_dic[key])}\n现值：{str(user_datadic_new[key])}\n"
                            self.userdata_dic[key] = user_datadic_new[key]

                    if pushtext_body:
                        self.push(pushtext_body)
                self.log_success(f'"{self.name}" getfanboxuser {self.tgt}')
            except Exception as e:
                self.log_error(f'"{self.name}" getfanboxuser {self.tgt}: {e}')
            time.sleep(self.interval)

    def push(self, pushtext_body):
        pushcolor_vipdic = getpushcolordic(self.tgt, self.vip_dic)
        pushcolor_dic = pushcolor_vipdic

        if pushcolor_dic:
            pushtext = f"【{self.__class__.__name__} {self.tgt_name} 数据改变】\n{pushtext_body}\n时间：{now():DateTimeFormat}网址：https://{self.tgt}.fanbox.cc/"
            pushall(pushtext, pushcolor_dic, self.push_list)
            self.log_info(f'"{self.name}" pushall {str(pushcolor_dic)}\n{pushtext}')
