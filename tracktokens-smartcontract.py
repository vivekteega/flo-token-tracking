import requests
import json
import sqlite3
import argparse
import configparser
import subprocess
import sys
import parsing
import os
import shutil
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy import create_engine, func, desc
from models import Extra, TransactionHistory, TransactionTable, TransferLogs, Webtable, Base, ContractStructure, ContractBase


def startWorking(transaction_data, parsed_data):

    # Do the necessary checks for the inputs and outputs

    # Create inputlist and outputlist
    inputlist = []
    querylist = []

    for obj in transaction_data["vin"]:
        querylist.append([obj["txid"], obj["vout"]])

    if len(querylist) > 1:
        print("Program has detected more than one input address ")
        print("This transaction will be discarded")
        return

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

    if len(transaction_data["vout"]) > 2:
        print("Program has detected more than one output address ")
        print("This transaction will be discarded")
        return

    outputlist = []
    for obj in transaction_data["vout"]:
        if obj["scriptPubKey"]["type"] == "pubkeyhash":
            if inputlist[0][0] == obj["scriptPubKey"]["addresses"][0]:
                continue

            outputlist.append([obj["scriptPubKey"]["addresses"][0], obj["value"]])

    print("\n\nInput List")
    print(inputlist)
    print("\nOutput List")
    print(outputlist)


    # Do operations as per the type of transaction
    if parsed_data['type'] == 'transfer':
        print('Found a transaction of the type transfer')

        if parsed_data['transferType'] == 'smartContract':
            print('do something')

        elif parsed_data['transferType'] == 'token':
            engine = create_engine('sqlite:///tokens/{}.db'.format(parsed_data['tokenIdentification']), echo=True)
            Base.metadata.create_all(bind=engine)
            session = sessionmaker(bind=engine)()
            availableTokens = session.query(func.sum(TransactionTable.transferBalance)).filter_by(address=inputlist[0][0]).all()[0][0]
            commentTransferAmount = parsed_data['amount']
            if availableTokens is None:
                print("The input address dosen't exist in our database ")

            elif availableTokens < commentTransferAmount:
                print(
                    "\nThe transfer amount passed in the comments is more than the user owns\nThis transaction will be discarded\n")
                return

            elif availableTokens >= commentTransferAmount:
                print("well i've reached here")

    elif parsed_data['type'] == 'tokenIncorporation':
        if not os.path.isfile('./tokens/{}.db'.format(parsed_data['tokenIdentification'])):
            engine = create_engine('sqlite:///tokens/{}.db'.format(parsed_data['tokenIdentification']), echo=True)
            Base.metadata.create_all(bind=engine)
            session = sessionmaker(bind=engine)()
            session.add(TransactionTable(address=outputlist[0][0], parentid=0, transferBalance=parsed_data['tokenAmount']))
            session.commit()
            session.close()
        else:
            print('Transaction rejected as the token with same name has already been incorporated')

    elif parsed_data['type'] == 'smartContractIncorporation':
        if not os.path.isfile('./smartContracts/{}.db'.format(parsed_data['contractName'])):
            if parsed_data['contractType'] == 'betting':
                print("Smart contract is of the type betting")
                if parsed_data['contractName'] is not None and parsed_data['contractAddress'] == outputlist[0][0]:
                    print("Hey I have passed the first test for smart contract")
                    engine = create_engine('sqlite:///smartContracts/{}.db'.format(parsed_data['contractName']), echo=True)
                    ContractBase.metadata.create_all(bind=engine)
                    session = sessionmaker(bind=engine)()
                    session.add(ContractStructure(attribute='contractType', index=0, value=parsed_data['contractType']))
                    session.add(ContractStructure(attribute='contractName', index=0, value=parsed_data['contractName']))
                    session.add(
                        ContractStructure(attribute='tokenIdentification', index=0, value=parsed_data['tokenIdentification']))
                    session.add(
                        ContractStructure(attribute='contractAddress', index=0, value=parsed_data['contractAddress'][:-1]))
                    session.add(
                        ContractStructure(attribute='flodata', index=0,
                                          value=parsed_data['flodata']))
                    session.add(
                        ContractStructure(attribute='userassetcommitment', index=0,
                                          value=parsed_data['contractConditions']['userassetcommitment'].split(parsed_data['tokenIdentification'][:-1])[0]))
                    for key, value in parsed_data['contractConditions']['smartcontractpays'].items():
                        session.add(ContractStructure(attribute='exitconditions', index=key, value=value))
                    session.commit()
                    session.close()
        else:
            print('Transaction rejected as a smartcontract with same name has already been incorporated')
    elif parsed_data['type'] == 'smartContractPays':
        print('Found a transaction of the type smartContractPays')




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


# Delete database and smartcontract directory if reset is set to 1
if args.reset == 1:
    apppath = os.path.dirname(os.path.realpath(__file__))
    dirpath = os.path.join(apppath, 'tokens')
    shutil.rmtree(dirpath)
    os.mkdir(dirpath)
    dirpath = os.path.join(apppath, 'smartContracts')
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

        parsed_data = parsing.parse_flodata(text)
        if parsed_data['type'] != 'noise':
            print(blockindex)
            print(parsed_data['type'])
            startWorking(transaction_data, parsed_data)