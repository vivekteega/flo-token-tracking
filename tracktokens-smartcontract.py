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
from models import Extra, TransactionHistory, TransactionTable, TransferLogs, Webtable, Base, ContractStructure, ContractBase, ContractParticipants, SystemBase, ActiveContracts


committeeAddressList = ['oUc4dVvxwK7w5MHUHtev8UawN3eDjiZnNx']

def transferToken(tokenIdentification, tokenAmount, inputAddress, outputAddress):
    engine = create_engine('sqlite:///tokens/{}.db'.format(tokenIdentification), echo=True)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    availableTokens = session.query(func.sum(TransactionTable.transferBalance)).filter_by(address=inputAddress).all()[0][0]
    commentTransferAmount = tokenAmount
    if availableTokens is None:
        print("The input address dosen't exist in our database ")
        session.close()
        return None

    elif availableTokens < commentTransferAmount:
        print(
            "\nThe transfer amount passed in the comments is more than the user owns\nThis transaction will be discarded\n")
        session.close()
        return None

    elif availableTokens >= commentTransferAmount:
        table = session.query(TransactionTable).filter(TransactionTable.address==inputAddress, TransactionTable.transferBalance>0).all()
        pidlst = []
        checksum = 0
        for row in table:
            if checksum >= commentTransferAmount:
                break
            pidlst.append(row.id)
            checksum = checksum + row.transferBalance

        balance = commentTransferAmount
        opbalance = session.query(func.sum(TransactionTable.transferBalance)).filter_by(address=outputAddress).all()[0][0]

        if opbalance is None:
            opbalance = 0

        ipbalance = availableTokens

        for pid in pidlst:
            temp = session.query(TransactionTable.transferBalance).filter_by(id=pid).all()[0][0]

            if balance <= temp:

                session.add(TransactionTable(address=outputAddress, parentid=pid, transferBalance=balance))
                entry = session.query(TransactionTable).filter(TransactionTable.id == pid).all()
                entry[0].transferBalance = temp - balance
                session.commit()

                ## transaction logs section ##
                result = session.query(TransactionTable.id).order_by(desc(TransactionTable.id)).all()
                lastid = result[-1].id
                transferDescription = str(balance) + " tokens transferred to " + str(
                    outputAddress) + " from " + str(inputAddress)
                blockchainReference = '{}tx/{}'.format(neturl, str(transaction))
                session.add(TransferLogs(primaryIDReference=lastid, transferDescription=transferDescription,
                                         transferIDConsumed=pid, blockchainReference=blockchainReference))
                transferDescription = str(inputAddress) + " balance UPDATED from " + str(
                    temp) + " to " + str(temp - balance)
                blockchainReference = '{}tx/{}'.format(neturl, str(transaction))
                session.add(TransferLogs(primaryIDReference=pid, transferDescription=transferDescription,
                                         blockchainReference=blockchainReference))

                ## transaction history table ##
                session.add(TransactionHistory(blockno=blockindex, fromAddress=inputAddress,
                                               toAddress=outputAddress, amount=str(balance),
                                               blockchainReference=blockchainReference))

                ##webpage table section ##
                transferDescription = str(commentTransferAmount) + " tokens transferred from " + str(
                    inputAddress) + " to " + str(outputAddress)
                session.add(
                    Webtable(transferDescription=transferDescription, blockchainReference=blockchainReference))

                transferDescription = "UPDATE " + str(outputAddress) + " balance from " + str(
                    opbalance) + " to " + str(opbalance + commentTransferAmount)
                session.add(
                    Webtable(transferDescription=transferDescription, blockchainReference=blockchainReference))

                transferDescription = "UPDATE " + str(inputAddress) + " balance from " + str(
                    ipbalance) + " to " + str(ipbalance - commentTransferAmount)
                session.add(
                    Webtable(transferDescription=transferDescription, blockchainReference=blockchainReference))

                balance = 0
                session.commit()

            elif balance > temp:
                session.add(TransactionTable(address=outputAddress, parentid=pid, transferBalance=temp))
                entry = session.query(TransactionTable).filter(TransactionTable.id == pid).all()
                entry[0].transferBalance = 0
                session.commit()

                ##transaction logs section ##
                result = session.query(TransactionTable.id).order_by(desc(TransactionTable.id)).all()
                lastid = result[-1].id
                transferDescription = str(temp) + " tokens transferred to " + str(outputAddress) + " from " + str(inputAddress)
                blockchainReference = '{}tx/{}'.format(neturl, str(transaction))
                session.add(TransferLogs(primaryIDReference=lastid, transferDescription=transferDescription,
                                             transferIDConsumed=pid, blockchainReference=blockchainReference))

                transferDescription = str() + " balance UPDATED from " + str(temp) + " to " + str(0)
                blockchainReference = '{}tx/{}'.format(neturl, str(transaction))
                session.add(TransferLogs(primaryIDReference=pid, transferDescription=transferDescription,
                                             blockchainReference=blockchainReference))

                ## transaction history table ##
                session.add(TransactionHistory(blockno=blockindex, fromAddress=inputAddress,
                                               toAddress=outputAddress, amount=str(balance),
                                               blockchainReference=blockchainReference))
                balance = balance - temp
                session.commit()
        session.close()
        return 1


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

        if parsed_data['transferType'] == 'token':

            returnval = transferToken(parsed_data['tokenIdentification'], parsed_data['tokenAmount'], inputlist[0][0], outputlist[0][0])
            if returnval is None:
                print("Something went wrong in the token transfer method")

        elif parsed_data['transferType'] == 'smartContract':

            # Check if the tokenAmount being transferred exists in the address & do the token transfer
            returnval = transferToken(parsed_data['tokenIdentification'], parsed_data['tokenAmount'], inputlist[0][0], outputlist[0][0])
            if returnval is not None:
                # Store participant details in the smart contract's db
                engine = create_engine('sqlite:///smartContracts/{}.db'.format(parsed_data['contractName']), echo=True)
                Base.metadata.create_all(bind=engine)
                session = sessionmaker(bind=engine)()
                session.add(ContractParticipants(participantAddress=inputadd, tokenAmount=parsed_data['tokenAmount'],
                                                 contractCondition=parsed_data['contractCondition']))
                session.commit()
                session.close()


            else:
                print("Something went wrong in the smartcontract token transfer method")


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
                        ContractStructure(attribute='contractAddress', index=0, value=parsed_data['contractAddress']))
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

                    # Store smart contract address in system's db, to be ignored during future transfers
                    engine = create_engine('sqlite:///system.db',
                                           echo=True)
                    SystemBase.metadata.create_all(bind=engine)
                    session = sessionmaker(bind=engine)()
                    session.add(
                        ActiveContracts(contractName=parsed_data['contractName'], contractAddress=parsed_data['contractAddress']))
                    session.commit()
                    session.close()
        else:
            print('Transaction rejected as a smartcontract with same name has already been incorporated')
    elif parsed_data['type'] == 'smartContractPays':
        print('Found a transaction of the type smartContractPays')

        # Check if input address is a committee address
        if inputlist[0][0] in committeeAddressList:

            # Check if the output address is an active Smart contract address
            engine = create_engine('sqlite:///system.db', echo=True)
            connection = engine.connect()
            activeContracts = connection.execute('select * from activecontracts').fetchall()
            connection.close()

            # Change columns into rows - https://stackoverflow.com/questions/44360162/how-to-access-a-column-in-a-list-of-lists-in-python
            activeContracts = list(zip(*activeContracts))
            if outputlist[0][0] in activeContracts[2] and parsed_data['contractName'] in activeContracts[1]:

                engine = create_engine('sqlite:///smartContracts/{}.db'.format(parsed_data['contractName']), echo=True)
                connection = engine.connect()
                contractWinners = connection.execute('select * from contractparticipants where contractCondition="{}"'.format(parsed_data['triggerCondition'])).fetchall()
                tokenSum = connection.execute('select sum(tokenAmount) from contractparticipants').fetchall()[0][0]
                tokenIdentification = connection.execute('select value from contractstructure where attribute="tokenIdentification"').fetchall()[0][0]
                connection.close()

                contractWinners = list(zip(*contractWinners))
                for address in contractWinners[1]:
                    transferToken(tokenIdentification, tokenSum/len(contractWinners[1]), outputlist[0][0], address)

            else:
                print('This trigger doesn\'t apply to an active contract. It will be discarded')

        else:
            print('Input address is not part of the committee address list. This trigger is rejected')



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

apppath = os.path.dirname(os.path.realpath(__file__))
dirpath = os.path.join(apppath, 'tokens')
if not os.path.isdir(dirpath):
    os.mkdir(dirpath)
dirpath = os.path.join(apppath, 'smartContracts')
if not os.path.isdir(dirpath):
    os.mkdir(dirpath)

# Delete database and smartcontract directory if reset is set to 1
if args.reset == 1:
    apppath = os.path.dirname(os.path.realpath(__file__))
    dirpath = os.path.join(apppath, 'tokens')
    shutil.rmtree(dirpath)
    os.mkdir(dirpath)
    dirpath = os.path.join(apppath, 'smartContracts')
    shutil.rmtree(dirpath)
    os.mkdir(dirpath)
    dirpath = os.path.join(apppath, 'system.db')
    if os.path.exists(dirpath):
        os.remove(dirpath)


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

        if blockindex == 498385:
            print('debug point')

        parsed_data = parsing.parse_flodata(text)
        if parsed_data['type'] != 'noise':
            print(blockindex)
            print(parsed_data['type'])
            startWorking(transaction_data, parsed_data)