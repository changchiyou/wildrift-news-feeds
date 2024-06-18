import datetime
from tweety import Twitter
from feedgen.feed import FeedGenerator
import toml
import os
import logging


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

        twitter_url = f'https://twitter.com/{username}'

        # Create RSS feed
        fg = FeedGenerator()
        fg.id(twitter_url)
        fg.title(rss_file_name)
        fg.author({'name': username, 'uri': twitter_url})
        fg.link(href=twitter_url)
        fg.language('en')
        fg.description(data[rss_file_name]["description"])

        # Add tweets to the RSS feed
        for tweet in tweets:
            fe = fg.add_entry()
            tweet_url = f'https://twitter.com/{username}/status/{tweet.id}'

            fe.id(tweet_url)
            fe.title(tweet.id)
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

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s')
    generate_twitter_rss()