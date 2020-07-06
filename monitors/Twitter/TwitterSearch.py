from ..BaseMonitor import BaseMonitor
from ..Utils import writelog, addpushcolordic, getpushcolordic, pushall
from ..Youtube.YoutubeLive import YoutubeLive

from .TwitterConstants import SearchParams, Headers

from pathlib import Path
from datetime import datetime
import time
import requests

# vip=tgt+mention, word=text, only_live="True"/"False", only_liveorvideo="True"/"False", "no_chat"="True"/"False"
class TwitterSearch(BaseMonitor):
    @staticmethod
    def gettwittersearchdic(qword, cookies, proxy):
        try:
            tweet_dic = {}
            # 推文内容包括#话题标签的文字，filter:links匹配链接图片视频但不匹配#话题标签的链接，%%23相当于#话题标签
            params = {**SearchParams}
            headers = {**Headers, "x-csrf-token": cookies["ct0"]}
            url = (
                "https://api.twitter.com/2/search/adaptive.json?include_profile_interstitial_type=1&include_blocking=1&include_blocked_by=1&include_followed_by=1&include_want_retweets=1&include_mute_edge=1&include_can_dm=1&include_can_media_tag=1&skip_status=1&cards_platform=Web-12&include_cards=1&include_composer_source=true&include_ext_alt_text=true&include_reply_count=1&tweet_mode=extended&include_entities=true&include_user_entities=true&include_ext_media_color=true&include_ext_media_availability=true&send_error_codes=true&simple_quoted_tweets=true&q="
                + qword
                + "&tweet_search_mode=live&count=20&query_source=typed_query&pc=1&spelling_corrections=1&ext=mediaStats%2CcameraMoment"
            )
            response = requests.get(
                url,
                headers=headers,
                params=params,
                cookies=cookies,
                timeout=(3, 7),
                proxies=proxy,
            )

            if "globalObjects" in response.json():
                tweetlist_dic = response.json()["globalObjects"]["tweets"]
                for tweet_id in tweetlist_dic.keys():
                    tweet_timestamp = datetime.strptime(
                        tweetlist_dic[tweet_id]["created_at"], "%a %b %d %H:%M:%S %z %Y"
                    ).timestamp()
                    tweet_text = tweetlist_dic[tweet_id]["full_text"]
                    if "retweeted_status_id_str" in tweetlist_dic[tweet_id]:
                        tweet_type = "转推"
                    # 不同于用户推特，总是有user_mentions键
                    elif tweetlist_dic[tweet_id]["entities"]["user_mentions"]:
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

        logpath = Path(f"./log/{self.__class__.__name__}")
        self.logpath = logpath / f"{self.name}.txt"
        if not logpath.exists():
            logpath.mkdir(parents=True)

        self.is_firstrun = True
        self.tweet_id_old = 0
        # 是否只推送有链接指向正在进行的youtube直播的推文
        self.only_live = getattr(self, "only_live", "False")
        # 是否只推送有链接指向youtube直播或视频的推文
        self.only_liveorvideo = getattr(self, "only_liveorvideo", "False")

    def run(self):
        while not self.stop_now:
            # 获取推特列表
            try:
                tweetdic_new = TwitterSearch.gettwittersearchdic(
                    self.tgt, self.cookies, self.proxy
                )
                if self.is_firstrun:
                    if tweetdic_new:
                        self.tweet_id_old = sorted(tweetdic_new, reverse=True)[0]
                    writelog(
                        self.logpath,
                        f'[Info] "{self.name}" gettwittersearchdic {self.tgt}: {tweetdic_new}',
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
                    f'[Success] "{self.name}" gettwittersearchdic {self.tgt}',
                )
            except Exception as e:
                writelog(
                    self.logpath,
                    f'[Error] "{self.name}" gettwittersearchdic {self.tgt}: {e}',
                )
            time.sleep(self.interval)

    def push(self, tweet_id, tweetdic):
        tweet = tweetdic[tweet_id]
        # 检测是否有链接指向正在进行的直播
        if self.only_live == "True":
            is_live = False
            for url in tweet["tweet_urls"]:
                if "https://youtu.be/" in url:
                    if (
                        YoutubeLive.getyoutubevideostatus(
                            url.replace("https://youtu.be/", ""),
                            self.cookies,
                            self.proxy,
                        )
                        == "开始"
                    ):
                        is_live = True
                        break
        else:
            is_live = True

        # 检测是否有链接指向直播或视频
        if self.only_liveorvideo == "True":
            is_liveorvideo = False
            for url in tweet["tweet_urls"]:
                if "https://youtu.be/" in url:
                    is_liveorvideo = True
                    break
        else:
            is_liveorvideo = True

        if is_live and is_liveorvideo:
            pushcolor_vipdic = getpushcolordic(
                f"{self.tgt}\n{tweet['tweet_metion']}", self.vip_dic
            )
            pushcolor_worddic = getpushcolordic(tweet["tweet_text"], self.word_dic)
            pushcolor_dic = addpushcolordic(pushcolor_vipdic, pushcolor_worddic)

            if pushcolor_dic:
                pushtext = f"【{self.__class__.__name__} {self.tgt_name} 推特】\n内容：{tweet['tweet_text']}\n媒体：{tweet['tweet_media']}\n链接：{tweet['tweet_urls']}\n时间：{datetime.utcfromtimestamp(tweet['tweet_timestamp']):%Y-%m%d %H:%M:%S %Z}\n网址：https://twitter.com/a/status/{tweet_id}"
                pushall(pushtext, pushcolor_dic, self.push_list)
                writelog(
                    self.logpath,
                    f'[Info] "{self.name}" pushall {str(pushcolor_dic)}\n{pushtext}',
                )
