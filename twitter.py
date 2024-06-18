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
        fg.id(twitter_url)
        fg.title(rss_file_name)
        fg.author({'name': username, 'uri': twitter_url})
        fg.link(href=twitter_url)
        fg.language('en')
        fg.description(rss_file_name)

        # Add tweets to the RSS feed
        for tweet in tweets:
            fe = fg.add_entry()
            tweet_url = f'https://x.com/{username}/status/{tweet.id}'

            scrape_result = scrape_tweet(tweet_url)
            logging.info(f"{tweet_url} has been scrapped by `scrape_tweet`")

            full_text = scrape_result["legacy"]["full_text"].split("https://")[0].strip()
            lang = scrape_result["legacy"]["lang"]
            entities = scrape_result["legacy"]["entities"]
            name = scrape_result["core"]["user_results"]["result"]["legacy"]["name"]
            created_at = scrape_result["legacy"]["created_at"]

            results = {"full_text": full_text, "lang": lang, "media": entities, "name": name, "created_at": created_at}
            logging.info(f"results: {results}")

            if entities.get("media") and entities["media"][0]["type"] == "photo":
                fe.media.content(url=entities["media"][0]["media_url_https"], medium='image') # type: ignore

            fe.id(tweet_url)
            fe.title(f"<![CDATA[ @{username}: {full_text} ]]>")
            fe.description(f'<![CDATA[ <blockquote class="twitter-tweet" data-width="550"><p lang="{lang}" dir="ltr">{full_text}</p>- {name} (@{username}) {created_at}</blockquote> <script async src="https://platform.twitter.com/widgets.js" charset="utf-8"></script> ]]>')
            fe.link(href=tweet_url)
            fe.pubDate(tweet.created_on)

        # Ensure the 'public' directory exists
        os.makedirs('public', exist_ok=True)

        # Generate the RSS XML
        xml_file_name = f'public/{rss_file_name}.xml'
        fg.rss_file(xml_file_name, pretty=True)
        xmls.append(xml_file_name)

    logging.info("Feeds generated in `public/` folder")

    logging.info("They will be published at:")
    for xml in xmls:
        logging.info(f"- https://changchiyou.github.io/wildrift-news-feeds/{xml}")

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

    return dict() # Would not be executed

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s')
    generate_twitter_rss()