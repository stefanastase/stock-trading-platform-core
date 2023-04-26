from flask import Flask, request, Response
from yfinance import getQuotes
import json
import requests
app = Flask(__name__)

def verify(request):
    authHeader = request.headers.get('authorization')
    
    if authHeader is None:
        return None
    
    headers = {'Authorization' : authHeader}
    response = requests.post("http://auth:5000/verify", headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        return None
        
@app.route('/quotes/<symbol>', methods=['GET'])
def get_quotes(symbol):
    quotes = getQuotes(symbol)
    
    if quotes is None:
        return Response(status=404)

    return Response(json.dumps(quotes), status=200, mimetype="application/json")

@app.route('/portfolio', methods=['GET'])
def get_portfolio():
    # Verify if the client is authenticated
    res = verify(request)

    if res is None:
        return Response(status=401)
    
    clientID = res['clientID']

    # Request client's portfolio from Portfolio Management Service
    response = requests.get(f"http://portfolio-mgmt:5000/portfolio/{clientID}")

    if not response is None:
        return Response(response.text, status=response.status_code, mimetype="application/json")

    return Response(status=400)


if __name__ == "__main__":
    app.run(debug=False)