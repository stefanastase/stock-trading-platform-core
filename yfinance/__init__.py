import json
import sys
from lxml import html
import requests

def buildUrl(symbol):
    # Get Yahoo! Finance URL for symbol
    return f'https://finance.yahoo.com/quote/{symbol}/'

def request(symbol):
    url = buildUrl(symbol)
    page = requests.get(url)
    tree = html.fromstring(page.content)

    # Get element using XPath
    price = tree.xpath("/html/body/div[1]/div/div/div[1]/div/div[2]/div/div/div[6]/div/div/div/div[3]/div[1]/div[1]/fin-streamer[1]")
    content = {}
    try:
        content['price'] = float(price[0].text)
    except:
        return None

    return content

def getQuotes(symbol):
    content = request(symbol)
    return content

if __name__ == '__main__':
    try:
        symbol = sys.argv[1]
    except:
        symbol = "AAPL"

    print(getQuotes(symbol))        
