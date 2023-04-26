from flask import Flask, Response
from yfinance import getQuotes
import json

app = Flask(__name__)

@app.route('/quotes/<symbol>', methods=['GET'])
def get_quote(symbol):
    quotes = getQuotes(symbol)
    
    if quotes is None:
        return Response(status=404)

    return Response(json.dumps(quotes), status=200, mimetype="application/json")


if __name__ == "__main__":
    app.run(debug=False)