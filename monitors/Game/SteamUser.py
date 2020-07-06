from ..base import BaseMonitor
from ..Utils import DateTimeFormat, now, writelog, getpushcolordic, pushall

from pathlib import Path
import requests
import time
from bs4 import BeautifulSoup as bs

# vip=tgt, "online_onstart"="True"/"False"
class SteamUser(BaseMonitor):
    @staticmethod
    def getsteamuser(user_id, cookies, proxy):
        try:
            userdata_dic = {}
            response = requests.get(
                f"https://steamcommunity.com/profiles/{user_id}",
                cookies=cookies,
                timeout=(3, 7),
                proxies=proxy,
            )
            soup = bs(response.text, "lxml")
            if not soup.find(class_="profile_private_info"):
                print(soup.find(class_="header_real_name ellipsis"))
                userdata_dic["user_position"] = soup.find(
                    class_="header_real_name ellipsis"
                ).text.strip()
                userdata_dic["user_level"] = soup.find(
                    class_="friendPlayerLevelNum"
                ).text.strip()
                userdata_dic["user_status"] = soup.find(
                    class_="profile_in_game_header"
                ).text.strip()
                for item_count in soup.find_all(class_="profile_count_link ellipsis"):
                    userdata_dic[
                        "user_"
                        + item_count.find(class_="count_link_label").text.strip()
                    ] = item_count.find(class_="profile_count_link_total").text.strip()
            return userdata_dic
        except Exception as e:
            raise e

    def __init__(self, name, tgt, tgt_name, cfg, **config_mod):
        super().__init__(name, tgt, tgt_name, cfg, **config_mod)

        logpath = Path(f"./log/{self.__class__.__name__}")
        self.logpath = logpath / f"{self.name}.txt"
        if not logpath.exists():
            logpath.mkdir(parents=True)

        self.is_firstrun = True
        self.userdata_dic = {}
        self.online_onstart = getattr(self, "online_onstart", "True")

    def run(self):
        while not self.stop_now:
            # 获取用户信息
            try:
                user_datadic_new = SteamUser.getsteamuser(
                    self.tgt, self.cookies, self.proxy
                )
                if self.is_firstrun:
                    # 首次在线即推送
                    if (
                        self.online_onstart == "True"
                        and "user_status" in user_datadic_new
                        and (
                            user_datadic_new["user_status"] == "Currently Online"
                            or user_datadic_new["user_status"] == "当前在线"
                            or user_datadic_new["user_status"] == "現在オンラインです。"
                        )
                    ):
                        pushtext = f"【{self.__class__.__name__} {self.tgt_name} 当前在线】\n时间：{now():DateTimeFormat}\n网址：https://steamcommunity.com/profiles/{self.tgt}"
                        self.push(pushtext)

                    self.userdata_dic = user_datadic_new
                    writelog(
                        self.logpath,
                        f'[Info] "{self.name}" getsteamuser {self.tgt}: {user_datadic_new}',
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
                        pushtext = f"【{self.__class__.__name__} {self.tgt_name} 数据改变】\n{pushtext_body}时间：{now():DateTimeFormat}\n网址：https://steamcommunity.com/profiles/{self.tgt}"
                        self.push(pushtext)
                writelog(
                    self.logpath, f'[Success] "{self.name}" getsteamuser {self.tgt}'
                )
            except Exception as e:
                writelog(
                    self.logpath, f'[Error] "{self.name}" getsteamuser {self.tgt}: {e}'
                )
            time.sleep(self.interval)

    def push(self, pushtext):
        pushcolor_vipdic = getpushcolordic(self.tgt, self.vip_dic)
        pushcolor_dic = pushcolor_vipdic

        if pushcolor_dic:
            pushall(pushtext, pushcolor_dic, self.push_list)
            writelog(
                self.logpath,
                f'[Info] "{self.name}" pushall {str(pushcolor_dic)}\n{pushtext}',
            )
