import datetime
from tweety import Twitter
from feedgen.feed import FeedGenerator
import toml
import os

data = toml.load('./twitter.toml')

# Initialize Twitter API
twitter = Twitter("SESSION")
twitter.load_auth_token(os.environ.get("TWITTER_AUTH_TOKEN"))

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

    # Generate the RSS XML
    fg.rss_file(f'{rss_file_name}.xml', pretty=True)