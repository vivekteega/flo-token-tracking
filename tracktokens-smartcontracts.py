import requests
import json
import sqlite3
import argparse
import configparser
import subprocess
import sys
import parsing
import time
import os
import shutil
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy import create_engine, func, desc
from models import SystemData, ActiveTable, ConsumedTable, TransferLogs, TransactionHistory, Base, ContractStructure, ContractBase, ContractParticipants, SystemBase, ActiveContracts


committeeAddressList = ['oUc4dVvxwK7w5MHUHtev8UawN3eDjiZnNx']

def transferToken(tokenIdentification, tokenAmount, inputAddress, outputAddress):
    engine = create_engine('sqlite:///tokens/{}.db'.format(tokenIdentification), echo=True)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    availableTokens = session.query(func.sum(ActiveTable.transferBalance)).filter_by(address=inputAddress).all()[0][0]
    commentTransferAmount = tokenAmount
    if availableTokens is None:
        print("The input address dosen't exist in our database ")
        session.close()
        return None

    elif availableTokens < commentTransferAmount:
        print("\nThe transfer amount passed in the comments is more than the user owns\nThis transaction will be discarded\n")
        session.close()
        return None

    elif availableTokens >= commentTransferAmount:
        table = session.query(ActiveTable).filter(ActiveTable.address==inputAddress).all()
        string = "{} getblock {}".format(localapi, transaction_data['blockhash'])
        response = subprocess.check_output(string, shell=True)
        block_data = json.loads(response.decode("utf-8"))

        pidlst = []
        checksum = 0
        for row in table:
            if checksum >= commentTransferAmount:
                break
            pidlst.append([row.id, row.transferBalance])
            checksum = checksum + row.transferBalance

        if checksum == commentTransferAmount:
            consumedpid_string = ''

            # Update all pids in pidlist's transferBalance to 0
            lastid = session.query(ActiveTable)[-1].id
            for piditem in pidlst:
                entry = session.query(ActiveTable).filter(ActiveTable.id == piditem[0]).all()
                consumedpid_string = consumedpid_string + '{},'.format(piditem[0])
                session.add(TransferLogs(sourceFloAddress=inputAddress, destFloAddress=outputAddress,
                                         transferAmount=entry[0].transferBalance, sourceId=piditem[0], destinationId=lastid+1,
                                         blockNumber=block_data['height'], time=block_data['time'],
                                         transactionHash=transaction_data['txid']))
                entry[0].transferBalance = 0

            if len(consumedpid_string)>1:
                consumedpid_string = consumedpid_string[:-1]

            # Make new entry
            session.add(ActiveTable(address=outputAddress, consumedpid=consumedpid_string,
                                    transferBalance=commentTransferAmount))

            # Migration
            # shift pid of used utxos from active to consumed
            for piditem in pidlst:
                # move the parentids consumed to consumedpid column in both activeTable and consumedTable
                entries = session.query(ActiveTable).filter(ActiveTable.parentid == piditem[0]).all()
                for entry in entries:
                    entry.consumedpid = entry.consumedpid + ',{}'.format(piditem[0])
                    entry.parentid = None

                entries = session.query(ConsumedTable).filter(ConsumedTable.parentid == piditem[0]).all()
                for entry in entries:
                    entry.consumedpid = entry.consumedpid + ',{}'.format(piditem[0])
                    entry.parentid = None

                # move the pids consumed in the transaction to consumedTable and delete them from activeTable
                session.execute(
                    'INSERT INTO consumedTable (id, address, parentid, consumedpid, transferBalance) SELECT id, address, parentid, consumedpid, transferBalance FROM activeTable WHERE id={}'.format(
                        piditem[0]))
                session.execute('DELETE FROM activeTable WHERE id={}'.format(piditem[0]))
                session.commit()
            session.commit()

        if checksum > commentTransferAmount:
            consumedpid_string = ''
            # Update all pids in pidlist's transferBalance
            lastid = session.query(ActiveTable)[-1].id
            for idx, piditem in enumerate(pidlst):
                entry = session.query(ActiveTable).filter(ActiveTable.id == piditem[0]).all()
                if idx != len(pidlst) - 1:
                    session.add(TransferLogs(sourceFloAddress=inputAddress, destFloAddress=outputAddress,
                                             transferAmount=entry[0].transferBalance, sourceId=piditem[0],
                                             destinationId=lastid + 1,
                                             blockNumber=block_data['height'], time=block_data['time'],
                                             transactionHash=transaction_data['txid']))
                    entry[0].transferBalance = 0
                    consumedpid_string = consumedpid_string + '{},'.format(piditem[0])
                else:
                    session.add(TransferLogs(sourceFloAddress=inputAddress, destFloAddress=outputAddress,
                                             transferAmount=piditem[1]-(checksum - commentTransferAmount), sourceId=piditem[0],
                                             destinationId=lastid + 1,
                                             blockNumber=block_data['height'], time=block_data['time'],
                                             transactionHash=transaction_data['txid']))
                    entry[0].transferBalance = checksum - commentTransferAmount


            if len(consumedpid_string) > 1:
                consumedpid_string = consumedpid_string[:-1]

            # Make new entry
            session.add(ActiveTable(address=outputAddress, parentid= pidlst[-1][0], consumedpid=consumedpid_string,
                                    transferBalance=commentTransferAmount))

            # Migration
            # shift pid of used utxos from active to consumed
            for piditem in pidlst[:-1]:
                # move the parentids consumed to consumedpid column in both activeTable and consumedTable
                entries = session.query(ActiveTable).filter(ActiveTable.parentid == piditem[0]).all()
                for entry in entries:
                    entry.consumedpid = entry.consumedpid + ',{}'.format(piditem[0])
                    entry.parentid = None

                entries = session.query(ConsumedTable).filter(ConsumedTable.parentid == piditem[0]).all()
                for entry in entries:
                    entry.consumedpid = entry.consumedpid + ',{}'.format(piditem[0])
                    entry.parentid = None

                # move the pids consumed in the transaction to consumedTable and delete them from activeTable
                session.execute(
                    'INSERT INTO consumedTable (id, address, parentid, consumedpid, transferBalance) SELECT id, address, parentid, consumedpid, transferBalance FROM activeTable WHERE id={}'.format(
                        piditem[0]))
                session.execute('DELETE FROM activeTable WHERE id={}'.format(piditem[0]))
                session.commit()
            session.commit()

        string = "{} getblock {}".format(localapi, transaction_data['blockhash'])
        response = subprocess.check_output(string, shell=True)
        block_data = json.loads(response.decode("utf-8"))
        blockchainReference = neturl + 'tx/' + transaction_data['txid']
        session.add(TransactionHistory(sourceFloAddress=inputAddress, destFloAddress=outputAddress,
                                 transferAmount=tokenAmount, blockNumber=block_data['height'], time=block_data['time'],
                                 transactionHash=transaction_data['txid'], blockchainReference=blockchainReference))
        session.commit()
        session.close()
        return 1


def startWorking(transaction_data, parsed_data):

    # Do the necessary checks for the inputs and outputs

    # todo Rule 38 - Here we are doing FLO processing. We attach asset amounts to a FLO address, so every FLO address
    #        will have multiple feed ins of the asset. Each of those feedins will be an input to the address.
    #        an address can also spend the asset. Each of those spends is an output of that address feeding the asset into some
    #        other address an as input

    # Rule 38 reframe - For checking any asset transfer on the flo blockchain it is possible that some transactions may use more than one
    # vins. However in any single transaction the system considers valid, they can be only one source address from which the flodata is
    # originting. To ensure consistency, we will have to check that even if there are more than one vins in a transaction, there should be
    # excatly one FLO address on the originating side and that FLO address should be the owner of the asset tokens being transferred

    # Create vinlist and outputlist
    vinlist = []
    querylist = []

    # todo Rule 39 - Create a list of vins for a given transaction id
    for obj in transaction_data["vin"]:
        querylist.append([obj["txid"], obj["vout"]])


    totalinputval = 0
    inputadd = ''

    # todo Rule 40 - For each vin, find the feeding address and the fed value. Make an inputlist containing [inputaddress, n value]
    for query in querylist:
        string = "{} getrawtransaction {} 1".format(localapi, str(query[0]))
        response = subprocess.check_output(string, shell=True)
        content = json.loads(response.decode("utf-8"))

        for objec in content["vout"]:
            if objec["n"] == query[1]:
                inputadd = objec["scriptPubKey"]["addresses"][0]
                totalinputval = totalinputval + objec["value"]
                vinlist.append([inputadd, objec["value"]])

    # todo Rule 41 - Check if all the addresses in a transaction on the input side are the same
    for idx, item in enumerate(vinlist):
        if idx == 0:
            temp = item[0]
            continue
        if item[0] != temp:
            print('System has found more than one address as part of vin')
            return

    inputlist = [vinlist[0][0], totalinputval]


    # todo Rule 42 - If the number of vout is more than 2, reject the transaction
    if len(transaction_data["vout"]) > 2:
        print("Program has detected more than 2 vouts ")
        print("This transaction will be discarded")
        return

    # todo Rule 43 - A transaction accepted by the system has two vouts, 1. The FLO address of the receiver
    #      2. Flo address of the sender as change address.  If the vout address is change address, then the other adddress
    #     is the recevier address

    outputlist = []
    for obj in transaction_data["vout"]:
        if obj["scriptPubKey"]["type"] == "pubkeyhash":
            if inputlist[0] == obj["scriptPubKey"]["addresses"][0]:
                continue
            outputlist.append([obj["scriptPubKey"]["addresses"][0], obj["value"]])

    if len(outputlist) != 1:
        print("The transaction change is not coming back to the input address")
        return

    outputlist = outputlist[0]

    print("\n\nInput Address")
    print(inputlist)
    print("\nOutput Address")
    print(outputlist)

    # All FLO checks completed at this point.
    # Semantic rules for parsed data begins


    # todo Rule 44 - Process as per the type of transaction
    if parsed_data['type'] == 'transfer':
        print('Found a transaction of the type transfer')

        # todo Rule 45 - If the transfer type is token, then call the function transferToken to adjust the balances
        if parsed_data['transferType'] == 'token':
            returnval = transferToken(parsed_data['tokenIdentification'], parsed_data['tokenAmount'], inputlist[0], outputlist[0])
            if returnval is None:
                print("Something went wrong in the token transfer method")

        # todo Rule 46 - If the transfer type is smart contract, then call the function transferToken to do sanity checks & lock the balance
        elif parsed_data['transferType'] == 'smartContract':
            # Check if the contract has expired
            if parsed_data['expiryTime'] and time.time()>parsed_data['expiryTime']:
                print('Contract has expired and will not accept any user participation')
                return
            # Check if the tokenAmount being transferred exists in the address & do the token transfer
            returnval = transferToken(parsed_data['tokenIdentification'], parsed_data['tokenAmount'], inputlist[0], outputlist[0])
            if returnval is not None:
                # Store participant details in the smart contract's db
                engine = create_engine('sqlite:///smartContracts/{}.db'.format(parsed_data['contractName']), echo=True)
                Base.metadata.create_all(bind=engine)
                session = sessionmaker(bind=engine)()
                session.add(ContractParticipants(participantAddress=inputadd, tokenAmount=parsed_data['tokenAmount'], userPreference=parsed_data['userPreference']))
                session.commit()
                session.close()
            else:
                print("Something went wrong in the smartcontract token transfer method")

    # todo Rule 47 - If the parsed data type is token incorporation, then check if the name hasn't been taken already
    #      if it has been taken then reject the incorporation. Else incorporate it
    elif parsed_data['type'] == 'tokenIncorporation':
        if not os.path.isfile('./tokens/{}.db'.format(parsed_data['tokenIdentification'])):
            engine = create_engine('sqlite:///tokens/{}.db'.format(parsed_data['tokenIdentification']), echo=True)
            Base.metadata.create_all(bind=engine)
            session = sessionmaker(bind=engine)()
            session.add(ActiveTable(address=inputlist[0], parentid=0, transferBalance=parsed_data['tokenAmount']))
            string = "{} getblock {}".format(localapi, transaction_data['blockhash'])
            response = subprocess.check_output(string, shell=True)
            block_data = json.loads(response.decode("utf-8"))
            session.add(TransferLogs(sourceFloAddress=inputadd, destFloAddress=outputlist[0], transferAmount=parsed_data['tokenAmount'], sourceId=0, destinationId=1, blockNumber=block_data['height'], time=block_data['time'], transactionHash=transaction_data['txid']))
            blockchainReference = neturl + 'tx/' + transaction_data['txid']
            session.add(TransactionHistory(sourceFloAddress=inputadd, destFloAddress='-',
                                           transferAmount=parsed_data['tokenAmount'], blockNumber=block_data['height'],
                                           time=block_data['time'],
                                           transactionHash=transaction_data['txid'],
                                           blockchainReference=blockchainReference))
            session.commit()
            session.close()
        else:
            print('Transaction rejected as the token with same name has already been incorporated')

    # todo Rule 48 - If the parsed data type if smart contract incorporation, then check if the name hasn't been taken already
    #         if it has been taken then reject the incorporation.
    elif parsed_data['type'] == 'smartContractIncorporation':
        if not os.path.isfile('./smartContracts/{}.db'.format(parsed_data['contractName'])):
            # todo Rule 49 - If the contract name hasn't been taken before, check if the contract type is an authorized type by the system
            if parsed_data['contractType'] == 'betting':
                print("Smart contract is of the type betting")
                # todo Rule 50 - Contract address mentioned in flodata field should be same as the receiver FLO address on the output side
                #    henceforth we will not consider any flo private key initiated comment as valid from this address
                #    Unlocking can only be done through smart contract system address
                if parsed_data['contractAddress'] == outputlist[0]:
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
        if inputlist[0] in committeeAddressList:

            # Check if the output address is an active Smart contract address
            engine = create_engine('sqlite:///system.db', echo=True)
            connection = engine.connect()
            activeContracts = connection.execute('select * from activecontracts').fetchall()
            connection.close()

            # Change columns into rows - https://stackoverflow.com/questions/44360162/how-to-access-a-column-in-a-list-of-lists-in-python
            activeContracts = list(zip(*activeContracts))
            if outputlist[0] in activeContracts[2] and parsed_data['contractName'] in activeContracts[1]:

                engine = create_engine('sqlite:///smartContracts/{}.db'.format(parsed_data['contractName']), echo=True)
                connection = engine.connect()
                contractWinners = connection.execute('select * from contractparticipants where userPreference="{}"'.format(parsed_data['triggerCondition'])).fetchall()
                tokenSum = connection.execute('select sum(tokenAmount) from contractparticipants').fetchall()[0][0]
                tokenIdentification = connection.execute('select value from contractstructure where attribute="tokenIdentification"').fetchall()[0][0]
                connection.close()

                contractWinners = list(zip(*contractWinners))
                for address in contractWinners[1]:
                    transferToken(tokenIdentification, tokenSum/len(contractWinners[1]), outputlist[0], address)

            else:
                print('This trigger doesn\'t apply to an active contract. It will be discarded')

        else:
            print('Input address is not part of the committee address list. This trigger is rejected')


# todo Rule 1 - Read command line arguments to reset the databases as blank
#  Rule 2  - Read config to set testnet/mainnet
#  Rule 3  - Set flo blockexplorer location depending on testnet or mainnet
#  Rule 4 -  Set the local flo-cli path depending on testnet or mainnet
#  Rule 5 - Set the block number to scan from



# Read command line arguments
parser = argparse.ArgumentParser(description='Script tracks RMT using FLO data on the FLO blockchain - https://flo.cash')
parser.add_argument('-r', '--reset', nargs='?', const=1, type=int, help='Purge existing db and rebuild it')
args = parser.parse_args()

apppath = os.path.dirname(os.path.realpath(__file__))
dirpath = os.path.join(apppath, 'tokens')
if not os.path.isdir(dirpath):
    os.mkdir(dirpath)
dirpath = os.path.join(apppath, 'smartContracts')
if not os.path.isdir(dirpath):
    os.mkdir(dirpath)

# Read configuration
config = configparser.ConfigParser()
config.read('config.ini')

# Assignment the flo-cli command
if config['DEFAULT']['NET'] == 'mainnet':
    neturl = 'https://flosight.duckdns.org/'
    localapi = config['DEFAULT']['FLO_CLI_PATH']
elif config['DEFAULT']['NET'] == 'testnet':
    neturl = 'https://testnet-flosight.duckdns.org/'
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
    dirpath = os.path.join(apppath, 'system.db')
    if os.path.exists(dirpath):
        os.remove(dirpath)

    # Read start block no
    startblock = int(config['DEFAULT']['START_BLOCK'])
    engine = create_engine('sqlite:///system.db', echo=True)
    SystemBase.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add( SystemData(attribute='lastblockscanned', value=startblock-1))
    session.commit()
    session.close()


# Read start block no
engine = create_engine('sqlite:///system.db', echo=True)
SystemBase.metadata.create_all(bind=engine)
session = sessionmaker(bind=engine)()
startblock = int(session.query(SystemData).filter_by(attribute='lastblockscanned').all()[0].value)
session.commit()
session.close()



# todo Rule 6 - Find current block height
#     Rule 7 - Start analysing the block contents from starting block to current height

# Find current block height
string = "{} getblockcount".format(localapi)
response = subprocess.check_output(string, shell=True)
current_index = json.loads(response.decode("utf-8"))
print("current_block_height : " + str(current_index))


for blockindex in range( startblock, current_index ):
    print(blockindex)

    if blockindex == 3387978:
        print('hello')

    # Scan every block
    string = "{} getblockhash {}".format(localapi, str(blockindex))
    response = subprocess.check_output(string, shell=True)
    blockhash = response.decode("utf-8")

    string = "{} getblock {}".format(localapi, str(blockhash))
    response = subprocess.check_output(string, shell=True)
    blockinfo = json.loads(response.decode("utf-8"))

    # todo Rule 8 - read every transaction from every block to find and parse flodata

    # Scan every transaction
    for transaction in blockinfo["tx"]:
        string = "{} getrawtransaction {} 1".format(localapi, str(transaction))
        response = subprocess.check_output(string, shell=True)
        transaction_data = json.loads(response.decode("utf-8"))
        text = transaction_data["floData"]

    # todo Rule 9 - Reject all noise transactions. Further rules are in parsing.py

        parsed_data = parsing.parse_flodata(text)
        if parsed_data['type'] != 'noise':
            print(blockindex)
            print(parsed_data['type'])
            startWorking(transaction_data, parsed_data)

        engine = create_engine('sqlite:///system.db')
        SystemBase.metadata.create_all(bind=engine)
        session = sessionmaker(bind=engine)()
        entry = session.query(SystemData).filter(SystemData.attribute == 'lastblockscanned').all()[0]
        entry.value = str(blockindex)
        session.commit()
        session.close()

