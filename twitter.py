import datetime
from tweety import Twitter
from feedgen.feed import FeedGenerator
import toml
import os
import logging
from playwright.sync_api import sync_playwright


def generate_twitter_rss():
    data = toml.load('./twitter.toml')
    logging.info("`./twitter.toml` loaded successfully")

    # Initialize Twitter API
    twitter = Twitter("SESSION")
    twitter.load_auth_token(os.environ.get("TWITTER_AUTH_TOKEN"))
    logging.info("twitter.load_auth_token success")

    xmls = []
    DISCORD_TITLE_LENGTH_LIMIT = 256
    DISCORD_DESCRIPTION_LENGTH_LIMIT = 2048

    for rss_file_name in data:
        username = data[rss_file_name]["username"]

        # Advanced Search - X/Twitter
        today_date = datetime.datetime.now().strftime(r'%Y-%m-%d')
        query = f'(from:wildrift) since:{today_date}'
        tweets = twitter.search(query)

        # Sort from old to new
        tweets = sorted(list(tweets), key=lambda tweet: tweet.created_on, reverse=False)

        twitter_url = f'https://x.com/{username}'

        # Create RSS feed
        fg = FeedGenerator()
        fg.load_extension('media')
        fg.load_extension('dc')
        fg.id(twitter_url)
        fg.title(data[rss_file_name]["rssname"])
        fg.author({'name': username, 'uri': twitter_url})
        fg.link(href=twitter_url)
        fg.language('en')
        fg.description(data[rss_file_name]["rssname"])

        # Add tweets to the RSS feed
        for tweet in tweets:
            fe = fg.add_entry()
            tweet_url = f'https://x.com/{username}/status/{tweet.id}'

            scrape_result = scrape_tweet(tweet_url)

            full_text = scrape_result["legacy"]["full_text"].split("https://")[0].strip()
            entities = scrape_result["legacy"]["entities"]
            name = scrape_result["core"]["user_results"]["result"]["legacy"]["name"]
            created_at = scrape_result["legacy"]["created_at"]

            in_reply_to_screen_name = scrape_result["legacy"].get("in_reply_to_screen_name")
            in_reply_to_status_id_str = scrape_result["legacy"].get("in_reply_to_status_id_str")
            title_prefix: str
            title_content: str
            description_content: str
            description_suffix: str

            if in_reply_to_screen_name and in_reply_to_status_id_str:
                reply_to_tweet_url = f'https://x.com/{in_reply_to_screen_name}/status/{in_reply_to_status_id_str}'
                logging.info(f"This is in response to another Twitter thread({reply_to_tweet_url}), not a standalone post of his own.")

                reply_scrape_result = scrape_tweet(reply_to_tweet_url)
                reply_full_text = reply_scrape_result["legacy"]["full_text"].split("https://")[0].strip()
                reply_name = reply_scrape_result["core"]["user_results"]["result"]["legacy"]["name"]
                reply_username = reply_scrape_result["core"]["user_results"]["result"]["legacy"]["screen_name"]
                reply_created_at = reply_scrape_result["legacy"]["created_at"]

                title_prefix = f"@{reply_username}: RT by @{username}: "
                title_content = resize_str(full_text, title_prefix, DISCORD_TITLE_LENGTH_LIMIT)

                description_suffix = f"- {reply_name} (@{reply_username}) {reply_created_at}"
                description_content = resize_str(reply_full_text, description_suffix, DISCORD_DESCRIPTION_LENGTH_LIMIT)
            else:
                title_prefix = f"@{username}: "
                title_content = resize_str(full_text, title_prefix, DISCORD_TITLE_LENGTH_LIMIT)

                description_suffix = f"- {name} (@{username}) {created_at}"
                description_content = resize_str(full_text, description_suffix, DISCORD_DESCRIPTION_LENGTH_LIMIT)

            fe.title(title_prefix + title_content)
            fe.description(description_content + description_suffix)

            if entities.get("media") and entities["media"][0]["type"] == "photo":
                media_url = entities["media"][0]["media_url_https"]
                fe.media.content(url=media_url, medium='image') # type: ignore
                logging.info(f"Found {len(entities.get('media'))} medias, picked 1 of them: {media_url}")

            fe.id(tweet_url)
            fe.link(href=tweet_url)
            fe.pubDate(tweet.created_on)
            fe.dc.dc_creator(f"@{username}") # type: ignore

        # Ensure the 'public' directory exists
        os.makedirs('public', exist_ok=True)

        # Generate the RSS XML
        xml_file_name = f'public/{rss_file_name}.xml'
        fg.rss_file(xml_file_name, pretty=True)
        xmls.append(xml_file_name)

        logging.info(f"{xml_file_name} has been generated")

    logging.info("Feeds generated in `public/` folder")

    logging.info("They will be published at:")
    for xml in xmls:
        logging.info(f"- https://changchiyou.github.io/wildrift-news-feeds/{xml}")

def resize_str(a: str, b: str, size: int):
    """Resize a to make len(a)+len(b) <= size. If a has to be resized, add ... at the end of it."""
    return a if len(a) + len(b) <= size else a[:size-len(b)-2]+'...'

def scrape_tweet(url: str) -> dict:
    """
    Scrape a single tweet page for Tweet thread e.g.:
    Return parent tweet, reply tweets and recommended tweets

    Reference: https://scrapfly.io/blog/how-to-scrape-twitter/
    """
    _xhr_calls = []

    def intercept_response(response):
        """capture all background requests and save them"""
        # we can extract details from background requests
        if response.request.resource_type == "xhr":
            _xhr_calls.append(response)
        return response

    with sync_playwright() as pw:
        browser = pw.firefox.launch()
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        # enable background request intercepting:
        page.on("response", intercept_response)
        # go to url and wait for the page to load
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_selector("[data-testid='tweet']")

        # find all tweet background requests:
        tweet_calls = [f for f in _xhr_calls if "TweetResultByRestId" in f.url]
        for xhr in tweet_calls:
            data = xhr.json()
            return data['data']['tweetResult']['result']

    logging.info(f"{url} has been scrapped by `scrape_tweet`")

    return dict() # Would not be executed

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s')
    generate_twitter_rss()