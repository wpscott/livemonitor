from ..base import BaseMonitor
from ..Utils import DateTimeFormat, now, writelog, getpushcolordic, pushall

from datetime import datetime
from pathlib import Path
import requests
import time
from bs4 import BeautifulSoup as bs

# vip=tgt, "ingame_onstart"="True"/"False"
class LolUser(BaseMonitor):
    @staticmethod
    def getloluser(user_name, user_region, proxy):
        try:
            userdata_dic = {}
            response = requests.get(
                f"https://{user_region}.op.gg/summoner/l=en_US&userName={user_name}",
                timeout=(3, 7),
                proxies=proxy,
            )
            soup = bs(response.text, "lxml")
            # 用户id与时间戳
            userdata_dic["user_id"] = int(
                soup.find(id="SummonerRefreshButton").get("onclick").split("'")[1]
            )
            userdata_dic["renew_timestamp"] = int(
                soup.find(class_="LastUpdate").span.get("data-datetime")
            )
            # 比赛结果
            userdata_dic["user_gamedic"] = {}
            for gameitem in soup.find_all(class_="GameItemWrap"):
                game_timestamp = int(gameitem.div.get("data-game-time"))
                game_id = int(gameitem.div.get("data-game-id"))
                game_result = gameitem.div.get("data-game-result")
                game_kda = f"{gameitem.find(class_='Kill').text}/{gameitem.find(class_='Death').text}/{gameitem.find(class_='Assist').text}"
                userdata_dic["user_gamedic"][game_timestamp] = {
                    "game_id": game_id,
                    "game_result": game_result,
                    "game_kda": game_kda,
                }

            response = requests.get(
                f"https://{user_region}.op.gg/summoner/spectator/l=en_US&userName={user_name}",
                timeout=(3, 7),
                proxies=proxy,
            )
            soup = bs(response.text, "lxml")
            # 当前游戏
            current_gameitem = soup.find(class_="SpectateSummoner")
            if current_gameitem:
                userdata_dic["user_status"] = "in_game"
                userdata_dic["user_gametimestamp"] = int(
                    current_gameitem.find(class_="Time").span.get("data-datetime")
                )
            else:
                userdata_dic["user_status"] = "not_in_game"
                userdata_dic["user_gametimestamp"] = False

            return userdata_dic
        except Exception as e:
            raise e

    @staticmethod
    def renewloluser(user_id, user_region, proxy):
        try:
            headers = {
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
            }
            data = f"summonerId={user_id}"
            response = requests.post(
                f"https://{user_region}.op.gg/summoner/ajax/renew.json/",
                headers=headers,
                data=data,
                timeout=(3, 7),
                proxies=proxy,
            )
            if response.status_code != 200:
                raise Exception("Refresh failed")
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
        self.lastgametimestamp = 0
        self.tgt_region = getattr(self, "tgt_region", "jp")
        self.ingame_onstart = getattr(self, "ingame_onstart", "True")

    def run(self):
        while not self.stop_now:
            # 获取用户信息
            try:
                user_datadic_new = LolUser.getloluser(
                    self.tgt, self.tgt_region, self.proxy
                )
                if self.is_firstrun:
                    # 首次在线即推送
                    if (
                        self.ingame_onstart == "True"
                        and user_datadic_new["user_status"] == "in_game"
                    ):
                        pushtext = f"【{self.__class__.__name__} {self.tgt_name} 当前比赛】\n时间：{datetime.utcfromtimestamp(user_datadic_new['user_gametimestamp']):DateTimeFormat}\n网址：https://{self.tgt_region}.op.gg/summoner/userName={self.tgt}&l=en_US"
                        self.push(pushtext)

                    self.userdata_dic = user_datadic_new
                    if user_datadic_new["user_gamedic"]:
                        self.lastgametimestamp = sorted(
                            user_datadic_new["user_gamedic"], reverse=True
                        )[0]
                    writelog(
                        self.logpath,
                        f'[Info] "{self.name}" getloluser {self.tgt}: {user_datadic_new}',
                    )
                    self.is_firstrun = False
                else:
                    for key in user_datadic_new:
                        # 比赛结果 直接推送
                        if key == "user_gamedic":
                            for gametimestamp in user_datadic_new["user_gamedic"]:
                                if gametimestamp > self.lastgametimestamp:
                                    pushtext = f"【{self.__class__.__name__} {self.tgt_name} 比赛统计】\n结果：{user_datadic_new['user_gamedic'][gametimestamp]['game_result']}\nKDA：{user_datadic_new['user_gamedic'][gametimestamp]['game_kda']}\n时间：{datetime.utcfromtimestamp(gametimestamp):DateTimeFormat}\n网址：https://{self.tgt_region}.op.gg/summoner/userName={self.tgt}&l=en_US"
                                    self.push(pushtext)
                            if user_datadic_new["user_gamedic"]:
                                self.lastgametimestamp = sorted(
                                    user_datadic_new["user_gamedic"], reverse=True
                                )[0]
                        # 当前游戏 整合推送
                        elif key == "user_status":
                            if user_datadic_new[key] != self.userdata_dic[key]:
                                if user_datadic_new[key] == "in_game":
                                    pushtext = f"【{self.__class__.__name__} {self.tgt_name} 比赛开始】\n时间：{datetime.utcfromtimestamp(user_datadic_new['user_gametimestamp']):DateTimeFormat}\n网址：https://{self.tgt_region}.op.gg/summoner/userName={self.tgt}&l=en_US"
                                    self.push(pushtext)
                                else:
                                    pushtext = f"【{self.__class__.__name__} {self.tgt_name} 比赛结束】\n时间：{now():DateTimeFormat}\n网址：https://{self.tgt_region}.op.gg/summoner/userName={self.tgt}&l=en_US"
                                    self.push(pushtext)
                            self.userdata_dic[key] = user_datadic_new[key]
                        # 其他 不推送
                        else:
                            self.userdata_dic[key] = user_datadic_new[key]
                writelog(self.logpath, f'[Success] "{self.name}" getloluser {self.tgt}')

                # 更新信息 最短间隔120秒
                if (
                    int(
                        datetime.datetime.utcnow()
                        .replace(tzinfo=datetime.timezone.utc)
                        .timestamp()
                    )
                    - self.userdata_dic["renew_timestamp"]
                    > 120
                ):
                    try:
                        LolUser.renewloluser(
                            self.userdata_dic["user_id"], self.tgt_region, self.proxy
                        )
                        writelog(
                            self.logpath,
                            f'[Success] "{self.name}" renewloluser {self.userdata_dic["user_id"]}',
                        )
                    except Exception as e:
                        writelog(
                            self.logpath,
                            f'[Error] "{self.name}" renewloluser {self.userdata_dic["user_id"]}: {e}',
                        )
            except Exception as e:
                writelog(
                    self.logpath, f'[Error] "{self.name}" getloluser {self.tgt}: {e}'
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
