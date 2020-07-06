from ..base import BaseMonitor
from ..Utils import DateTimeFormat, writelog, addpushcolordic, getpushcolordic, pushall
from .TwitterUser import TwitterUser

from .TwitterConstants import TweetParams, Headers

from pathlib import Path
from datetime import datetime
import time
import requests

# vip=tgt+mention, word=text
class TwitterTweet(BaseMonitor):
    @staticmethod
    def gettwittertweetdic(user_restid, cookies, proxy):
        try:
            tweet_dic = {}
            params = {**TweetParams, "userId": user_restid}
            headers = {**Headers, "x-csrf-token": cookies["ct0"]}
            response = requests.get(
                f"https://api.twitter.com/2/timeline/profile/{user_restid}.json",
                headers=headers,
                params=params,
                cookies=cookies,
                timeout=(3, 7),
                proxies=proxy,
            )

            if "globalObjects" in response.json():
                tweetlist_dic = response.json()["globalObjects"]["tweets"]
                for tweet_id in tweetlist_dic:
                    if tweetlist_dic[tweet_id]["user_id_str"] == user_restid:
                        tweet_timestamp = datetime.strptime(
                            tweetlist_dic[tweet_id]["created_at"],
                            "%a %b %d %H:%M:%S %z %Y",
                        ).timestamp()
                        tweet_text = tweetlist_dic[tweet_id]["full_text"]
                        if "retweeted_status_id_str" in tweetlist_dic[tweet_id]:
                            tweet_type = "转推"
                        elif "user_mentions" in tweetlist_dic[tweet_id]["entities"]:
                            tweet_type = "回复"
                        else:
                            tweet_type = "发布"
                        tweet_media = []
                        if "media" in tweetlist_dic[tweet_id]["entities"]:
                            for media in tweetlist_dic[tweet_id]["entities"]["media"]:
                                tweet_media.append(media["expanded_url"])
                        tweet_urls = []
                        if "urls" in tweetlist_dic[tweet_id]["entities"]:
                            for url in tweetlist_dic[tweet_id]["entities"]["urls"]:
                                tweet_urls.append(url["expanded_url"])
                        tweet_mention = ""
                        if "user_mentions" in tweetlist_dic[tweet_id]["entities"]:
                            for user_mention in tweetlist_dic[tweet_id]["entities"][
                                "user_mentions"
                            ]:
                                tweet_mention += f"{user_mention['screen_name']}\n"
                        tweet_dic[int(tweet_id)] = {
                            "tweet_timestamp": tweet_timestamp,
                            "tweet_text": tweet_text,
                            "tweet_type": tweet_type,
                            "tweet_media": tweet_media,
                            "tweet_urls": tweet_urls,
                            "tweet_mention": tweet_mention,
                        }
            return tweet_dic
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
        self.tgt_restid = False
        # tweet_id为整数
        self.tweet_id_old = 0

    def run(self):
        while not self.stop_now:
            # 获取用户restid
            if not self.tgt_restid:
                try:
                    tgt_dic = TwitterUser.gettwitteruser(
                        self.tgt, self.cookies, self.proxy
                    )
                    self.tgt_restid = tgt_dic["rest_id"]
                    writelog(
                        self.logpath,
                        f'[Info] "{self.name}" gettwitteruser {self.tgt}: {self.tgt_restid}',
                    )
                    writelog(
                        self.logpath,
                        f'[Success] "{self.name}" gettwitteruser {self.tgt}',
                    )
                except Exception as e:
                    writelog(
                        self.logpath,
                        f'[Error] "{self.name}" gettwitteruser {self.tgt}: {e}',
                    )
                    time.sleep(5)
                    continue

            # 获取推特列表
            if self.tgt_restid:
                try:
                    tweetdic_new = TwitterTweet.gettwittertweetdic(
                        self.tgt_restid, self.cookies, self.proxy
                    )
                    if self.is_firstrun:
                        if tweetdic_new:
                            self.tweet_id_old = sorted(tweetdic_new, reverse=True)[0]
                        writelog(
                            self.logpath,
                            f'[Info] "{self.name}" gettwittertweetdic {self.tgt}: {tweetdic_new}',
                        )
                        self.is_firstrun = False
                    else:
                        for tweet_id in tweetdic_new:
                            if tweet_id > self.tweet_id_old:
                                self.push(tweet_id, tweetdic_new)
                        if tweetdic_new:
                            self.tweet_id_old = sorted(tweetdic_new, reverse=True)[0]
                    writelog(
                        self.logpath,
                        f'[Success] "{self.name}" gettwittertweetdic {self.tgt_restid}',
                    )
                except Exception as e:
                    writelog(
                        self.logpath,
                        f'[Error] "{self.name}" gettwittertweetdic {self.tgt_restid}: {e}',
                    )
            time.sleep(self.interval)

    def push(self, tweet_id, tweetdic):
        tweet = tweetdic[tweet_id]
        # 获取用户推特时大小写不敏感，但检测用户和提及的时候大小写敏感
        pushcolor_vipdic = getpushcolordic(
            f"{self.tgt}\n{tweet['tweet_mention']}", self.vip_dic
        )
        pushcolor_worddic = getpushcolordic(tweet["tweet_text"], self.word_dic)
        pushcolor_dic = addpushcolordic(pushcolor_vipdic, pushcolor_worddic)

        if pushcolor_dic:
            pushtext = f"【{self.__class__.__name__} {self.tgt_name} 推特{tweet['tweet_type']}】\n内容：{tweet['tweet_text']}\n媒体：{tweet['tweet_media']}\n链接：{tweet['tweet_urls']}\n时间：{datetime.utcfromtimestamp(tweet['tweet_timestamp']):DateTimeFormat}\n网址：https://twitter.com/{self.tgt}/status/{tweet_id}"
            pushall(pushtext, pushcolor_dic, self.push_list)
            writelog(
                self.logpath,
                f'[Info] "{self.name}" pushall {str(pushcolor_dic)}\n{pushtext}',
            )
