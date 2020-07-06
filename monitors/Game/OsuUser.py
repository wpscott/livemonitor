from ..base import BaseMonitor
from ..Utils import DateTimeFormat, now, writelog, getpushcolordic, pushall

from datetime import datetime
from pathlib import Path
import requests
import time
import json
from bs4 import BeautifulSoup as bs

# vip=tgt, "online_onstart"="True"/"False"
class OsuUser(BaseMonitor):
    @staticmethod
    def getosuuser(user_id, cookies, proxy):
        try:
            response = requests.get(
                f"https://osu.ppy.sh/users/{user_id}",
                cookies=cookies,
                timeout=(3, 7),
                proxies=proxy,
            )
            soup = bs(response.text, "lxml")
            user_data = json.loads(
                soup.find(attrs={"id": "json-user", "type": "application/json"}).text
            )
            userdata_dic = user_data
            for key in user_data["statistics"]:
                userdata_dic[key] = user_data["statistics"][key]
            userdata_dic.pop("statistics")

            userdata_dic.pop("follower_count")
            userdata_dic.pop("rank")
            userdata_dic.pop("rankHistory")
            userdata_dic.pop("pp_rank")
            userdata_dic.pop("last_visit")

            # 比赛结果
            userdata_dic["user_gamedic"] = {}
            gamelist = json.loads(
                soup.find(attrs={"id": "json-extras", "type": "application/json"}).text
            )["recentActivity"]
            for gameitem in gamelist:
                game_id = gameitem["id"]
                # python3.6无法识别+00:00格式，只能识别+0000格式
                try:
                    game_timestamp = datetime.datetime.strptime(
                        gameitem["createdAt"], "%Y-%m-%dT%H:%M:%S%z"
                    ).timestamp()
                except:
                    game_timestamp = datetime.datetime.strptime(
                        gameitem["createdAt"].replace(":", ""), "%Y-%m-%dT%H%M%S%z"
                    ).timestamp()
                game_type = gameitem["type"]
                try:
                    game_result = f"{gameitem['mode']} - {gameitem['scoreRank']}({gameitem['rank']}) - {gameitem['beatmap']['title']}(https://osu.ppy.sh/{gameitem['beatmap']['url']})"
                except:
                    game_result = ""
                userdata_dic["user_gamedic"][game_id] = {
                    "game_timestamp": game_timestamp,
                    "game_type": game_type,
                    "game_result": game_result,
                }
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
        self.lastgameid = 0
        self.online_onstart = getattr(self, "online_onstart", "True")

    def run(self):
        while not self.stop_now:
            # 获取用户信息
            try:
                user_datadic_new = OsuUser.getosuuser(
                    self.tgt, self.cookies, self.proxy
                )
                if self.is_firstrun:
                    # 首次在线即推送
                    if (
                        self.online_onstart == "True"
                        and "is_online" in user_datadic_new
                        and user_datadic_new["is_online"] == "true"
                    ):
                        pushtext = f"【{self.__class__.__name__} {self.tgt_name} 当前在线】\n时间：{now():DateTimeFormat}\n网址：https://osu.ppy.sh/users/{self.tgt}"
                        self.push(pushtext)

                    self.userdata_dic = user_datadic_new
                    if user_datadic_new["user_gamedic"]:
                        self.lastgameid = sorted(
                            user_datadic_new["user_gamedic"], reverse=True
                        )[0]
                    writelog(
                        self.logpath,
                        f'[Info] "{self.name}" getosuuser {self.tgt}: {user_datadic_new}',
                    )
                    self.is_firstrun = False
                else:
                    pushtext_body = ""
                    for key in user_datadic_new:
                        # 比赛结果 直接推送
                        if key == "user_gamedic":
                            for gameid in user_datadic_new["user_gamedic"]:
                                if gameid > self.lastgameid:
                                    game = user_datadic_new["user_gamedic"][gameid]
                                    pushtext = f"【{self.__class__.__name__} {self.tgt_name} 比赛统计】\n类型：{game['game_type']}\n结果：{game['game_result']}\n时间：{datetime.utcfromtimestamp(game['game_timestamp']):DateTimeFormat}\n网址：https://osu.ppy.sh/users/{self.tgt}"
                                    self.push(pushtext)
                            if user_datadic_new["user_gamedic"]:
                                self.lastgameid = sorted(
                                    user_datadic_new["user_gamedic"], reverse=True
                                )[0]
                        # 其他 整合推送
                        else:
                            if key not in self.userdata_dic:
                                pushtext_body += (
                                    f"新键：{key}\n值：{str(user_datadic_new[key])}\n"
                                )
                                self.userdata_dic[key] = user_datadic_new[key]
                            elif self.userdata_dic[key] != user_datadic_new[key]:
                                pushtext_body += f"键：{key}\n原值：{str(self.userdata_dic[key])}\n现值：{str(user_datadic_new[key])}\n"
                                self.userdata_dic[key] = user_datadic_new[key]

                    if pushtext_body:
                        pushtext = f"【{self.__class__.__name__} {self.tgt_name} 数据改变】\n{pushtext_body}\n时间：{now():DateTimeFormat}网址：https://osu.ppy.sh/users/{self.tgt}"
                        self.push(pushtext)
                writelog(self.logpath, f'[Success] "{self.name}" getosuuser {self.tgt}')
            except Exception as e:
                writelog(
                    self.logpath, f'[Error] "{self.name}" getosuuser {self.tgt}: {e}'
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
