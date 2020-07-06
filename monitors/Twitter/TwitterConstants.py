Params = {
    "include_profile_interstitial_type": "1",
    "include_blocking": "1",
    "include_blocked_by": "1",
    "include_followed_by": "1",
    "include_want_retweets": "1",
    "include_mute_edge": "1",
    "include_can_dm": "1",
    "include_can_media_tag": "1",
    "skip_status": "1",
    "cards_platform": "Web-12",
    "include_cards": "1",
    "include_composer_source": "true",
    "include_ext_alt_text": "true",
    "include_reply_count": "1",
    "tweet_mode": "extended",
    "include_entities": "true",
    "include_user_entities": "true",
    "include_ext_media_color": "true",
    "include_ext_media_availability": "true",
    "send_error_codes": "true",
    "simple_quoted_tweets": "true",
    "count": "20",
    "ext": "mediaStats,cameraMoment",
}

TweetParams = {**Params, "include_tweet_replies": "true", "userId": None}
SearchParams = {
    **Params,
    "tweet_search_mode": "live",
    "query_source": "typed_query",
    "pc": "1",
    "spelling_corrections": "1",
}

Headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:72.0) Gecko/20100101 Firefox/72.0",
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
    "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
    "x-twitter-auth-type": "OAuth2Session",
    "x-twitter-client-language": "zh-cn",
    "x-twitter-active-user": "yes",
    "x-csrf-token": None,
    "Origin": "https://twitter.com",
    "Connection": "keep-alive",
    "TE": "Trailers",
}
