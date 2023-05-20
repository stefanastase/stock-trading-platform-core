from flask import Flask, request, Response
from yfinance import getQuotes
import json
import requests
from datetime import datetime
import os
from logging.config import dictConfig

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    }},
    'root': {
        'level': 'INFO',
        'handlers': ['wsgi']
    }
})

app = Flask(__name__)

order_secret_file = os.getenv('ORDER_SECRET_FILE')

def verify(request):
    authHeader = request.headers.get('authorization')
    
    if authHeader is None:
        app.logger.error("No token provided.")
        return None
    
    headers = {'Authorization' : authHeader}
    response = requests.post("http://auth:5000/verify", headers=headers)
    app.logger.debug("Response received from Auth Service.")

    if response.status_code == 200:
        app.logger.info(f"Token is valid.")  
        return response.json()
    else:
        app.logger.error(f"Token is invalid.")  
        return None
        
@app.route('/quotes/<symbol>', methods=['GET'])
def get_quotes(symbol):
    quotes = getQuotes(symbol)
    app.logger.debug(f"Got quotes for symbol {symbol}.")

    if quotes is None:
        app.logger.error(f"The symbol {symbol} could not be found") 
        return Response(status=404)

    response = requests.get(f"http://order-mgmt:5000/depth/{symbol}")
    app.logger.debug(f"Response  with depth for {symbol} received from Order Management Service.")

    if response.status_code == 200:
        app.logger.info(f"Returning quote for {symbol} with depth information")
        quotes['depth']  = response.json()
    else:
        app.logger.info(f"Returning quote for {symbol} without depth information")

    return Response(json.dumps(quotes), status=200, mimetype="application/json")

@app.route('/quotes/<symbol>/buy', methods=['POST'])
def place_buy_order(symbol):
    # Verify if the client is authenticated
    res = verify(request)
    app.logger.debug(f"Request token was verified.")
    if res is None:
        app.logger.error("Client provided invalid token for authentication.")
        return Response(status=401)
    
    clientID = res['clientID']
    app.logger.debug(f"Client ID is {clientID}")

    payload = request.get_json(force=True)
    quantity = int(payload['quantity'])
    price = float(payload['price'])
    app.logger.debug(f"Client {clientID} placed order with: qty={quantity}, price={price}.")
    # Request client's portfolio from Portfolio Management Service
    response = requests.get(f"http://portfolio-mgmt:5000/portfolio/{clientID}")
    app.logger.debug(f"Got response from Portfolio Management Service")
    if not response is None:
        app.logger.info(f"Received portfolio for client {clientID}")
        portfolio = response.json()
        if float(portfolio['Cash']) < price * quantity:
            app.logger.error(f"Client {clientID} has insufficient funds to place buy order.")
            return Response(json.dumps({'error': 'insufficient funds'}), status=400, mimetype='application/json')
    else:
        app.logger.error(f"Portfolio for client {clientID} not found")
        return Response(json.dumps({'error': 'portfolio not found'}), status=400, mimetype='application/json')
    
    order_payload = {
        "client_id": clientID,
        "symbol": symbol,
        "type": 'B',
        "quantity": quantity,
        "price": price,
        "placed_at": datetime.now().isoformat()
    }
    app.logger.info(f"{clientID}: BUY {quantity} {symbol} @ {price}")
    app.logger.debug(f"Sending BUY order from {clientID} to Order Management")
    response = requests.post("http://order-mgmt:5000/orders", json=order_payload)
    app.logger.debug(f"Received response from Order Management for {clientID}'s BUY order.")

    if response.status_code == 200:
        app.logger.info(f"Buy Order of {clientID} executed directly.")
    elif response.status_code == 201:
        app.logger.info(f"Buy Order of {clientID} was placed, but not executed yet.")
    else:
        app.logger.error(f"Buy Order of {clientID} could not be placed.")

    return Response(json.dumps(response.json()), status=response.status_code, mimetype='application/json')

@app.route('/quotes/<symbol>/sell', methods=['POST'])
def place_sell_order(symbol):
    # Verify if the client is authenticated
    res = verify(request)
    app.logger.debug(f"Request token was verified.")
    if res is None:
        app.logger.error("Client provided invalid token for authentication.")
        return Response(status=401)
    
    clientID = res['clientID']
    app.logger.debug(f"Client ID is {clientID}")

    payload = request.get_json(force=True)
    quantity = int(payload['quantity'])
    price = float(payload['price'])
    app.logger.debug(f"Client{clientID} placed order with: qty={quantity}, price={price}.")
    # Request client's portfolio from Portfolio Management Service
    response = requests.get(f"http://portfolio-mgmt:5000/portfolio/{clientID}")
    app.logger.debug(f"Got response from Portfolio Management Service")
    if not response is None:
        app.logger.info(f"Received portfolio for client {clientID}")
        portfolio = response.json()
        if portfolio.get(symbol) is None:
            app.logger.error(f"Client {clientID} does not have symbol {symbol} in their portfolio.")
            return Response(json.dumps({'error': 'symbol not found in portfolio'}), status=400, mimetype='application/json')
        elif float(portfolio[symbol]) < quantity:
            app.logger.error(f"Client {clientID} does not have enough qunatity of {symbol} in their portfolio. ({portfolio['symbol']} vs. {quantity})")
            return Response(json.dumps({'error': 'quantity of order exceeds available amount'}), status=400, mimetype='application/json')
    else:
        app.logger.error(f"Portfolio for client {clientID} not found")
        return Response(json.dumps({'error': 'portfolio not found'}), status=400, mimetype='application/json')
    
    order_payload = {
        "client_id": clientID,
        "symbol": symbol,
        "type": 'S',
        "quantity": quantity,
        "price": price,
        "placed_at": datetime.now().isoformat()
    }
    app.logger.info(f"{clientID}: SELL {quantity} {symbol} @ {price}")
    app.logger.debug(f"Sending SELL order from {clientID} to Order Management")
    response = requests.post("http://order-mgmt:5000/orders", json=order_payload)
    app.logger.debug(f"Received response from Order Management for {clientID}'s SELL order.")

    if response.status_code == 200:
        app.logger.info(f"Sell Order of {clientID} executed directly.")
    elif response.status_code == 201:
        app.logger.info(f"Sell Order of {clientID} was placed, but not executed yet.")
    else:
        app.logger.error(f"Sell Order of {clientID} could not be placed.")

    return Response(json.dumps(response.json()), status=response.status_code, mimetype='application/json')


@app.route('/orders', methods=['GET'])
def get_orders():
    # Verify if the client is authenticated
    res = verify(request)
    app.logger.debug(f"Request token was verified.")
    if res is None:
        app.logger.error("Client provided invalid token for authentication.")
        return Response(status=401)
    
    clientID = res['clientID']
    app.logger.debug(f"Client ID is {clientID}")

    response = requests.get(f"http://order-mgmt:5000/orders/client/{clientID}")
    app.logger.debug(f"Received response for GET {clientID} orders")

    if response.status_code == 200:
        app.logger.info(f"Orders of {clientID} received.")
    else:
        app.logger.error(f"Orders of {clientID} were not received.")
    return Response(json.dumps(response.json()), status=response.status_code, mimetype='application/json')

@app.route('/orders/<id>', methods=['PUT'])
def update_order(id):
    # Verify if the client is authenticated
    res = verify(request)
    app.logger.debug(f"Request token was verified.")
    if res is None:
        app.logger.error("Client provided invalid token for authentication.")
        return Response(status=401)
    
    clientID = res['clientID']
    app.logger.debug(f"Client ID is {clientID}")

    get_response = requests.get(f"http://order-mgmt:5000/orders/{id}")
    app.logger.debug(f"Got response for GET ORDER BY ID (id={id})")

    if get_response.status_code == 404:
        app.logger.error(f"Order with id={id} not found.")
        return Response(status=get_response.status_code)
    elif get_response.status_code == 400:
        app.logger.error(f"Order with id={id} could not be fetched succesfully.")
        return Response(status=get_response.status_code)
    
    app.logger.info(f"Order with id={id} found.")
    order_json = get_response.json()
    if order_json['ClientID'] != clientID:
        app.logger.error(f"Order with id={id} was not placed by {clientID}.")
        return Response(status=401)
    
    payload = request.get_json(force=True)
    quantity = int(payload['quantity'])
    price = float(payload['price'])
    app.logger.debug(f"Client {clientID} updated order id={id} with: qty={quantity}, price={price}.")
    if order_json['Type'] == 'B':
        # Request client's portfolio from Portfolio Management Service
        response = requests.get(f"http://portfolio-mgmt:5000/portfolio/{clientID}")
        app.logger.debug(f"Got response from Portfolio Management Service")
        if not response is None:
            app.logger.info(f"Received portfolio for client {clientID}")
            portfolio = response.json()
            if float(portfolio['Cash']) < price * quantity:
                app.logger.error(f"Client {clientID} has insufficient funds to place buy order.")
                return Response(json.dumps({'error': 'insufficient funds'}), status=400, mimetype='application/json')
        else:
            app.logger.error(f"Portfolio for client {clientID} not found")
            return Response(json.dumps({'error': 'portfolio not found'}), status=400, mimetype='application/json')
    else:
        # Request client's portfolio from Portfolio Management Service
        response = requests.get(f"http://portfolio-mgmt:5000/portfolio/{clientID}")
        app.logger.debug("Got response from Portfolio Management Service")
        if not response is None:
            portfolio = response.json()
            symbol = order_json.get("Symbol")

            if portfolio.get(symbol) is None:
                app.logger.error(f"Client {clientID} does not have symbol {symbol} in their portfolio.")
                return Response(json.dumps({'error': 'symbol not found in portfolio'}), status=400, mimetype='application/json')
            elif float(portfolio[symbol]) < quantity:
                app.logger.error(f"Client {clientID} does not have enough qunatity of {symbol} in their portfolio. ({portfolio['symbol']} vs. {quantity})")
                return Response(json.dumps({'error': 'quantity of order exceeds available amount'}), status=400, mimetype='application/json')
        else:
            app.logger.error(f"Portfolio for client {clientID} not found")
            return Response(json.dumps({'error': 'portfolio not found'}), status=400, mimetype='application/json')
        
    update_payload = {
        "quantity": quantity,
        "price": price,
        "placed_at": datetime.now().isoformat()
    }
    app.logger.info(f"{clientID}: UPDATE ORDER {id}: qty={quantity}, price={price}")
    app.logger.debug(f"Sending updated order from {clientID} to Order Management")
    response=requests.put(f"http://order-mgmt:5000/orders/{id}", json=update_payload)
    app.logger.debug(f"Received response from Order Management for {clientID}'s SELL order.")

    if response.status_code == 200:
        app.logger.info(f"Order {id} of {clientID} updated.")
    elif response.status_cod == 404:
        app.logger.error(f"Order {id} does not exist.")
    else:
        app.logger.error(f"Order {id} of {clientID} could not be updated.")

    return Response(json.dumps(response.json()), status=response.status_code, mimetype='application/json')

@app.route('/orders/<id>', methods=['DELETE'])
def remove_order(id):
    # Verify if the client is authenticated
    res = verify(request)
    app.logger.debug(f"Request token was verified.")
    if res is None:
        app.logger.error("Client provided invalid token for authentication.")
        return Response(status=401)
    
    clientID = res['clientID']
    app.logger.debug(f"Client ID is {clientID}")

    get_response = requests.get(f"http://order-mgmt:5000/orders/{id}")
    app.logger.debug(f"Got response for GET ORDER BY ID (id={id})")

    if get_response.status_code == 404:
        app.logger.error(f"Order with id={id} not found.")
        return Response(json.dumps({'error': 'order not found'}), status=404, mimetype='application/json')
    elif get_response.status_code != 200:
        app.logger.error(f"Order with id={id} could not be fetched succesfully.")
        return Response(status=get_response.status_code)
    
    app.logger.info(f"Order with id={id} found.")
    order_json = get_response.json()
    if order_json['ClientID'] != clientID:
        app.logger.error(f"Order with id={id} was not placed by {clientID}.")
        return Response(status=401)
    
    response = requests.delete(f"http://order-mgmt:5000/orders/{id}")
    app.logger.debug(f"Got response for DELETE ORDER {id} from Order Management Service")

    if response.status_code == 200:
        app.logger.info(f"Order with id={id} deleted succesfully.")
        return Response(json.dumps({'id': id}), status=200, mimetype='application/json')
    
    app.logger.error(f"Order with id={id} could not be deleted.")
    return Response(status=400)

@app.route('/orders/process', methods=['POST'])
def process_order():
    payload = request.get_json(force=True)
    order_secret = None
    with open(order_secret_file) as file:
        order_secret = file.read()
    if order_secret == None:
        app.logger.error("Order Managament Secret not known by Platform.")
        return Response(status=400)
    app.logger.debug("Order secret file was read.")
    # Operation Management service is the only entity allowed to perform this operation
    if payload['secret'] != order_secret:
        app.logger.error("Order Process request not issued by Order Management Service.")
        return Response(status=401)
    
    client_id = payload['client_id']
    from_client_id = payload['from_client_id']
    symbol = payload['symbol']
    quantity = int(payload['quantity'])
    price = float(payload['price'])
    type = payload['type']

    # Request client's portfolio from Portfolio Management Service
    response = requests.get(f"http://portfolio-mgmt:5000/portfolio/{client_id}")
    app.logger.debug(f"Got response for GET PORTFOLIO for {client_id} from Portfolio Management Service")
    
    if response is None:
        app.logger.error(f"Portfolio for {client_id} could not be fetched.")
        return Response(status=400)
    elif response.status_code != 200:
        app.logger.error(f"Portfolio for {client_id} could not be fetched.")
        return Response(status=response.status_code)
    
    app.logger.info(f"Portfolio for {client_id} found.")
    portfolio = response.json()
    # Get portfolio details about cash and symbol, if available
    cash_balance = float(portfolio['Cash'])
    old_quantity = int(portfolio[symbol]) if not portfolio.get(symbol) is None else 0 
    # Buy Order
    if type == 'B':
        paid_amount = price * quantity
        new_cash_balance_client = cash_balance - paid_amount
        new_quantity = old_quantity + quantity 
        client_payload = {
            "Cash": new_cash_balance_client,
            symbol: new_quantity
        }
        # Update portfolio of the other client as well if they are not an external client
        if from_client_id != 'external':
            app.logger.info("Transaction involving internal client")
            from_response = requests.get(f"http://portfolio-mgmt:5000/portfolio/{from_client_id}")
            if from_response is None:
                app.logger.error(f"Portfolio for {from_client_id} could not be fetched.")
                return Response(status=400)
            elif from_response.status_code != 200:
                app.logger.error(f"Portfolio for {from_client_id} could not be fetched.")
                return Response(status=from_response.status_code)
            app.logger.info(f"Portfolio for {client_id} found.")    

            from_portfolio = from_response.json()
            from_cash_balance = float(from_portfolio['Cash'])
            from_quantity = int(from_portfolio[symbol]) if not from_portfolio.get(symbol) is None else 0 
            new_cash_balance_from_client = from_cash_balance + paid_amount
            from_client_payload = {
                "Cash": new_cash_balance_from_client,
                symbol: from_quantity - quantity
            }

            app.logger.info(f"Updating portfolio for {from_client_id} with: cash={new_cash_balance_from_client}, {symbol}={from_quantity - quantity}.")
            from_response = requests.put(f"http://portfolio-mgmt:5000/portfolio/{from_client_id}", json=from_client_payload)
            if from_response.status_code != 200:
                app.logger.error(f"Portfolio for {from_client_id} could not be updated.")
                return Response(status=from_response.status_code)
            app.logger.info(f"Portfolio for {from_client_id} updated.")
        else:
            app.logger.info("Transaction involving external client")
        app.logger.info(f"Updating portfolio for {client_id} with: cash={new_cash_balance_client}, {symbol}={new_quantity}.")
        response = requests.put(f"http://portfolio-mgmt:5000/portfolio/{client_id}", json=client_payload)
        if response.status_code != 200:
            app.logger.error(f"Portfolio for {client_id} could not be updated.")
            return Response(status=response.status_code)
        app.logger.info(f"Portfolio for {client_id} updated.")
    # Sell Order
    else:
        paid_amount = price * quantity
        new_cash_balance_client = cash_balance + paid_amount
        new_quantity = old_quantity - quantity
        client_payload = {
            "Cash": new_cash_balance_client,
            symbol: new_quantity
        }
        if from_client_id != 'external':
            app.logger.info("Transaction involving internal client")
            from_response = requests.get(f"http://portfolio-mgmt:5000/portfolio/{from_client_id}")
            if from_response is None:
                app.logger.error(f"Portfolio for {from_client_id} could not be fetched.")
                return Response(status=400)
            elif from_response.status_code != 200:
                app.logger.error(f"Portfolio for {from_client_id} could not be fetched.")
                return Response(status=from_response.status_code)
            
            from_portfolio = from_response.json()
            from_cash_balance = float(from_portfolio['Cash'])
            from_quantity = int(from_portfolio[symbol]) if not from_portfolio.get(symbol) is None else 0 
            new_cash_balance_from_client = from_cash_balance - paid_amount
            from_client_payload = {
                "Cash": new_cash_balance_from_client,
                symbol: from_quantity + quantity
            }
            app.logger.info(f"Updating portfolio for {from_client_id} with: cash={new_cash_balance_from_client}, {symbol}={from_quantity + quantity}.")
            from_response = requests.put(f"http://portfolio-mgmt:5000/portfolio/{from_client_id}", json=from_client_payload)
            if from_response.status_code != 200:
                app.logger.error(f"Portfolio for {from_client_id} could not be updated.")
                return Response(status=from_response.status_code)
            app.logger.info(f"Portfolio for {from_client_id} updated.")
        else:
            app.logger.info("Transaction involving external client")
        app.logger.info(f"Updating portfolio for {client_id} with: cash={new_cash_balance_client}, {symbol}={new_quantity}.")
        response = requests.put(f"http://portfolio-mgmt:5000/portfolio/{client_id}", json=client_payload)
        if response.status_code != 200:
            app.logger.error(f"Portfolio for {client_id} could not be updated.")
            return Response(status=response.status_code)
        app.logger.info(f"Portfolio for {client_id} updated.")

    return Response(status=200)

@app.route('/portfolio', methods=['GET'])
def get_portfolio():
    # Verify if the client is authenticated
    res = verify(request)
    app.logger.debug(f"Request token was verified.")
    if res is None:
        app.logger.error("Client provided invalid token for authentication.")
        return Response(status=401)
    
    clientID = res['clientID']
    app.logger.debug(f"Client ID is {clientID}")

    # Request client's portfolio from Portfolio Management Service
    response = requests.get(f"http://portfolio-mgmt:5000/portfolio/{clientID}")
    app.logger.debug(f"Got response for GET PORTFOLIO for {clientID} from Portfolio Management Service")

    if not response is None and response.status_code == 200:
        app.logger.info(f"Portfolio for {clientID} found.")
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

        
        app.logger.debug(f"Calculated total value for {clientID}'s portfolio")
        portfolio['Value'] = value
        return Response(json.dumps(portfolio), status=response.status_code, mimetype="application/json")
    app.logger.error(f"Portfolio for {clientID} could not be fetched.")
    return Response(status=400)

@app.route('/deposit', methods=['POST'])
def deposit():
    # Verify if the client is authenticated
    res = verify(request)
    app.logger.debug(f"Request token was verified.")
    if res is None:
        app.logger.error("Client provided invalid token for authentication.")
        return Response(status=401)
    
    clientID = res['clientID']
    app.logger.debug(f"Client ID is {clientID}")

    # Request client's portfolio from Portfolio Management Service
    response = requests.get(f"http://portfolio-mgmt:5000/portfolio/{clientID}")
    app.logger.debug(f"Got response for GET PORTFOLIO for {clientID} from Portfolio Management Service")
    if not response is None and response.status_code == 200:
        app.logger.info(f"Portfolio for {clientID} found.")
        data = response.json()
        old_cash_balance = float(data['Cash'])

        # Get request body
        payload = request.get_json(force=True)

        deposited_cash = float(payload.get('amount'))
        new_cash_balance = old_cash_balance + deposited_cash

        update_payload = {"Cash": str(new_cash_balance)}
        app.logger.info(f"Updating {clientID} portfolio with cash={new_cash_balance}")
        response = requests.put(f"http://portfolio-mgmt:5000/portfolio/{clientID}", json=update_payload)

        if response and response.status_code == 200:
            app.logger.info(f"Portfolio for {clientID} updated.")
        else:
            app.logger.error(f"Portfolio for {clientID} was not updated.")
        return Response(response.text, status=response.status_code, mimetype="json/application")
    app.logger.error(f"Portfolio for {clientID} could not be fetched.")    
    return Response(status=400)

@app.route('/withdraw', methods=['POST'])
def withdraw():
    # Verify if the client is authenticated
    res = verify(request)
    app.logger.debug(f"Request token was verified.")
    if res is None:
        app.logger.error("Client provided invalid token for authentication.")
        return Response(status=401)
    
    clientID = res['clientID']
    app.logger.debug(f"Client ID is {clientID}")

    # Request client's portfolio from Portfolio Management Service
    response = requests.get(f"http://portfolio-mgmt:5000/portfolio/{clientID}")
    app.logger.debug(f"Got response for GET PORTFOLIO for {clientID} from Portfolio Management Service")
    if not response is None and response.status_code == 200:
        app.logger.info(f"Portfolio for {clientID} found.")
        data = response.json()
        cash_balance = float(data['Cash'])

        # Get request body
        payload = request.get_json(force=True)

        withdrawn_cash = float(payload.get('amount'))
        new_cash_balance = cash_balance - withdrawn_cash

        if new_cash_balance < 0.0:
            app.logger.error(f"Insufficient funds ({cash_balance}) to withdraw {withdrawn_cash} for client {clientID}")
            return Response(json.dumps({'error': 'insufficient funds'}), status=400, mimetype='application/json')

        update_payload = {"Cash": str(new_cash_balance)}
        app.logger.info(f"Updating {clientID} portfolio with cash={new_cash_balance}")
        response = requests.put(f"http://portfolio-mgmt:5000/portfolio/{clientID}", json=update_payload)

        if response and response.status_code == 200:
            app.logger.info(f"Portfolio for {clientID} updated.")
        else:
            app.logger.error(f"Portfolio for {clientID} was not updated.")
        return Response(response.text, status=response.status_code, mimetype="json/application")
    app.logger.error(f"Portfolio for {clientID} could not be fetched.")        
    return Response(status=400)

if __name__ == "__main__":
    app.run(debug=False)