from block import Block
from blockchain import BlockChain
from flask import Flask, render_template, redirect, request
import requests
import json
import time
import datetime
import os
import psycopg2

#BASE_URL = 'http://127.0.0.1:5000'
#DATABASE_URL = 'postgres://hutzvtefjxlkbg:e8a5444ac9953c604df8272b40c9451bb6e34cea42a7cb86d37aa237adb443b4@ec2-54-225-96-191.compute-1.amazonaws.com:5432/d30o5uum8id8hv'

BASE_URL = 'https://app-blockchain.herokuapp.com'
DATABASE_URL = os.environ['DATABASE_URL']

app = Flask(__name__)

blockchain = BlockChain()
posts = []


def timestamp_to_string(epoch_time):
    return datetime.datetime.fromtimestamp(epoch_time).strftime('%H:%M')


def save_db():
    # update db
    chain_data = []
    for block in blockchain.chain:
        chain_data.append(block.__dict__)
    chain = json.dumps({"length": len(chain_data),
                       "chain": chain_data})

    pending_tx = json.dumps(blockchain.unconfirmed_transactions)

    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    cur.execute("SELECT * FROM blockchain;")
    data = cur.fetchone()
    if data is not None:
        cur.execute("UPDATE blockchain SET CHAIN = '{0}', PENDING_TX = '{1}';".format(chain, pending_tx))
    else:
        cur.execute("INSERT INTO blockchain VALUES ('{0}', '{1}');".format(chain, pending_tx))
    conn.commit()
    cur.close()
    conn.close()


def load_db():
    global blockchain
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    cur.execute("SELECT * FROM blockchain;")
    data = cur.fetchone()
    if data is not None:
        chain = []
        obj = json.loads(data[0])
        # convert JSON array to an Array of Objects
        for block in obj['chain']:
            print(block)
            blk = Block(block['index'],
                        block['transactions'],
                        block['timestamp'],
                        block['previous_hash'])
            blk.hash = block['hash']
            chain.append(blk)
        blockchain.chain = chain
        blockchain.unconfirmed_transactions = json.loads(data[1])
    else:
        blockchain = BlockChain()
    conn.commit()
    cur.close()
    conn.close()


def clear_db():
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    cur.execute("delete FROM blockchain;")
    conn.commit()
    cur.close()
    conn.close()


@app.route('/')
def index():
    print("--- START load data from DB ---")
    load_db()
    print("--- END load data from DB ---")

    content = []

    for block in blockchain.chain:
        for tx in block.transactions:
            tx["index"] = block.index
            tx["hash"] = block.previous_hash
            content.append(tx)

    global posts
    posts = sorted(content, key=lambda k: k['timestamp'],
                       reverse=True)

    return render_template('index.html',
                           title='BlockChain - '
                                 'Distributed content sharing',
                           posts=posts,
                           pending_tx=len(blockchain.unconfirmed_transactions),
                           readable_time=timestamp_to_string)


@app.route('/submit', methods=['POST'])
def submit_textarea():
    """
    Endpoint to create a new transaction via our application.
    """
    print("--- submit ---")
    post_content = request.form["content"]
    author = request.form["author"]

    post_object = {
        'author': author,
        'content': post_content,
    }

    # Submit a transaction
    new_tx_address = "{}/new_transaction".format(BASE_URL)

    requests.post(new_tx_address,
                  json=post_object,
                  headers={'Content-type': 'application/json'})

    return redirect('/')


@app.route('/chain', methods=['GET'])
def get_chain():
    chain_data = []
    for block in blockchain.chain:
        chain_data.append(block.__dict__)
    return json.dumps({"length": len(chain_data),
                       "chain": chain_data}), 200


@app.route('/new_transaction', methods=['POST'])
def new_transaction():
    print("--- new transaction ---")
    print("--- START load data from DB ---")
    load_db()
    print("--- END load data from DB ---")
    tx_data = request.get_json()
    required_fields = ["author", "content"]

    for field in required_fields:
        if not tx_data.get(field):
            return "Invalid transaction data", 404

    tx_data["timestamp"] = time.time()

    blockchain.add_new_transaction(tx_data)

    print("--- START save data in DB ---")
    save_db()
    print("--- END save data in DB ---")

    return "Success", 201


@app.route('/mine', methods=['GET'])
def mine_unconfirmed_transactions():
    print("--- START load data from DB ---")
    load_db()
    print("--- END load data from DB ---")
    result = blockchain.mine()
    print("Block #{} is mined.".format(result))

    print("--- START save data in DB ---")
    save_db()
    print("--- END save data in DB ---")

    return redirect('/')


@app.route('/reset', methods=['GET'])
def reset_chain():
    print("--- START clear DB ---")
    clear_db()
    print("--- END clear DB ---")
    return redirect('/')


# endpoint to query unconfirmed transactions
@app.route('/pending_tx')
def get_pending_tx():
    return json.dumps(blockchain.unconfirmed_transactions)


# endpoint to add a block mined by someone else to
# the node's chain. The block is first verified by the node
# and then added to the chain.
@app.route('/add_block', methods=['POST'])
def validate_and_add_block():
    block_data = request.get_json()
    block = Block(block_data["index"],
                  block_data["transactions"],
                  block_data["timestamp",
                  block_data["previous_hash"]])

    proof = block_data['hash']
    added = blockchain.add_block(block, proof)

    if not added:
        return "The block was discarded by the node", 400

    return "Block added to the chain", 201


if __name__ == '__main__':
    app.run(debug=True)