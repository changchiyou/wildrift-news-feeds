import datetime
from tweety import TwitterAsync
from feedgen.feed import FeedGenerator
import toml
import os
import logging
from playwright.async_api import async_playwright
import jmespath
import asyncio

async def generate_twitter_rss():
    logging.info("Starting `generate_twitter_rss` function")
    data = toml.load('./twitter.toml')
    logging.info("`./twitter.toml` loaded successfully")

    # Initialize Twitter API
    twitter = TwitterAsync("SESSION")
    logging.info("TwitterAsync API initialized")

    # Signing In using Credentials
    # account, password, extra = os.environ.get("TWITTER_ACCOUNT_PASSWORD", "").split()
    # await twitter.start(account, password, extra=extra)
    # logging.info(f"logged in as `{twitter.user}`")

    # Signing In using Cookies
    # https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm?utm_campaign=cgagnier.ca
    # Export -> Header String
    cookie_value = os.environ.get("TWITTER_COOKIE_VALUE", "")
    await twitter.load_cookies(cookie_value)
    logging.info("twitter.load_cookies success")

    # To test in local, execute following cmd in terminal:
    # export TWITTER_AUTH_TOKEN=<your token>
    # twitter.load_auth_token(os.environ.get("TWITTER_AUTH_TOKEN"))
    # logging.info("twitter.load_auth_token success")

    xmls = []

    for rss_file_name in data:
        logging.info(f"Processing `{rss_file_name}`")
        username = data[rss_file_name]["username"]
        logging.info(f"Fetching tweets from user `{username}`")

        # Advanced Search - X/Twitter
        today_date = datetime.datetime.now().strftime(r'%Y-%m-%d')
        query = f'(from:{username}) since:{today_date}'
        logging.info(f"Search query: `{query}`")
        tweets = await twitter.search(query)

        # Sort from old to new
        tweets = sorted(list(tweets), key=lambda tweet: tweet.created_on, reverse=False)
        logging.info("Sorted tweets from old to new")

        twitter_url = f'https://x.com/{username}'
        logging.info(f"Twitter URL: `{twitter_url}`")

        # Create RSS feed
        fg = FeedGenerator()
        fg.load_extension('media')
        fg.id(twitter_url)
        fg.title(data[rss_file_name]["rssname"])
        fg.author({'name': username, 'uri': twitter_url})
        fg.link(href=twitter_url)
        fg.language('en')
        fg.description(data[rss_file_name]["rssname"])

        # Add tweets to the RSS feed
        for tweet in tweets:
            logging.info(f"Processing tweet ID `{tweet.id}`")
            fe = fg.add_entry()
            tweet_url = f'https://x.com/{username}/status/{tweet.id}'

            result = parse_tweet(await scrape_tweet(tweet_url))
            logging.info(f"Scraped tweet ID `{tweet.id}`")

            reply_to = f"reply to @{result['in_reply_to_screen_name']} " if result['in_reply_to_screen_name'] else ""
            title = f"{result['username']} (@{result['userid']}) {reply_to}on X"

            description = result["full_text"]
            media_urls = result["media_urls"]

            if media_urls:
                for attached_url in media_urls:
                    description = description.replace(attached_url, '')

                media_includes = set()
                for media_expanded_url, media_type \
                    in zip(result["media_expanded_urls"], result["media_types"]):
                    match media_type:
                        case "photo":
                            media_includes.add("🌄")
                            medium = "image"
                            media_found_log = "Found [image] media: "
                        case "video"|"animated_gif":
                            media_includes.add("🎬")
                            medium = "image"
                            media_found_log = f"Found [{media_type}] media but only embed preview image: "
                        case _:
                            continue

                    fe.media.content(url=media_expanded_url, medium=medium)  # type: ignore
                    logging.info(f"{media_found_log}{media_expanded_url}")

                if media_includes:
                    title += " " + "".join(media_includes)

            fe.title(title)
            fe.description(description)
            fe.id(tweet_url)
            fe.link(href=tweet_url)
            fe.pubDate(tweet.created_on)

        # Ensure the 'public' directory exists
        os.makedirs('public', exist_ok=True)
        logging.info(f"'public' directory ensured")

        # Generate the RSS XML
        xml_file_name = f'public/{rss_file_name}.xml'
        fg.rss_file(xml_file_name, pretty=True)
        xmls.append(xml_file_name)

        logging.info(f"{xml_file_name} has been generated")

    logging.info("Feeds generated in `public/` folder")

    logging.info("They will be published at:")
    for xml in xmls:
        base_name = os.path.basename(xml)
        logging.info(f"- https://changchiyou.github.io/wildrift-news-feeds/{base_name")

def parse_tweet(data: dict) -> dict:
    """
    Parse Twitter tweet JSON dataset for the most important fields.

    Reference: https://scrapfly.io/blog/how-to-scrape-twitter/
    """
    logging.info("Parsing tweet data")
    result = jmespath.search(
        """{
        userid: core.user_results.result.legacy.screen_name,
        username: core.user_results.result.legacy.name,
        created_at: legacy.created_at,
        attached_display_urls: legacy.entities.urls[].display_url,
        attached_expanded_urls: legacy.entities.urls[].expanded_url,
        attached_urls: legacy.entities.urls[].url,
        media_expanded_urls: legacy.entities.media[].media_url_https,
        media_types: legacy.entities.media[].type,
        media_urls: legacy.entities.media[].url,
        media_video_info: legacy.entities.media[].video_info,
        tagged_userids: legacy.entities.user_mentions[].screen_name,
        tagged_hashtags: legacy.entities.hashtags[].text,
        full_text: legacy.full_text,
        lang: legacy.lang,
        in_reply_to_screen_name: legacy.in_reply_to_screen_name
    }""",
        data,
    )
    logging.info("Parsed tweet data successfully")
    return result

async def scrape_tweet(url: str) -> dict:
    """
    Scrape a single tweet page for Tweet thread e.g.:
    Return parent tweet, reply tweets and recommended tweets

    Reference: https://scrapfly.io/blog/how-to-scrape-twitter/
    """
    logging.info(f"Starting to scrape tweet from URL: `{url}`")
    _xhr_calls = []

    def intercept_response(response):
        """capture all background requests and save them"""
        # we can extract details from background requests
        if response.request.resource_type == "xhr":
            _xhr_calls.append(response)
        return response

    async with async_playwright() as pw:
        browser = await pw.firefox.launch()
        logging.info("Launched Firefox browser")
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        logging.info("Created new browser context")
        page = await context.new_page()

        # enable background request intercepting:
        page.on("response", intercept_response)
        logging.info("Enabled response interception")
        # go to url and wait for the page to load
        await page.goto(url, wait_until="domcontentloaded")
        logging.info("Navigated to tweet URL and waiting for content to load")
        await page.wait_for_selector("[data-testid='tweet']")
        logging.info("Tweet content loaded")

        # find all tweet background requests:
        tweet_calls = [f for f in _xhr_calls if "TweetResultByRestId" in f.url]
        # logging.info(f"Captured background requests for tweets: {tweet_calls}")
        logging.info(f"Captured background requests for tweets")
        for xhr in tweet_calls:
            try:
                data = await xhr.json()
                logging.info(f"Scraped data from tweet URL: `{url}`")
                return data['data']['tweetResult']['result']
            except Exception as e:
                logging.error(f"Failed to parse JSON from response: {e}")
                logging.error(f"Response content: {await xhr.text()}")

    logging.info(f"{url} has been scrapped by `scrape_tweet`")

    return dict() # Would not be executed

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s')
    logging.info("Script execution started")
    retries = 3
    for attempt in range(retries):
        try:
            asyncio.run(generate_twitter_rss())
            break  # Exit loop if no exception is raised
        except Exception as e:
            logging.error(f"Attempt {attempt + 1} of {retries} failed.")
            if attempt == retries - 1:
                logging.error("Maximum retries reached. Raising exception.")
                raise e
            else:
                logging.info("Retrying...")
