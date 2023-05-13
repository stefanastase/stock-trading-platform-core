from flask import Flask, request, Response
from yfinance import getQuotes
import json
import requests
from datetime import datetime

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

@app.route('/quotes/<symbol>/buy', methods=['POST'])
def place_buy_order(symbol):
    # Verify if the client is authenticated
    res = verify(request)

    if res is None:
        return Response(status=401)
    
    clientID = res['clientID']

    payload = request.get_json(force=True)
    quantity = int(payload['quantity'])
    price = float(payload['price'])

    # Request client's portfolio from Portfolio Management Service
    response = requests.get(f"http://portfolio-mgmt:5000/portfolio/{clientID}")

    if not response is None:
        portfolio = response.json()
        if float(portfolio['Cash']) < price * quantity:
            return Response(json.dumps({'error': 'insufficient funds'}), status=400, mimetype='application/json')
    else:
        return Response(json.dumps({'error': 'portfolio not found'}), status=400, mimetype='application/json')
    
    order_payload = {
        "client_id": clientID,
        "symbol": symbol,
        "type": 'B',
        "quantity": quantity,
        "price": price,
        "placed_at": datetime.now().isoformat()
    }

    response = requests.post("http://order-mgmt:5000/orders", json=order_payload)
    return Response(json.dumps(response.json()), status=response.status_code, mimetype='application/json')

@app.route('/quotes/<symbol>/sell', methods=['POST'])
def place_sell_order(symbol):
    # Verify if the client is authenticated
    res = verify(request)

    if res is None:
        return Response(status=401)
    
    clientID = res['clientID']

    payload = request.get_json(force=True)
    quantity = int(payload['quantity'])
    price = float(payload['price'])

    # Request client's portfolio from Portfolio Management Service
    response = requests.get(f"http://portfolio-mgmt:5000/portfolio/{clientID}")

    if not response is None:
        portfolio = response.json()
        if portfolio.get(symbol) is None:
            return Response(json.dumps({'error': 'symbol not found in portfolio'}), status=400, mimetype='application/json')
        elif float(portfolio[symbol]) < quantity:
            return Response(json.dumps({'error': 'quantity of order exceeds available amount'}), status=400, mimetype='application/json')
    else:
        return Response(json.dumps({'error': 'portfolio not found'}), status=400, mimetype='application/json')
    
    order_payload = {
        "client_id": clientID,
        "symbol": symbol,
        "type": 'S',
        "quantity": quantity,
        "price": price,
        "placed_at": datetime.now().isoformat()
    }

    response = requests.post("http://order-mgmt:5000/orders", json=order_payload)
    return Response(json.dumps(response.json()), status=response.status_code, mimetype='application/json')

@app.route('/orders', methods=['GET'])
def get_orders():
    # Verify if the client is authenticated
    res = verify(request)

    if res is None:
        return Response(status=401)
    
    clientID = res['clientID']

    response = requests.get(f"http://order-mgmt:5000/orders/client/{clientID}")
    return Response(json.dumps(response.json()), status=response.status_code, mimetype='application/json')

@app.route('/orders/<id>', methods=['PUT'])
def update_order(id):
    # Verify if the client is authenticated
    res = verify(request)

    if res is None:
        return Response(status=401)
    
    clientID = res['clientID']

    get_response = requests.get(f"http://order-mgmt:5000/orders/{id}")

    if get_response.status_code != 200:
        return Response(status=get_response.status_code)
    
    order_json = get_response.json()
    if order_json['ClientID'] != clientID:
        return Response(status=401)
    
    payload = request.get_json(force=True)
    quantity = int(payload['quantity'])
    price = float(payload['price'])

    if order_json['Type'] == 'B':
        # Request client's portfolio from Portfolio Management Service
        response = requests.get(f"http://portfolio-mgmt:5000/portfolio/{clientID}")

        if not response is None:
            portfolio = response.json()
            if float(portfolio['Cash']) < price * quantity:
                return Response(json.dumps({'error': 'insufficient funds'}), status=400, mimetype='application/json')
        else:
            return Response(json.dumps({'error': 'portfolio not found'}), status=400, mimetype='application/json')
    else:
        # Request client's portfolio from Portfolio Management Service
        response = requests.get(f"http://portfolio-mgmt:5000/portfolio/{clientID}")

        if not response is None:
            portfolio = response.json()
            symbol = order_json.get("Symbol")
            
            if portfolio.get(symbol) is None:
                return Response(json.dumps({'error': 'symbol not found in portfolio'}), status=400, mimetype='application/json')
            elif float(portfolio[symbol]) < quantity:
                return Response(json.dumps({'error': 'quantity of order exceeds available amount'}), status=400, mimetype='application/json')
        else:
            return Response(json.dumps({'error': 'portfolio not found'}), status=400, mimetype='application/json')
        
    update_payload = {
        "quantity": quantity,
        "price": price,
        "placed_at": datetime.now().isoformat()
    }

    response=requests.put(f"http://order-mgmt:5000/orders/{id}", json=update_payload)

    return Response(json.dumps(response.json()), status=response.status_code, mimetype='application/json')

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
        value = 0.0
        # Append total value of portfolio to response
        portfolio = response.json()
        for symbol in portfolio:
            if symbol == 'Cash':
                value += float(portfolio[symbol])
            else:
                price = getQuotes(symbol).get('price')
                quantity = int(portfolio[symbol])
                value += price * quantity

        portfolio['Value'] = value
        return Response(json.dumps(portfolio), status=response.status_code, mimetype="application/json")

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
def withdraw():
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