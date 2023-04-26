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

@app.route('/deposit', methods=['POST'])
def deposit():
    # Verify if the client is authenticated
    res = verify(request)

    if res is None:
        return Response(status=401)
    
    clientID = res['clientID']
    
    # Request client's portfolio from Portfolio Management Service
    response = requests.get(f"http://portfolio-mgmt:5000/portfolio/{clientID}")
    
    if not response is None:
        data = response.json()
        old_cash_balance = int(data['Cash'])

        # Get request body
        payload = request.get_json(force=True)

        deposited_cash = int(payload.get('amount'))
        new_cash_balance = old_cash_balance + deposited_cash

        update_payload = {"Cash": str(new_cash_balance)}

        response = requests.put(f"http://portfolio-mgmt:5000/portfolio/{clientID}", json=update_payload)

        return Response(response.text, status=response.status_code, mimetype="json/application")
        
    return Response(status=400)

@app.route('/withdraw', methods=['POST'])
def withdra():
    # Verify if the client is authenticated
    res = verify(request)

    if res is None:
        return Response(status=401)
    
    clientID = res['clientID']
    
    # Request client's portfolio from Portfolio Management Service
    response = requests.get(f"http://portfolio-mgmt:5000/portfolio/{clientID}")
    
    if not response is None:
        data = response.json()
        cash_balance = int(data['Cash'])

        # Get request body
        payload = request.get_json(force=True)

        withdrawn_cash = int(payload.get('amount'))
        new_cash_balance = cash_balance - withdrawn_cash

        if new_cash_balance < 0:
            return Response(json.dumps({'error': 'insufficient funds'}), status=400, mimetype='application/json')

        update_payload = {"Cash": str(new_cash_balance)}

        response = requests.put(f"http://portfolio-mgmt:5000/portfolio/{clientID}", json=update_payload)

        return Response(response.text, status=response.status_code, mimetype="json/application")
        
    return Response(status=400)

if __name__ == "__main__":
    app.run(debug=False)