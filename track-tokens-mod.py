import requests
import json
import sqlite3
import argparse
import configparser
import subprocess
import sys
import parsing
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy import create_engine, func, desc
from models import Extra, TransactionHistory, TransactionTable, TransferLogs, Webtable, Base


def startWorking(transaction_data, parsed_data):
    engine = create_engine('sqlite:///databases/{}.db'.format(parsed_data['marker'][:-1]), echo=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Play area
    if parsed_data['type'] == 'transfer':
        if parsed_data['amount'] is None:
            print("Value for token transfer has not been specified")
            return
    elif parsed_data['type'] == 'incorporation':
        if parsed_data['initTokens'] is None:
            print("Value for token transfer has not been specified")
            return

    inputlist = []
    querylist = []

    for obj in transaction_data["vin"]:
        querylist.append([obj["txid"], obj["vout"]])

    inputval = 0
    inputadd = ''

    for query in querylist:
        string = "{} getrawtransaction {} 1".format(localapi, str(query[0]))
        response = subprocess.check_output(string, shell=True)
        content = json.loads(response.decode("utf-8"))

        for objec in content["vout"]:
            if objec["n"] == query[1]:
                inputadd = objec["scriptPubKey"]["addresses"][0]
                inputval = inputval + objec["value"]

        inputlist = [[inputadd, inputval]]

        if len(inputlist) > 1:
            print("Program has detected more than one input address ")
            print("This transaction will be discarded")
            break

        outputlist = []
        for obj in transaction_data["vout"]:
            if obj["scriptPubKey"]["type"] == "pubkeyhash":
                if inputlist[0][0] == obj["scriptPubKey"]["addresses"][0]:
                    continue
                temp = []
                temp.append(obj["scriptPubKey"]["addresses"][0])
                temp.append(obj["value"])

                outputlist.append(temp)

        print("\n\nInput List")
        print(inputlist)
        print("\nOutput List")
        print(outputlist)

        if len(inputlist) > 1:
            print("Program has detected more than one input address ")
            print("This transaction will be discarded")
            continue

        # Check if the transaction is of the type 'incorporation'
        if parsed_data['type'] == 'incorporation':

            session.add(TransactionTable(address=outputlist[0][0], parentid=0, transferBalance=parsed_data['initTokens']))
            session.commit()
            #transferDescription = "Root address = " + str(root_address) + " has been initialized with " + str(root_init_value) + " tokens"
            #blockchainReference = '{}tx/'.format(neturl)
            #session.add(TransferLogs(primaryIDReference=1, transferDescription=transferDescription, transferIDConsumed=0, blockchainReference=blockchainReference))
            #session.add(TransactionHistory(blockno=root_block_index, fromAddress='', toAddress=root_address, amount=root_init_value, blockchainReference=blockchainReference))
            #session.commit()
            return

        availableTokens = session.query(func.sum(TransactionTable.transferBalance)).filter_by(address=inputlist[0][0]).all()[0][0]
        commentTransferAmount = parsed_data['amount']

        if availableTokens is None:
            print("The input address dosen't exist in our database ")

        elif availableTokens < commentTransferAmount:
            print(
                "\nThe transfer amount passed in the comments is more than the user owns\nThis transaction will be discarded\n")
            continue

        elif availableTokens >= commentTransferAmount:
            '''if len(commentTransferAmount) != len(outputlist):
                print("The parameters in the comments aren't enough")
                print("This transaction will be discarded")
                continue'''

            # if output[0] == inputlist[0][0]:
            # 	continue

            #c.execute("SELECT * FROM transactiontable WHERE address=?", (inputlist[0][0],))
            #table = c.fetchall()
            table = session.query(TransactionTable).filter_by(address=inputlist[0][0]).all()

            pidlst = []
            checksum = 0
            for row in table:
                if checksum >= commentTransferAmount:
                    break
                pidlst.append(row.id)
                checksum = checksum + row.transferBalance

            balance = commentTransferAmount
            #c.execute("SELECT sum(transferBalance) FROM transactiontable WHERE address=?", (outputlist[i][0],))
            #opbalance = c.fetchall()[0][0]
            opbalance = session.query(func.sum(TransactionTable.transferBalance)).filter_by(address=outputlist[0][0]).all()[0][0]

            if opbalance is None:
                opbalance = 0

            #c.execute("SELECT sum(transferBalance) FROM transactiontable WHERE address=?", (inputlist[0][0],))
            #ipbalance = c.fetchall()[0][0]
            ipbalance = session.query(func.sum(TransactionTable.transferBalance)).filter_by(address=inputlist[0][0]).all()[0][0]

            for pid in pidlst:
                #c.execute("SELECT transferBalance FROM transactiontable WHERE id=?", (pid,))
                #temp = c.fetchall()
                #temp = temp[0][0]
                temp = session.query(TransactionTable.transferBalance).filter_by(id=pid).all()[0][0]

                if balance <= temp:
                    #c.execute("INSERT INTO transactiontable (address, parentid, transferBalance) VALUES (?,?,?)",
                    #          (outputlist[i][0], pid, balance))
                    #c.execute("UPDATE transactiontable SET transferBalance=? WHERE id=?", (temp - balance, pid))

                    session.add(TransactionTable(address=outputlist[0][0], parentid=pid, transferBalance=balance))
                    entry = session.query(TransactionTable).filter(TransactionTable.id == pid).all()
                    entry[0].transferBalance = temp - balance
                    session.commit()

                    ## transaction logs section ##
                    result = session.query(TransactionTable.id).order_by(desc(TransactionTable.id)).all()
                    lastid = result[-1].id
                    transferDescription = str(balance) + " tokens transferred to " + str(
                        outputlist[0][0]) + " from " + str(inputlist[0][0])
                    blockchainReference = '{}tx/{}'.format(neturl, str(transaction))
                    session.add(TransferLogs(primaryIDReference=lastid, transferDescription=transferDescription,
                                             transferIDConsumed=pid, blockchainReference=blockchainReference))
                    transferDescription = str(inputlist[0][0]) + " balance UPDATED from " + str(
                        temp) + " to " + str(temp - balance)
                    blockchainReference = '{}tx/{}'.format(neturl, str(transaction))
                    session.add(TransferLogs(primaryIDReference=pid, transferDescription=transferDescription,
                                             blockchainReference=blockchainReference))

                    ## transaction history table ##
                    session.add(TransactionHistory(blockno=blockindex, fromAddress=inputlist[0][0],
                                                   toAddress=outputlist[0][0], amount=str(balance),
                                                   blockchainReference=blockchainReference))

                    ##webpage table section ##
                    transferDescription = str(commentTransferAmount) + " tokens transferred from " + str(
                        inputlist[0][0]) + " to " + str(outputlist[0][0])
                    session.add(
                        Webtable(transferDescription=transferDescription, blockchainReference=blockchainReference))

                    transferDescription = "UPDATE " + str(outputlist[0][0]) + " balance from " + str(
                        opbalance) + " to " + str(opbalance + commentTransferAmount)
                    session.add(
                        Webtable(transferDescription=transferDescription, blockchainReference=blockchainReference))

                    transferDescription = "UPDATE " + str(inputlist[0][0]) + " balance from " + str(
                        ipbalance) + " to " + str(ipbalance - commentTransferAmount)
                    session.add(
                        Webtable(transferDescription=transferDescription, blockchainReference=blockchainReference))

                    balance = 0
                    session.commit()

                elif balance > temp:
                    session.add(TransactionTable(address=outputlist[0][0], parentid=pid, transferBalance=temp))
                    entry = session.query(TransactionTable).filter(TransactionTable.id == pid).all()
                    entry[0].transferBalance = 0
                    session.commit()

                    ##transaction logs section ##
                    session.query(TransactionTable.id).order_by(desc(TransactionTable.id))
                    result = session.query(TransactionTable.id).order_by(desc(TransactionTable.id)).all()
                    lastid = result[-1].id
                    transferDescription = str(temp) + " tokens transferred to " + str(
                        outputlist[0][0]) + " from " + str(inputlist[0][0])
                    blockchainReference = '{}tx/{}'.format(neturl, str(transaction))
                    session.add(TransactionTable(primaryIDReference=lastid, transferDescription=transferDescription,
                                                 transferIDConsumed=pid, blockchainReference=blockchainReference))

                    transferDescription = str() + " balance UPDATED from " + str(temp) + " to " + str(0)
                    blockchainReference = '{}tx/{}'.format(neturl, str(transaction))
                    session.add(TransactionTable(primaryIDReference=pid, transferDescription=transferDescription,
                                                 blockchainReference=blockchainReference))

                    ## transaction history table ##
                    session.add(TransactionHistory(blockno=blockindex, fromAddress=inputlist[0][0],
                                                   toAddress=outputlist[0][0], amount=str(balance),
                                                   blockchainReference=blockchainReference))
                    balance = balance - temp
                    session.commit()

    # Finishing statements
    session.commit()
    session.close()

# Read configuration
config = configparser.ConfigParser()
config.read('config.ini')

# Read command line arguments
parser = argparse.ArgumentParser(description='Script tracks RMT using FLO data on the FLO blockchain - https://flo.cash')
parser.add_argument('-r', '--reset', nargs='?', const=1, type=int, help='Purge existing db and rebuild it')
args = parser.parse_args()

# Assignment the flo-cli command
if config['DEFAULT']['NET'] == 'mainnet':
    neturl = 'https://florincoin.info/'
    localapi = config['DEFAULT']['FLO_CLI_PATH']
elif config['DEFAULT']['NET'] == 'testnet':
    neturl = 'https://testnet.florincoin.info/'
    localapi = '{} --testnet'.format(config['DEFAULT']['FLO_CLI_PATH'])
else:
    print("NET parameter is wrong\nThe script will exit now ")


# Delete database directory if reset is set to 1
if args.reset == 1:
    import os
    import shutil
    apppath = os.path.dirname(os.path.realpath(__file__))
    dirpath = os.path.join(apppath, 'databases')
    shutil.rmtree(dirpath)
    os.mkdir(dirpath)


# Read start block no
startblock = int(config['DEFAULT']['START_BLOCK'])

# Find current block height
string = "{} getblockcount".format(localapi)
response = subprocess.check_output(string, shell=True)
current_index = json.loads(response.decode("utf-8"))
print("current_block_height : " + str(current_index))

for blockindex in range( startblock, current_index ):
    print(blockindex)

    # Scan every block
    string = "{} getblockhash {}".format(localapi, str(blockindex))
    response = subprocess.check_output(string, shell=True)
    blockhash = response.decode("utf-8")

    string = "{} getblock {}".format(localapi, str(blockhash))
    response = subprocess.check_output(string, shell=True)
    blockinfo = json.loads(response.decode("utf-8"))

    # Scan every transaction
    for transaction in blockinfo["tx"]:
        string = "{} getrawtransaction {} 1".format(localapi, str(transaction))
        response = subprocess.check_output(string, shell=True)
        transaction_data = json.loads(response.decode("utf-8"))
        text = transaction_data["floData"]
        text = text[5:]

        parsed_data = parsing.parse_flodata(text)
        if parsed_data['type'] != 'noise':
            print(blockindex)
            print(parsed_data['type'])
            startWorking(transaction_data, parsed_data)

