import argparse
import configparser
import json
import logging
import os
import shutil
import sqlite3
import sys
import pybtc
import requests
import socketio
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
import time
import parsing 
from config import *
from datetime import datetime
import pdb
from models import SystemData, ActiveTable, ConsumedTable, TransferLogs, TransactionHistory, RejectedTransactionHistory, Base, ContractStructure, ContractBase, ContractParticipants, SystemBase, ActiveContracts, ContractAddressMapping, LatestCacheBase, ContractTransactionHistory, RejectedContractTransactionHistory, TokenContractAssociation, ContinuosContractBase, ContractStructure1, ContractParticipants1, ContractDeposits1, ContractTransactionHistory1


goodblockset = {}
goodtxset = {}


def newMultiRequest(apicall):
    current_server = serverlist[0]
    while True:
        try:
            response = requests.get('{}api/{}'.format(current_server, apicall))
        except:
            current_server = switchNeturl(current_server)
            logger.info(f"newMultiRequest() switched to {current_server}")
            time.sleep(2)
        else:
            if response.status_code == 200:
                return json.loads(response.content)
            else:
                current_server = switchNeturl(current_server) 
                logger.info(f"newMultiRequest() switched to {current_server}")
                time.sleep(2)


def pushData_SSEapi(message):
    signature = pybtc.sign_message(message.encode(), privKey)
    headers = {'Accept': 'application/json', 'Content-Type': 'application/json', 'Signature': signature}

    '''try:
        r = requests.post(sseAPI_url, json={'message': '{}'.format(message)}, headers=headers)
    except:
    logger.error("couldn't push the following message to SSE api {}".format(message))'''
    print('')


def check_database_existence(type, parameters):
    if type == 'token':
        return os.path.isfile(f"./tokens/{parameters['token_name']}.db")

    if type == 'smart_contract':
        return os.path.isfile(f"./smartContracts/{parameters['contract_name']}-{parameters['contract_address']}.db")


def create_database_connection(type, parameters):
    if type == 'token':
        engine = create_engine(f"sqlite:///tokens/{parameters['token_name']}.db", echo=True)
    elif type == 'smart_contract':
        engine = create_engine(f"sqlite:///smartContracts/{parameters['contract_name']}-{parameters['contract_address']}.db", echo=True)
    elif type == 'system_dbs':
        engine = create_engine(f"sqlite:///{parameters['db_name']}.db", echo=False)

    connection = engine.connect()
    return connection


def create_database_session_orm(type, parameters, base):
    if type == 'token':
        engine = create_engine(f"sqlite:///tokens/{parameters['token_name']}.db", echo=True)
        base.metadata.create_all(bind=engine)
        session = sessionmaker(bind=engine)()

    elif type == 'smart_contract':
        engine = create_engine(f"sqlite:///smartContracts/{parameters['contract_name']}-{parameters['contract_address']}.db", echo=True)
        base.metadata.create_all(bind=engine)
        session = sessionmaker(bind=engine)()
    
    elif type == 'system_dbs':
        engine = create_engine(f"sqlite:///{parameters['db_name']}.db", echo=False)
        base.metadata.create_all(bind=engine)
        session = sessionmaker(bind=engine)()
    
    return session


def processBlock(blockindex=None, blockhash=None):
    if blockindex is not None and blockhash is None:
        logger.info(f'Processing block {blockindex}')
        # Get block details
        response = newMultiRequest(f"block-index/{blockindex}")
        blockhash = response['blockHash']

    blockinfo = newMultiRequest(f"block/{blockhash}")

    # todo Rule 8 - read every transaction from every block to find and parse flodata
    counter = 0
    acceptedTxList = []
    # Scan every transaction
    logger.info("Before tx loop")
    counter = 0
    for transaction in blockinfo["tx"]:
        counter = counter + 1
        logger.info(f"Transaction {counter} {transaction}")
        current_index = -1
        while(current_index == -1):
            transaction_data = newMultiRequest(f"tx/{transaction}")
            try:
                text = transaction_data["floData"]
                text = text.replace("\n", " \n ")
                text = "create 1000 rmt#"
                current_index = 2
            except:
                logger.info("The API has passed the Block height test but failed transaction_data['floData'] test")
                logger.info(f"Block Height : {blockinfo['height']}")
                logger.info(f"Transaction {transaction} data : ")
                logger.info(transaction_data)
                logger.info('Program will wait for 1 seconds and try to reconnect')
                time.sleep(1)  
            
        # todo Rule 9 - Reject all noise transactions. Further rules are in parsing.py
        returnval = None
        #parsed_data = parsing.parse_flodata(text, blockinfo, config['DEFAULT']['NET'])
        parsed_data = parsing.parse_flodata(text, blockinfo, config['DEFAULT']['NET'])
        if parsed_data['type'] != 'noise':
            logger.info(f"Processing transaction {transaction}")
            logger.info(f"flodata {text} is parsed to {parsed_data}")
            returnval = processTransaction(transaction_data, parsed_data)

        if returnval == 1:
            acceptedTxList.append(transaction)
        elif returnval == 0:
            logger.info("Transfer for the transaction %s is illegitimate. Moving on" % transaction)

    if len(acceptedTxList) > 0:
        tempinfo = blockinfo['tx'].copy()
        for tx in blockinfo['tx']:
            if tx not in acceptedTxList:
                tempinfo.remove(tx)
        blockinfo['tx'] = tempinfo
        updateLatestBlock(blockinfo)

    session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
    entry = session.query(SystemData).filter(SystemData.attribute == 'lastblockscanned').all()[0]
    entry.value = str(blockinfo['height'])
    session.commit()
    session.close()

    # Check smartContracts which will be triggered locally, and not by the contract committee
    checkLocaltriggerContracts(blockinfo)
    # Check if any deposits have to be returned 
    checkReturnDeposits(blockinfo)


def updateLatestTransaction(transactionData, parsed_data):
    # connect to latest transaction db
    conn = sqlite3.connect('latestCache.db')
    conn.execute(
        "INSERT INTO latestTransactions(transactionHash, blockNumber, jsonData, transactionType, parsedFloData) VALUES (?,?,?,?,?)",
        (transactionData['txid'], transactionData['blockheight'], json.dumps(transactionData), parsed_data['type'],
         json.dumps(parsed_data)))
    conn.commit()
    conn.close()


def updateLatestBlock(blockData):
    # connect to latest block db
    conn = sqlite3.connect('latestCache.db')
    conn.execute('INSERT INTO latestBlocks(blockNumber, blockHash, jsonData) VALUES (?,?,?)', (blockData['height'], blockData['hash'], json.dumps(blockData)))
    conn.commit()
    conn.close()


def transferToken(tokenIdentification, tokenAmount, inputAddress, outputAddress, transaction_data=None, parsed_data=None):
    session = create_database_session_orm('token', {'token_name': f"{tokenIdentification}"}, Base)

    availableTokens = session.query(func.sum(ActiveTable.transferBalance)).filter_by(address=inputAddress).all()[0][0]
    commentTransferAmount = float(tokenAmount)
    if availableTokens is None:
        logger.info(f"The sender address {inputAddress} doesn't own any {tokenIdentification.upper()} tokens")
        session.close()
        return 0

    elif availableTokens < commentTransferAmount:
        logger.info("The transfer amount passed in the comments is more than the user owns\nThis transaction will be discarded\n")
        session.close()
        return 0

    elif availableTokens >= commentTransferAmount:
        table = session.query(ActiveTable).filter(ActiveTable.address == inputAddress).all()
        block_data = newMultiRequest('block/{}'.format(transaction_data['blockhash']))

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
                                         transferAmount=entry[0].transferBalance, sourceId=piditem[0],
                                         destinationId=lastid + 1,
                                         blockNumber=block_data['height'], time=block_data['time'],
                                         transactionHash=transaction_data['txid']))
                entry[0].transferBalance = 0

            if len(consumedpid_string) > 1:
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

        elif checksum > commentTransferAmount:
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
                                             transferAmount=piditem[1] - (checksum - commentTransferAmount),
                                             sourceId=piditem[0],
                                             destinationId=lastid + 1,
                                             blockNumber=block_data['height'], time=block_data['time'],
                                             transactionHash=transaction_data['txid']))
                    entry[0].transferBalance = checksum - commentTransferAmount

            if len(consumedpid_string) > 1:
                consumedpid_string = consumedpid_string[:-1]

            # Make new entry
            session.add(ActiveTable(address=outputAddress, parentid=pidlst[-1][0], consumedpid=consumedpid_string,
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

        block_data = newMultiRequest('block/{}'.format(transaction_data['blockhash']))

        blockchainReference = neturl + 'tx/' + transaction_data['txid']
        session.add(TransactionHistory(sourceFloAddress=inputAddress, destFloAddress=outputAddress,
                                       transferAmount=tokenAmount, blockNumber=block_data['height'],
                                       blockHash=block_data['hash'], time=block_data['time'],
                                       transactionHash=transaction_data['txid'],
                                       blockchainReference=blockchainReference, jsonData=json.dumps(transaction_data),
                                       transactionType=parsed_data['type'],
                                       parsedFloData=json.dumps(parsed_data)))
        session.commit()
        session.close()
        return 1


def checkLocaltriggerContracts(blockinfo):
    connection = create_database_connection('system_dbs', {'db_name':"system"})
    # todo : filter activeContracts which only have local triggers
    activeContracts = connection.execute('select contractName, contractAddress from activecontracts where status=="active" ').fetchall()
    connection.close()

    for contract in activeContracts:

        # pull out the contract structure into a dictionary
        connection = create_database_connection('smart_contract', {'contract_name':f"{contract[0]}", 'contract_address':f"{contract[1]}"})
        # todo : filter activeContracts which only have local triggers
        attributevaluepair = connection.execute(
            "select attribute, value from contractstructure where attribute != 'contractName' and attribute != 'flodata' and attribute != 'contractAddress'").fetchall()
        contractStructure = {}
        conditionDict = {}
        counter = 0
        for item in attributevaluepair:
            if list(item)[0] == 'exitconditions':
                conditionDict[counter] = list(item)[1]
                counter = counter + 1
            else:
                contractStructure[list(item)[0]] = list(item)[1]
        if len(conditionDict) > 0:
            contractStructure['exitconditions'] = conditionDict
        del counter, conditionDict

        if contractStructure['contractType'] == 'one-time-event':
            # Check if the contract has blockchain trigger or committee trigger
            if 'exitconditions' in contractStructure:
                # This is a committee trigger contract
                expiryTime = contractStructure['expiryTime']
                expirytime_split = expiryTime.split(' ')
                parse_string = '{}/{}/{} {}'.format(expirytime_split[3], parsing.months[expirytime_split[1]],
                                                    expirytime_split[2], expirytime_split[4])
                expirytime_object = parsing.arrow.get(parse_string, 'YYYY/M/D HH:mm:ss').replace(
                    tzinfo=expirytime_split[5][3:])
                blocktime_object = parsing.arrow.get(blockinfo['time']).to('Asia/Kolkata')

                if blocktime_object > expirytime_object:
                    if 'minimumsubscriptionamount' in contractStructure:
                        minimumsubscriptionamount = contractStructure['minimumsubscriptionamount']
                        tokenAmount_sum = \
                            connection.execute('select sum(tokenAmount) from contractparticipants').fetchall()[0][0]
                        if tokenAmount_sum < minimumsubscriptionamount:
                            # Initialize payback to contract participants
                            contractParticipants = connection.execute(
                                'select participantAddress, tokenAmount, transactionHash from contractparticipants').fetchall()[
                                0][0]

                            for participant in contractParticipants:
                                tokenIdentification = contractStructure['tokenIdentification']
                                contractAddress = connection.execute(
                                    'select * from contractstructure where attribute="contractAddress"').fetchall()[0][
                                    0]
                                returnval = transferToken(tokenIdentification, participant[1], contractAddress,
                                                          participant[0])
                                if returnval is None:
                                    logger.critical(
                                        "Something went wrong in the token transfer method while doing local Smart Contract Trigger. THIS IS CRITICAL ERROR")
                                    return
                                connection.execute(
                                    'update contractparticipants set winningAmount="{}" where participantAddress="{}" and transactionHash="{}"'.format(
                                        (participant[1], participant[0], participant[2])))

                            # add transaction to ContractTransactionHistory
                            session = create_database_session_orm('smart_contract', {'contract_name': f"{contract[0]}", 'contract_address': f"{contract[1]}"}, ContractBase)
                            session.add(ContractTransactionHistory(transactionType='trigger',
                                                                   transactionSubType='minimumsubscriptionamount-payback',
                                                                   transferAmount=None,
                                                                   blockNumber=blockinfo['height'],
                                                                   blockHash=blockinfo['hash'],
                                                                   time=blockinfo['time']))
                            session.commit()
                            session.close()

                            connection = create_database_connection('system_dbs', {'db_name':'system'})
                            connection.execute(
                                'update activecontracts set status="closed" where contractName="{}" and contractAddress="{}"'.format(
                                    contract[0], contract[1]))
                            connection.execute(
                                'update activecontracts set closeDate="{}" where contractName="{}" and contractAddress="{}"'.format(
                                    blockinfo['time'],
                                    contract[0], contract[1]))
                            connection.close()

                    connection = create_database_connection('system_dbs', {'db_name':'system'})
                    connection.execute(
                        'update activecontracts set status="expired" where contractName="{}" and contractAddress="{}"'.format(
                            contract[0], contract[1]))
                    connection.execute(
                        'update activecontracts set expirydate="{}" where contractName="{}" and contractAddress="{}"'.format(
                            blockinfo['time'],
                            contract[0], contract[1]))
                    connection.close()

            elif 'payeeAddress' in contractStructure:
                # This is a local trigger contract
                if 'maximumsubscriptionamount' in contractStructure:
                    maximumsubscriptionamount = connection.execute(
                        'select value from contractstructure where attribute=="maximumsubscriptionamount"').fetchall()[
                        0][0]
                    tokenAmount_sum = \
                        connection.execute('select sum(tokenAmount) from contractparticipants').fetchall()[0][0]
                    if tokenAmount_sum >= maximumsubscriptionamount:
                        # Trigger the contract
                        payeeAddress = contractStructure['payeeAddress']
                        tokenIdentification = contractStructure['tokenIdentification']
                        contractAddress = contractStructure['contractAddress']
                        returnval = transferToken(tokenIdentification, tokenAmount_sum, contractAddress, payeeAddress)
                        if returnval is None:
                            logger.critical(
                                "Something went wrong in the token transfer method while doing local Smart Contract Trigger")
                            return
                        connection.execute(
                            'update contractparticipants set winningAmount="{}"'.format(
                                (0)))

                        # add transaction to ContractTransactionHistory                        
                        session = create_database_session_orm('smart_contract', {'contract_name': f"{contract[0]}", 'contract_address': f"{contract[1]}"}, ContractBase)
                        session.add(ContractTransactionHistory(transactionType='trigger',
                                                               transactionSubType='maximumsubscriptionamount',
                                                               sourceFloAddress=contractAddress,
                                                               destFloAddress=payeeAddress,
                                                               transferAmount=tokenAmount_sum,
                                                               blockNumber=blockinfo['height'],
                                                               blockHash=blockinfo['hash'],
                                                               time=blockinfo['time']))
                        session.commit()
                        session.close()

                        connection = create_database_connection('system_dbs', {'db_name':'system'})
                        connection.execute(
                            'update activecontracts set status="closed" where contractName="{}" and contractAddress="{}"'.format(
                                contract[0], contract[1]))
                        connection.execute(
                            'update activecontracts set closeDate="{}" where contractName="{}" and contractAddress="{}"'.format(
                                blockinfo['time'], contract[0], contract[1]))
                        connection.execute(
                            'update activecontracts set expiryDate="{}" where contractName="{}" and contractAddress="{}"'.format(
                                blockinfo['time'], contract[0], contract[1]))
                        connection.close()
                        return

                expiryTime = contractStructure['expiryTime']
                expirytime_split = expiryTime.split(' ')
                parse_string = '{}/{}/{} {}'.format(expirytime_split[3], parsing.months[expirytime_split[1]],
                                                    expirytime_split[2], expirytime_split[4])
                expirytime_object = parsing.arrow.get(parse_string, 'YYYY/M/D HH:mm:ss').replace(
                    tzinfo=expirytime_split[5][3:])
                blocktime_object = parsing.arrow.get(blockinfo['time']).to('Asia/Kolkata')

                if blocktime_object > expirytime_object:
                    if 'minimumsubscriptionamount' in contractStructure:
                        minimumsubscriptionamount = contractStructure['minimumsubscriptionamount']
                        tokenAmount_sum = \
                            connection.execute('select sum(tokenAmount) from contractparticipants').fetchall()[0][0]
                        if tokenAmount_sum < minimumsubscriptionamount:
                            # Initialize payback to contract participants
                            contractParticipants = connection.execute(
                                'select participantAddress, tokenAmount, transactionHash from contractparticipants').fetchall()[
                                0][0]

                            for participant in contractParticipants:
                                tokenIdentification = connection.execute(
                                    'select * from contractstructure where attribute="tokenIdentification"').fetchall()[
                                    0][
                                    0]
                                contractAddress = connection.execute(
                                    'select * from contractstructure where attribute="contractAddress"').fetchall()[0][
                                    0]
                                returnval = transferToken(tokenIdentification, participant[1], contractAddress,
                                                          participant[0])
                                if returnval is None:
                                    logger.critical(
                                        "Something went wrong in the token transfer method while doing local Smart Contract Trigger")
                                    return
                                connection.execute(
                                    'update contractparticipants set winningAmount="{}" where participantAddress="{}" and transactionHash="{}"'.format(
                                        (participant[1], participant[0], participant[2])))

                            # add transaction to ContractTransactionHistory
                            session = create_database_session_orm('smart_contract', {'contract_name': f"{contract[0]}", 'contract_address': f"{contract[1]}"}, ContractBase)
                            session.add(ContractTransactionHistory(transactionType='trigger',
                                                                   transactionSubType='minimumsubscriptionamount-payback',
                                                                   transferAmount=None,
                                                                   blockNumber=blockinfo['height'],
                                                                   blockHash=blockinfo['hash'],
                                                                   time=blockinfo['time']))
                            session.commit()
                            session.close()

                            connection = create_database_connection('system_dbs', {'db_name':'system'})
                            connection.execute(
                                'update activecontracts set status="closed" where contractName="{}" and contractAddress="{}"'.format(
                                    contract[0], contract[1]))
                            connection.execute(
                                'update activecontracts set closeDate="{}" where contractName="{}" and contractAddress="{}"'.format(
                                    blockinfo['time'], contract[0], contract[1]))
                            connection.execute(
                                'update activecontracts set expiryDate="{}" where contractName="{}" and contractAddress="{}"'.format(
                                    blockinfo['time'], contract[0], contract[1]))
                            connection.close()
                            return

                    # Trigger the contract
                    payeeAddress = contractStructure['payeeAddress']
                    tokenIdentification = contractStructure['tokenIdentification']
                    contractAddress = contractStructure['contractAddress']
                    connection = create_database_connection('smart_contract', {'contract_name':f"{contract[0]}", 'contract_address':f"{contract[1]}"})
                    tokenAmount_sum = \
                        connection.execute('select sum(tokenAmount) from contractparticipants').fetchall()[0][0]
                    returnval = transferToken(tokenIdentification, tokenAmount_sum, contractAddress, payeeAddress)
                    if returnval is None:
                        logger.critical(
                            "Something went wrong in the token transfer method while doing local Smart Contract Trigger")
                        return
                    connection.execute('update contractparticipants set winningAmount="{}"'.format(0))

                    # add transaction to ContractTransactionHistory
                    session = create_database_session_orm('smart_contract', {'contract_name': f"{contract[0]}", 'contract_address': f"{contract[1]}"}, ContractBase)
                    session.add(ContractTransactionHistory(transactionType='trigger',
                                                           transactionSubType='expiryTime',
                                                           sourceFloAddress=contractAddress,
                                                           destFloAddress=payeeAddress,
                                                           transferAmount=tokenAmount_sum,
                                                           blockNumber=blockinfo['height'],
                                                           blockHash=blockinfo['hash'],
                                                           time=blockinfo['time']))
                    session.commit()
                    session.close()

                    connection = create_database_connection('system_dbs', {'db_name':'system'})
                    connection.execute(
                        'update activecontracts set status="closed" where contractName="{}" and contractAddress="{}"'.format(
                            contract[0], contract[1]))
                    connection.execute(
                        'update activecontracts set closeDate="{}" where contractName="{}" and contractAddress="{}"'.format(
                            blockinfo['time'], contract[0], contract[1]))
                    connection.execute(
                        'update activecontracts set expiryDate="{}" where contractName="{}" and contractAddress="{}"'.format(
                            blockinfo['time'], contract[0], contract[1]))
                    connection.close()
                    return


def checkReturnDeposits(blockinfo):
    pass


def processTransaction(transaction_data, parsed_data):
    # Do the necessary checks for the inputs and outputs
    # todo Rule 38 - Here we are doing FLO processing. We attach asset amounts to a FLO address, so every FLO address
    #        will have multiple feed ins of the asset. Each of those feedins will be an input to the address.
    #        an address can also spend the asset. Each of those spends is an output of that address feeding the asset into some
    #        other address an as input
    # Rule 38 reframe - For checking any asset transfer on the flo blockchain it is possible that some transactions may use more than one
    # vins. However in any single transaction the system considers valid, they can be only one source address from which the flodata is
    # originting. To ensure consistency, we will have to check that even if there are more than one vins in a transaction, there should be
    # exactly one FLO address on the originating side and that FLO address should be the owner of the asset tokens being transferred


    # Create vinlist and outputlist
    vinlist = []
    querylist = []

    # todo Rule 39 - Create a list of vins for a given transaction id
    for obj in transaction_data["vin"]:
        if 'coinbase' in obj.keys():
            return 0
        querylist.append([obj["txid"], obj["vout"]])

    totalinputval = 0
    inputadd = ''

    # todo Rule 40 - For each vin, find the feeding address and the fed value. Make an inputlist containing [inputaddress, n value]
    for query in querylist:
        content = newMultiRequest('tx/{}'.format(str(query[0])))
        for objec in content["vout"]:
            if objec["n"] == query[1]:
                inputadd = objec["scriptPubKey"]["addresses"][0]
                totalinputval = totalinputval + float(objec["value"])
                vinlist.append([inputadd, objec["value"]])

    # todo Rule 41 - Check if all the addresses in a transaction on the input side are the same
    for idx, item in enumerate(vinlist):
        if idx == 0:
            temp = item[0]
            continue
        if item[0] != temp:
            logger.info(f"System has found more than one address as part of vin. Transaction {transaction_data['txid']} is rejected")
            return 0

    inputlist = [vinlist[0][0], totalinputval]

    # todo Rule 42 - If the number of vout is more than 2, reject the transaction
    if len(transaction_data["vout"]) > 2:
        logger.info(f"System has found more than 2 address as part of vout. Transaction {transaction_data['txid']} is rejected")
        return 0

    # todo Rule 43 - A transaction accepted by the system has two vouts, 1. The FLO address of the receiver
    #      2. Flo address of the sender as change address.  If the vout address is change address, then the other adddress
    #     is the recevier address

    outputlist = []
    addresscounter = 0
    inputcounter = 0
    for obj in transaction_data["vout"]:
        if obj["scriptPubKey"]["type"] == "pubkeyhash":
            addresscounter = addresscounter + 1
            if inputlist[0] == obj["scriptPubKey"]["addresses"][0]:
                inputcounter = inputcounter + 1
                continue
            outputlist.append([obj["scriptPubKey"]["addresses"][0], obj["value"]])

    if addresscounter == inputcounter:
        outputlist = [inputlist[0]]
    elif len(outputlist) != 1:
        logger.info(f"Transaction's change is not coming back to the input address. Transaction {transaction_data['txid']} is rejected")
        return 0
    else:
        outputlist = outputlist[0]

    logger.info(f"Input address list : {inputlist}")
    logger.info(f"Output address list : {outputlist}")

    # All FLO checks completed at this point.
    # Semantic rules for parsed data begins

    # todo Rule 44 - Process as per the type of transaction
    if parsed_data['type'] == 'transfer':
        logger.info(f"Transaction {transaction_data['txid']} is of the type transfer")

        # todo Rule 45 - If the transfer type is token, then call the function transferToken to adjust the balances
        if parsed_data['transferType'] == 'token':
            # check if the token exists in the database
            if check_database_existence('token', {'token_name':f"{parsed_data['tokenIdentification']}"}):
                # Check if the transaction hash already exists in the token db
                connection = create_database_connection('token', {'token_name':f"{create_database_connection}"})
                blockno_txhash = connection.execute('select blockNumber, transactionHash from transactionHistory').fetchall()
                connection.close()
                blockno_txhash_T = list(zip(*blockno_txhash))

                if transaction_data['txid'] in list(blockno_txhash_T[1]):
                    logger.warning(f"Transaction {transaction_data['txid']} already exists in the token db. This is unusual, please check your code")
                    pushData_SSEapi(f"Error | Transaction {transaction_data['txid']} already exists in the token db. This is unusual, please check your code")
                    return 0

                returnval = transferToken(parsed_data['tokenIdentification'], parsed_data['tokenAmount'], inputlist[0],outputlist[0], transaction_data, parsed_data)
                if returnval is None:
                    logger.info("Something went wrong in the token transfer method")
                    pushData_SSEapi(f"Error | Something went wrong while doing the internal db transactions for {transaction_data['txid']}")
                    return 0
                else:
                    updateLatestTransaction(transaction_data, parsed_data)

                # If this is the first interaction of the outputlist's address with the given token name, add it to token mapping
                connection = create_database_connection('system_dbs', {'db_name':'system'})
                firstInteractionCheck = connection.execute(f"select * from tokenAddressMapping where tokenAddress='{outputlist[0]}' and token='{parsed_data['tokenIdentification']}'").fetchall()

                if len(firstInteractionCheck) == 0:
                    connection.execute(f"INSERT INTO tokenAddressMapping (tokenAddress, token, transactionHash, blockNumber, blockHash) VALUES ('{outputlist[0]}', '{parsed_data['tokenIdentification']}', '{transaction_data['txid']}', '{transaction_data['blockheight']}', '{transaction_data['blockhash']}')")

                connection.close()

                # Pass information to SSE channel
                headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
                # r = requests.post(tokenapi_sse_url, json={f"message': 'Token Transfer | name:{parsed_data['tokenIdentification']} | transactionHash:{transaction_data['txid']}"}, headers=headers)
                return 1
            else:
                logger.info(f"Token transfer at transaction {transaction_data['txid']} rejected as a token with the name {parsed_data['tokenIdentification']} doesnt not exist")
                session = create_database_session_orm('system_dbs', {'db_name': "system"}, Base)
                
                blockchainReference = neturl + 'tx/' + transaction_data['txid']
                session.add(RejectedTransactionHistory(tokenIdentification=parsed_data['tokenIdentification'],
                                                       sourceFloAddress=inputadd, destFloAddress=outputlist[0],
                                                       transferAmount=parsed_data['tokenAmount'],
                                                       blockNumber=transaction_data['blockheight'],
                                                       blockHash=transaction_data['blockhash'],
                                                       time=transaction_data['blocktime'],
                                                       transactionHash=transaction_data['txid'],
                                                       blockchainReference=blockchainReference,
                                                       jsonData=json.dumps(transaction_data),
                                                       rejectComment=f"Token transfer at transaction {transaction_data['txid']} rejected as a token with the name {parsed_data['tokenIdentification']} doesnt not exist",
                                                       transactionType=parsed_data['type'],
                                                       parsedFloData=json.dumps(parsed_data)
                                                       ))
                session.commit()
                session.close()
                pushData_SSEapi(f"Error | Token transfer at transaction {transaction_data['txid']} rejected as a token with the name {parsed_data['tokenIdentification']} doesnt not exist")
                return 0

        # todo Rule 46 - If the transfer type is smart contract, then call the function transferToken to do sanity checks & lock the balance
        elif parsed_data['transferType'] == 'smartContract':
            if check_database_existence('smart_contract', {'contract_name':f"{parsed_data['contractName']}", 'contract_address':f"{outputlist[0]}"}):
                # Check if the transaction hash already exists in the contract db (Safety check)
                connection = create_database_connection('smart_contract', {'contract_name':f"{parsed_data['contractName']}", 'contract_address':f"{outputlist[0]}"}, echo=True)
                participantAdd_txhash = connection.execute('select participantAddress, transactionHash from contractparticipants').fetchall()
                participantAdd_txhash_T = list(zip(*participantAdd_txhash))

                if len(participantAdd_txhash) != 0 and transaction_data['txid'] in list(participantAdd_txhash_T[1]):
                    logger.warning(f"Transaction {transaction_data['txid']} rejected as it already exists in the Smart Contract db. This is unusual, please check your code")
                    pushData_SSEapi(f"Error | Transaction {transaction_data['txid']} rejected as it already exists in the Smart Contract db. This is unusual, please check your code")
                    return 0

                # if contractAddress was passed, then check if it matches the output address of this contract
                if 'contractAddress' in parsed_data:
                    if parsed_data['contractAddress'] != outputlist[0]:
                        logger.info(f"Contract participation at transaction {transaction_data['txid']} rejected as contractAddress specified in flodata, {parsed_data['contractAddress']}, doesnt not match with transaction's output address {outputlist[0]}")
                        # Store transfer as part of RejectedContractTransactionHistory
                        session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                        blockchainReference = neturl + 'tx/' + transaction_data['txid']
                        session.add(RejectedContractTransactionHistory(transactionType='participation',
                                                               contractName=parsed_data['contractName'],
                                                               contractAddress=outputlist[0],
                                                               sourceFloAddress=inputadd,
                                                               destFloAddress=outputlist[0],
                                                               transferAmount=None,
                                                               blockNumber=transaction_data['blockheight'],
                                                               blockHash=transaction_data['blockhash'],
                                                               time=transaction_data['blocktime'],
                                                               transactionHash=transaction_data['txid'],
                                                               blockchainReference=blockchainReference,
                                                               jsonData=json.dumps(transaction_data),
                                                               rejectComment=f"Contract participation at transaction {transaction_data['txid']} rejected as contractAddress specified in flodata, {parsed_data['contractAddress']}, doesnt not match with transaction's output address {outputlist[0]}",
                                                               parsedFloData=json.dumps(parsed_data)))
                        session.commit()
                        session.close()

                        headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
                        '''r = requests.post(tokenapi_sse_url, json={'message': f"Error | Contract participation at transaction {transaction_data['txid']} rejected as contractAddress specified in flodata, {parsed_data['contractAddress']}, doesnt not match with transaction's output address {outputlist[0]}"},
                                          headers=headers)'''

                        # Pass information to SSE channel
                        pushData_SSEapi('Error| Mismatch in contract address specified in flodata and the output address of the transaction {}'.format(transaction_data['txid']))
                        return 0

                # check the status of the contract
                connection = create_database_connection('system_dbs', {'db_name':'system'})
                contractStatus = connection.execute(f"select status from activecontracts where contractName=='{parsed_data['contractName']}' and contractAddress='{outputlist[0]}'").fetchall()[0][0]
                connection.close()
                contractList = []

                if contractStatus == 'closed':
                    logger.info(f"Transaction {transaction_data['txid']} closed as Smart contract {parsed_data['contractName']} at the {outputlist[0]} is closed")
                    # Store transfer as part of RejectedContractTransactionHistory
                    session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                    blockchainReference = neturl + 'tx/' + transaction_data['txid']
                    session.add(RejectedContractTransactionHistory(transactionType='participation',
                                                           contractName=parsed_data['contractName'],
                                                           contractAddress=outputlist[0],
                                                           sourceFloAddress=inputadd,
                                                           destFloAddress=outputlist[0],
                                                           transferAmount=None,
                                                           blockNumber=transaction_data['blockheight'],
                                                           blockHash=transaction_data['blockhash'],
                                                           time=transaction_data['blocktime'],
                                                           transactionHash=transaction_data['txid'],
                                                           blockchainReference=blockchainReference,
                                                           jsonData=json.dumps(transaction_data),
                                                           rejectComment=f"Transaction {transaction_data['txid']} closed as Smart contract {parsed_data['contractName']} at the {outputlist[0]} is closed",

                                                           parsedFloData=json.dumps(parsed_data)
                                                           ))
                    session.commit()
                    session.close()

                    headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
                    '''r = requests.post(tokenapi_sse_url, json={'message': f"Error | Transaction {transaction_data['txid']} closed as Smart contract {parsed_data['contractName']} at the {outputlist[0]} is closed"},
                                      headers=headers)'''
                    return 0
                else:
                    session = create_database_session_orm('smart_contract', {'contract_name': f"{parsed_data['contractName']}", 'contract_address': f"{outputlist[0]}"}, ContractBase)
                    result = session.query(ContractStructure).filter_by(attribute='expiryTime').all()
                    session.close()
                    if result:
                        # now parse the expiry time in python
                        expirytime = result[0].value.strip()
                        expirytime_split = expirytime.split(' ')
                        parse_string = '{}/{}/{} {}'.format(expirytime_split[3], parsing.months[expirytime_split[1]],
                                                            expirytime_split[2], expirytime_split[4])
                        expirytime_object = parsing.arrow.get(parse_string, 'YYYY/M/D HH:mm:ss').replace(
                            tzinfo=expirytime_split[5][3:])
                        blocktime_object = parsing.arrow.get(transaction_data['blocktime']).to('Asia/Kolkata')

                        if blocktime_object > expirytime_object:
                            logger.info(
                                f"Transaction {transaction_data['txid']} rejected as Smart contract {parsed_data['contractName']}-{outputlist[0]} has expired and will not accept any user participation")
                            # Store transfer as part of RejectedContractTransactionHistory
                            session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                            blockchainReference = neturl + 'tx/' + transaction_data['txid']
                            session.add(RejectedContractTransactionHistory(transactionType='participation',
                                                                   contractName=parsed_data['contractName'],
                                                                   contractAddress=outputlist[0],
                                                                   sourceFloAddress=inputadd,
                                                                   destFloAddress=outputlist[0],
                                                                   transferAmount=None,
                                                                   blockNumber=transaction_data['blockheight'],
                                                                   blockHash=transaction_data['blockhash'],
                                                                   time=transaction_data['blocktime'],
                                                                   transactionHash=transaction_data['txid'],
                                                                   blockchainReference=blockchainReference,
                                                                   jsonData=json.dumps(transaction_data),
                                                                   rejectComment=f"Transaction {transaction_data['txid']} rejected as Smart contract {parsed_data['contractName']}-{outputlist[0]} has expired and will not accept any user participation",
                                                                   parsedFloData=json.dumps(parsed_data)
                                                                   ))
                            session.commit()
                            session.close()
                            pushData_SSEapi(
                                f"Error| Transaction {transaction_data['txid']} rejected as Smart contract {parsed_data['contractName']}-{outputlist[0]} has expired and will not accept any user participation")
                            return 0

                # pull out the contract structure into a dictionary
                connection = create_database_connection('smart_contract', {'contract_name':f"{parsed_data['contractName']}", 'contract_address':f"{outputlist[0]}"})
                attributevaluepair = connection.execute("select attribute, value from contractstructure where attribute != 'contractName' and attribute != 'flodata' and attribute != 'contractAddress'").fetchall()
                contractStructure = {}
                conditionDict = {}
                counter = 0
                for item in attributevaluepair:
                    if list(item)[0] == 'exitconditions':
                        conditionDict[counter] = list(item)[1]
                        counter = counter + 1
                    else:
                        contractStructure[list(item)[0]] = list(item)[1]
                if len(conditionDict) > 0:
                    contractStructure['exitconditions'] = conditionDict
                del counter, conditionDict

                # check if user choice has been passed, to the wrong contract type
                if 'userChoice' in parsed_data and 'exitconditions' not in contractStructure:
                    logger.info(
                        f"Transaction {transaction_data['txid']} rejected as userChoice, {parsed_data['userChoice']}, has been passed to Smart Contract named {parsed_data['contractName']} at the address {outputlist[0]} which doesn't accept any userChoice")
                    # Store transfer as part of RejectedContractTransactionHistory
                    session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                    blockchainReference = neturl + 'tx/' + transaction_data['txid']
                    session.add(
                        RejectedContractTransactionHistory(transactionType='participation',
                                                           contractName=parsed_data['contractName'],
                                                           contractAddress=outputlist[0],
                                                           sourceFloAddress=inputadd,
                                                           destFloAddress=outputlist[0],
                                                           transferAmount=None,
                                                           blockNumber=transaction_data['blockheight'],
                                                           blockHash=transaction_data['blockhash'],
                                                           time=transaction_data['blocktime'],
                                                           transactionHash=transaction_data['txid'],
                                                           blockchainReference=blockchainReference,
                                                           jsonData=json.dumps(transaction_data),
                                                           rejectComment=f"Transaction {transaction_data['txid']} rejected as userChoice, {parsed_data['userChoice']}, has been passed to Smart Contract named {parsed_data['contractName']} at the address {outputlist[0]} which doesn't accept any userChoice",

                                                           parsedFloData=json.dumps(parsed_data)
                                                           ))
                    session.commit()
                    session.close()
                    pushData_SSEapi(
                        f"Error | Transaction {transaction_data['txid']} rejected as userChoice, {parsed_data['userChoice']}, has been passed to Smart Contract named {parsed_data['contractName']} at the address {outputlist[0]} which doesn't accept any userChoice")
                    return 0

                # check if the right token is being sent for participation
                if parsed_data['tokenIdentification'] != contractStructure['tokenIdentification']:
                    logger.info(
                        f"Transaction {transaction_data['txid']} rejected as the token being transferred, {parsed_data['tokenIdentidication'].upper()}, is not part of the structure of Smart Contract named {parsed_data['contractName']} at the address {outputlist[0]}")
                    # Store transfer as part of RejectedContractTransactionHistory
                    session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                    blockchainReference = neturl + 'tx/' + transaction_data['txid']
                    session.add(
                        RejectedContractTransactionHistory(transactionType='participation',
                                                           contractName=parsed_data['contractName'],
                                                           contractAddress=outputlist[0],
                                                           sourceFloAddress=inputadd,
                                                           destFloAddress=outputlist[0],
                                                           transferAmount=None,
                                                           blockNumber=transaction_data['blockheight'],
                                                           blockHash=transaction_data['blockhash'],
                                                           time=transaction_data['blocktime'],
                                                           transactionHash=transaction_data['txid'],
                                                           blockchainReference=blockchainReference,
                                                           jsonData=json.dumps(transaction_data),
                                                           rejectComment=f"Transaction {transaction_data['txid']} rejected as the token being transferred, {parsed_data['tokenIdentidication'].upper()}, is not part of the structure of Smart Contract named {parsed_data['contractName']} at the address {outputlist[0]}",

                                                           parsedFloData=json.dumps(parsed_data)
                                                           ))
                    session.commit()
                    session.close()
                    pushData_SSEapi(
                        f"Error| Transaction {transaction_data['txid']} rejected as the token being transferred, {parsed_data['tokenIdentidication'].upper()}, is not part of the structure of Smart Contract named {parsed_data['contractName']} at the address {outputlist[0]}")
                    return 0

                # Check if the contract is of the type one-time-event
                if contractStructure['contractType'] == 'one-time-event':
                    # Check if contractAmount is part of the contract structure, and enforce it if it is
                    if 'contractAmount' in contractStructure:
                        if float(contractStructure['contractAmount']) != float(parsed_data['tokenAmount']):
                            logger.info(
                                f"Transaction {transaction_data['txid']} rejected as contractAmount being transferred is not part of the structure of Smart Contract named {parsed_data['contractName']} at the address {outputlist[0]}")
                            # Store transfer as part of RejectedContractTransactionHistory
                            session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                            blockchainReference = neturl + 'tx/' + transaction_data['txid']
                            session.add(
                                RejectedContractTransactionHistory(transactionType='participation',
                                                                   contractName=parsed_data['contractName'],
                                                                   contractAddress=outputlist[0],
                                                                   sourceFloAddress=inputadd,
                                                                   destFloAddress=outputlist[0],
                                                                   transferAmount=None,
                                                                   blockNumber=transaction_data['blockheight'],
                                                                   blockHash=transaction_data['blockhash'],
                                                                   time=transaction_data['blocktime'],
                                                                   transactionHash=transaction_data['txid'],
                                                                   blockchainReference=blockchainReference,
                                                                   jsonData=json.dumps(transaction_data),
                                                                   rejectComment=f"Transaction {transaction_data['txid']} rejected as contractAmount being transferred is not part of the structure of Smart Contract named {parsed_data['contractName']} at the address {outputlist[0]}",

                                                                   parsedFloData=json.dumps(parsed_data)
                                                                   ))
                            session.commit()
                            session.close()
                            pushData_SSEapi(
                                f"Error| Transaction {transaction_data['txid']} rejected as contractAmount being transferred is not part of the structure of Smart Contract named {parsed_data['contractName']} at the address {outputlist[0]}")
                            return 0

                    partialTransferCounter = 0
                    # Check if maximum subscription amount has reached
                    if 'maximumsubscriptionamount' in contractStructure:
                        # now parse the expiry time in python
                        maximumsubscriptionamount = float(contractStructure['maximumsubscriptionamount'])
                        session = create_database_session_orm('smart_contract', {'contract_name': f"{parsed_data['contractName']}", 'contract_address': f"{outputlist[0]}"}, ContractBase)
                        amountDeposited = session.query(func.sum(ContractParticipants.tokenAmount)).all()[0][0]
                        session.close()

                        if amountDeposited is None:
                            amountDeposited = 0

                        if amountDeposited >= maximumsubscriptionamount:
                            logger.info(
                                f"Transaction {transaction_data['txid']} rejected as maximum subscription amount has been reached for the Smart contract named {parsed_data['contractName']} at the address {outputlist[0]}")
                            # Store transfer as part of RejectedContractTransactionHistory
                            session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                            blockchainReference = neturl + 'tx/' + transaction_data['txid']
                            session.add(
                                RejectedContractTransactionHistory(transactionType='participation',
                                                                   contractName=parsed_data['contractName'],
                                                                   contractAddress=outputlist[0],
                                                                   sourceFloAddress=inputadd,
                                                                   destFloAddress=outputlist[0],
                                                                   transferAmount=None,
                                                                   blockNumber=transaction_data['blockheight'],
                                                                   blockHash=transaction_data['blockhash'],
                                                                   time=transaction_data['blocktime'],
                                                                   transactionHash=transaction_data['txid'],
                                                                   blockchainReference=blockchainReference,
                                                                   jsonData=json.dumps(transaction_data),
                                                                   rejectComment=f"Transaction {transaction_data['txid']} rejected as maximum subscription amount has been reached for the Smart contract named {parsed_data['contractName']} at the address {outputlist[0]}",

                                                                   parsedFloData=json.dumps(parsed_data)
                                                                   ))
                            session.commit()
                            session.close()
                            pushData_SSEapi(
                                f"Error | Transaction {transaction_data['txid']} rejected as maximum subscription amount has been reached for the Smart contract named {parsed_data['contractName']} at the address {outputlist[0]}")
                            return 0
                        elif ((float(amountDeposited) + float(parsed_data[
                                                                  'tokenAmount'])) > maximumsubscriptionamount) and 'contractAmount' in contractStructure:
                            logger.info(
                                f"Transaction {transaction_data['txid']} rejected as the contractAmount surpasses the maximum subscription amount, {contractStructure['maximumsubscriptionamount']} {contractStructure['tokenIdentification'].upper()}, for the Smart contract named {parsed_data['contractName']} at the address {outputlist[0]}")
                            # Store transfer as part of RejectedContractTransactionHistory
                            session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                            blockchainReference = neturl + 'tx/' + transaction_data['txid']
                            session.add(
                                RejectedContractTransactionHistory(transactionType='participation',
                                                                   contractName=parsed_data['contractName'],
                                                                   contractAddress=outputlist[0],
                                                                   sourceFloAddress=inputadd,
                                                                   destFloAddress=outputlist[0],
                                                                   transferAmount=None,
                                                                   blockNumber=transaction_data['blockheight'],
                                                                   blockHash=transaction_data['blockhash'],
                                                                   time=transaction_data['blocktime'],
                                                                   transactionHash=transaction_data['txid'],
                                                                   blockchainReference=blockchainReference,
                                                                   jsonData=json.dumps(transaction_data),
                                                                   rejectComment=f"Transaction {transaction_data['txid']} rejected as the contractAmount surpasses the maximum subscription amount, {contractStructure['maximumsubscriptionamount']} {contractStructure['tokenIdentification'].upper()}, for the Smart contract named {parsed_data['contractName']} at the address {outputlist[0]}",

                                                                   parsedFloData=json.dumps(parsed_data)
                                                                   ))
                            session.commit()
                            session.close()
                            pushData_SSEapi(
                                f"Error | Transaction {transaction_data['txid']} rejected as the contractAmount surpasses the maximum subscription amount, {contractStructure['maximumsubscriptionamount']} {contractStructure['tokenIdentification'].upper()}, for the Smart contract named {parsed_data['contractName']} at the address {outputlist[0]}")
                            return 0
                        else:
                            partialTransferCounter = 1

                    # Check if exitcondition exists as part of contractstructure and is given in right format
                    if 'exitconditions' in contractStructure:
                        # This means the contract has an external trigger, ie. trigger coming from the contract committee
                        exitconditionsList = []
                        for condition in contractStructure['exitconditions']:
                            exitconditionsList.append(contractStructure['exitconditions'][condition])

                        if parsed_data['userChoice'] in exitconditionsList:
                            if partialTransferCounter == 0:
                                # Check if the tokenAmount being transferred exists in the address & do the token transfer
                                returnval = transferToken(parsed_data['tokenIdentification'],
                                                          parsed_data['tokenAmount'], inputlist[0], outputlist[0],
                                                          transaction_data, parsed_data)
                                if returnval is not None:
                                    # Store participant details in the smart contract's db
                                    session.add(ContractParticipants(participantAddress=inputadd,
                                                                     tokenAmount=parsed_data['tokenAmount'],
                                                                     userChoice=parsed_data['userChoice'],
                                                                     transactionHash=transaction_data['txid'],
                                                                     blockNumber=transaction_data['blockheight'],
                                                                     blockHash=transaction_data['blockhash']))
                                    session.commit()

                                    # Store transfer as part of ContractTransactionHistory
                                    blockchainReference = neturl + 'tx/' + transaction_data['txid']
                                    session.add(ContractTransactionHistory(transactionType='participation',
                                                                           sourceFloAddress=inputadd,
                                                                           destFloAddress=outputlist[0],
                                                                           transferAmount=parsed_data['tokenAmount'],
                                                                           blockNumber=transaction_data['blockheight'],
                                                                           blockHash=transaction_data['blockhash'],
                                                                           time=transaction_data['blocktime'],
                                                                           transactionHash=transaction_data['txid'],
                                                                           blockchainReference=blockchainReference,
                                                                           jsonData=json.dumps(transaction_data),
                                                                           parsedFloData=json.dumps(parsed_data)
                                                                           ))

                                    session.commit()
                                    session.close()

                                    # Store a mapping of participant address -> Contract participated in
                                    session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                                    session.add(ContractAddressMapping(address=inputadd, addressType='participant',
                                                                       tokenAmount=parsed_data['tokenAmount'],
                                                                       contractName=parsed_data['contractName'],
                                                                       contractAddress=outputlist[0],
                                                                       transactionHash=transaction_data['txid'],
                                                                       blockNumber=transaction_data['blockheight'],
                                                                       blockHash=transaction_data['blockhash']))
                                    session.commit()

                                    # If this is the first interaction of the outputlist's address with the given token name, add it to token mapping
                                    connection = create_database_connection('system_dbs', {'db_name':'system'})
                                    firstInteractionCheck = connection.execute(
                                        f"select * from tokenAddressMapping where tokenAddress='{outputlist[0]}' and token='{parsed_data['tokenIdentification']}'").fetchall()

                                    if len(firstInteractionCheck) == 0:
                                        connection.execute(
                                            f"INSERT INTO tokenAddressMapping (tokenAddress, token, transactionHash, blockNumber, blockHash) VALUES ('{outputlist[0]}', '{parsed_data['tokenIdentification']}', '{transaction_data['txid']}', '{transaction_data['blockheight']}', '{transaction_data['blockhash']}')")

                                    connection.close()

                                    updateLatestTransaction(transaction_data, parsed_data)
                                    return 1

                                else:
                                    logger.info("Something went wrong in the smartcontract token transfer method")
                                    return 0
                            elif partialTransferCounter == 1:
                                # Transfer only part of the tokens users specified, till the time it reaches maximumamount
                                returnval = transferToken(parsed_data['tokenIdentification'],
                                                          maximumsubscriptionamount - amountDeposited,
                                                          inputlist[0], outputlist[0], transaction_data, parsed_data)
                                if returnval is not None:
                                    # Store participant details in the smart contract's db
                                    session.add(ContractParticipants(participantAddress=inputadd,
                                                                     tokenAmount=maximumsubscriptionamount - amountDeposited,
                                                                     userChoice=parsed_data['userChoice'],
                                                                     transactionHash=transaction_data['txid'],
                                                                     blockNumber=transaction_data['blockheight'],
                                                                     blockHash=transaction_data['blockhash']))
                                    session.commit()
                                    session.close()

                                    # Store a mapping of participant address -> Contract participated in
                                    session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                                    session.add(ContractAddressMapping(address=inputadd, addressType='participant',
                                                                       tokenAmount=maximumsubscriptionamount - amountDeposited,
                                                                       contractName=parsed_data['contractName'],
                                                                       contractAddress=outputlist[0],
                                                                       transactionHash=transaction_data['txid'],
                                                                       blockNumber=transaction_data['blockheight'],
                                                                       blockHash=transaction_data['blockhash']))
                                    session.commit()
                                    session.close()
                                    updateLatestTransaction(transaction_data, parsed_data)
                                    return 1

                                else:
                                    logger.info("Something went wrong in the smartcontract token transfer method")
                                    return 0

                        else:
                            logger.info(f"Transaction {transaction_data['txid']} rejected as wrong userchoice entered for the Smart Contract named {parsed_data['contractName']} at the address {outputlist[0]}")
                            # Store transfer as part of RejectedContractTransactionHistory
                            session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                            blockchainReference = neturl + 'tx/' + transaction_data['txid']
                            session.add(RejectedContractTransactionHistory(transactionType='participation',
                                                                   contractName=parsed_data['contractName'],
                                                                   contractAddress=outputlist[0],
                                                                   sourceFloAddress=inputadd,
                                                                   destFloAddress=outputlist[0],
                                                                   transferAmount=None,
                                                                   blockNumber=transaction_data['blockheight'],
                                                                   blockHash=transaction_data['blockhash'],
                                                                   time=transaction_data['blocktime'],
                                                                   transactionHash=transaction_data['txid'],
                                                                   blockchainReference=blockchainReference,
                                                                   jsonData=json.dumps(transaction_data),
                                                                   rejectComment=f"Transaction {transaction_data['txid']} rejected as wrong userchoice entered for the Smart Contract named {parsed_data['contractName']} at the address {outputlist[0]}",
                                                                   parsedFloData=json.dumps(parsed_data)
                                                                   ))
                            session.commit()
                            session.close()
                            pushData_SSEapi(
                                f"Error| Transaction {transaction_data['txid']} rejected as wrong userchoice entered for the Smart Contract named {parsed_data['contractName']} at the address {outputlist[0]}")
                            return 0

                    elif 'payeeAddress' in contractStructure:
                        # this means the contract if of the type internal trigger
                        if partialTransferCounter == 0:
                            # Check if the tokenAmount being transferred exists in the address & do the token transfer
                            returnval = transferToken(parsed_data['tokenIdentification'],
                                                      parsed_data['tokenAmount'], inputlist[0], outputlist[0],
                                                      transaction_data, parsed_data)
                            if returnval is not None:
                                # Store participant details in the smart contract's db
                                session.add(ContractParticipants(participantAddress=inputadd,
                                                                 tokenAmount=parsed_data['tokenAmount'],
                                                                 userChoice='-',
                                                                 transactionHash=transaction_data['txid'],
                                                                 blockNumber=transaction_data['blockheight'],
                                                                 blockHash=transaction_data['blockhash']))
                                session.commit()

                                # Store transfer as part of ContractTransactionHistory
                                blockchainReference = neturl + 'tx/' + transaction_data['txid']
                                session.add(ContractTransactionHistory(transactionType='participation',
                                                                       sourceFloAddress=inputadd,
                                                                       destFloAddress=outputlist[0],
                                                                       transferAmount=parsed_data['tokenAmount'],
                                                                       blockNumber=transaction_data['blockheight'],
                                                                       blockHash=transaction_data['blockhash'],
                                                                       time=transaction_data['blocktime'],
                                                                       transactionHash=transaction_data['txid'],
                                                                       blockchainReference=blockchainReference,
                                                                       jsonData=json.dumps(transaction_data),

                                                                       parsedFloData=json.dumps(parsed_data)
                                                                       ))

                                session.commit()
                                session.close()

                                # Store a mapping of participant address -> Contract participated in
                                session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                                session.add(ContractAddressMapping(address=inputadd, addressType='participant',
                                                                   tokenAmount=parsed_data['tokenAmount'],
                                                                   contractName=parsed_data['contractName'],
                                                                   contractAddress=outputlist[0],
                                                                   transactionHash=transaction_data['txid'],
                                                                   blockNumber=transaction_data['blockheight'],
                                                                   blockHash=transaction_data['blockhash']))
                                session.commit()

                                updateLatestTransaction(transaction_data, parsed_data)
                                return 1

                            else:
                                logger.info("Something went wrong in the smartcontract token transfer method")
                                return 0
                        elif partialTransferCounter == 1:
                            # Transfer only part of the tokens users specified, till the time it reaches maximumamount
                            returnval = transferToken(parsed_data['tokenIdentification'],
                                                      maximumsubscriptionamount - amountDeposited,
                                                      inputlist[0], outputlist[0], transaction_data, parsed_data)
                            if returnval is not None:
                                # Store participant details in the smart contract's db
                                session.add(ContractParticipants(participantAddress=inputadd,
                                                                 tokenAmount=maximumsubscriptionamount - amountDeposited,
                                                                 userChoice='-',
                                                                 transactionHash=transaction_data['txid'],
                                                                 blockNumber=transaction_data['blockheight'],
                                                                 blockHash=transaction_data['blockhash']))
                                session.commit()
                                session.close()

                                # Store a mapping of participant address -> Contract participated in
                                session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                                session.add(ContractAddressMapping(address=inputadd, addressType='participant',
                                                                   tokenAmount=maximumsubscriptionamount - amountDeposited,
                                                                   contractName=parsed_data['contractName'],
                                                                   contractAddress=outputlist[0],
                                                                   transactionHash=transaction_data['txid'],
                                                                   blockNumber=transaction_data['blockheight'],
                                                                   blockHash=transaction_data['blockhash']))
                                session.commit()
                                session.close()
                                updateLatestTransaction(transaction_data, parsed_data)
                                return 1

                            else:
                                logger.info("Something went wrong in the smartcontract token transfer method")
                                return 0

                else:
                    logger.info(
                        f"Transaction {transaction_data['txid']} rejected as the participation doesn't belong to any valid contract type")
                    # Store transfer as part of RejectedContractTransactionHistory
                    session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                    blockchainReference = neturl + 'tx/' + transaction_data['txid']
                    session.add(
                        RejectedContractTransactionHistory(transactionType='participation',
                                                           contractName=parsed_data['contractName'],
                                                           contractAddress=outputlist[0],
                                                           sourceFloAddress=inputadd,
                                                           destFloAddress=outputlist[0],
                                                           transferAmount=None,
                                                           blockNumber=transaction_data['blockheight'],
                                                           blockHash=transaction_data['blockhash'],
                                                           time=transaction_data['blocktime'],
                                                           transactionHash=transaction_data['txid'],
                                                           blockchainReference=blockchainReference,
                                                           jsonData=json.dumps(transaction_data),
                                                           rejectComment=f"Transaction {transaction_data['txid']} rejected as the participation doesn't belong to any valid contract type",

                                                           parsedFloData=json.dumps(parsed_data)
                                                           ))
                    session.commit()
                    session.close()

                    headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
                    '''r = requests.post(tokenapi_sse_url, json={'message': f"Error | Transaction {transaction_data['txid']} rejected as the participation doesn't belong to any valid contract type"}, headers=headers)'''
                    return 0

            else:
                logger.info(f"Transaction {transaction_data['txid']} rejected as a Smart Contract with the name {parsed_data['contractName']} at address {outputlist[0]} doesnt exist")
                # Store transfer as part of RejectedContractTransactionHistory
                session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                blockchainReference = neturl + 'tx/' + transaction_data['txid']
                session.add(RejectedContractTransactionHistory(transactionType='participation',
                                                       contractName=parsed_data['contractName'],
                                                       contractAddress=outputlist[0],
                                                       sourceFloAddress=inputadd,
                                                       destFloAddress=outputlist[0],
                                                       transferAmount=None,
                                                       blockNumber=transaction_data['blockheight'],
                                                       blockHash=transaction_data['blockhash'],
                                                       time=transaction_data['blocktime'],
                                                       transactionHash=transaction_data['txid'],
                                                       blockchainReference=blockchainReference,
                                                       jsonData=json.dumps(transaction_data),
                                                       rejectComment=f"Transaction {transaction_data['txid']} rejected as a Smart Contract with the name {parsed_data['contractName']} at address {outputlist[0]} doesnt exist",

                                                       parsedFloData=json.dumps(parsed_data)
                                                       ))
                session.commit()
                session.close()

                headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
                '''r = requests.post(tokenapi_sse_url, json={'message': f"Error | Contract transaction {transaction_data['txid']} rejected as a smartcontract with same name {parsed_data['contractName']}-{parsed_data['contractAddress']} dosent exist "}, headers=headers)'''
                return 0

        elif parsed_data['transferType'] == 'swapParticipaton':
            if check_database_existence('smart_contract', {'contract_name':f"{parsed_data['contractName']}", 'contract_address':f"{outputlist[0]}"}):
                # Check if the transaction hash already exists in the contract db (Safety check)
                connection = create_database_connection('smart_contract', {'contract_name':f"{parsed_data['contractName']}", 'contract_address':f"{outputlist[0]}"})
                participantAdd_txhash = connection.execute('select participantAddress, transactionHash from contractparticipants').fetchall()
                participantAdd_txhash_T = list(zip(*participantAdd_txhash))

                # if contractAddress was passed, then check if it matches the output address of this contract
                if 'contractAddress' in parsed_data:
                    if parsed_data['contractAddress'] != outputlist[0]:
                        logger.info(f"Contract participation at transaction {transaction_data['txid']} rejected as contractAddress specified in flodata, {parsed_data['contractAddress']}, doesnt not match with transaction's output address {outputlist[0]}")
                        # Store transfer as part of RejectedContractTransactionHistory
                        session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                        blockchainReference = neturl + 'tx/' + transaction_data['txid']
                        session.add(RejectedContractTransactionHistory(transactionType='participation',
                                                               contractName=parsed_data['contractName'],
                                                               contractAddress=outputlist[0],
                                                               sourceFloAddress=inputadd,
                                                               destFloAddress=outputlist[0],
                                                               transferAmount=None,
                                                               blockNumber=transaction_data['blockheight'],
                                                               blockHash=transaction_data['blockhash'],
                                                               time=transaction_data['blocktime'],
                                                               transactionHash=transaction_data['txid'],
                                                               blockchainReference=blockchainReference,
                                                               jsonData=json.dumps(transaction_data),
                                                               rejectComment=f"Contract participation at transaction {transaction_data['txid']} rejected as contractAddress specified in flodata, {parsed_data['contractAddress']}, doesnt not match with transaction's output address {outputlist[0]}",

                                                               parsedFloData=json.dumps(parsed_data)))
                        session.commit()
                        session.close()

                        headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
                        '''r = requests.post(tokenapi_sse_url, json={'message': f"Error | Contract participation at transaction {transaction_data['txid']} rejected as contractAddress specified in flodata, {parsed_data['contractAddress']}, doesnt not match with transaction's output address {outputlist[0]}"},
                                          headers=headers)'''

                        # Pass information to SSE channel
                        pushData_SSEapi('Error| Mismatch in contract address specified in flodata and the output address of the transaction {}'.format(transaction_data['txid']))
                        return 0

                # pull out the contract structure into a dictionary
                connection = create_database_connection('smart_contract', {'contract_name':f"{parsed_data['contractName']}", 'contract_address':f"{outputlist[0]}"})
                attributevaluepair = connection.execute("select attribute, value from contractstructure where attribute != 'contractName' and attribute != 'flodata' and attribute != 'contractAddress'").fetchall()
                contractStructure = {}
                conditionDict = {}
                counter = 0
                del counter, conditionDict

                if contractStructure['priceType'] == 'predetermined':
                    swapPrice = contractStructure['price']
                elif contractStructure['priceType'] == 'dynamic':
                    pass
                                
                returnval = transferToken(contractStructure['accepting_token'], swapPrice, inputlist[0],outputlist[0], transaction_data, parsed_data)
                if returnval is None:
                    logger.info("Something went wrong in the token transfer method")
                    pushData_SSEapi(f"Error | Something went wrong while doing the internal db transactions for {transaction_data['txid']}")
                    return 0
                else:
                    updateLatestTransaction(transaction_data, parsed_data)

                # If this is the first interaction of the outputlist's address with the given token name, add it to token mapping
                connection = create_database_connection('system_dbs', {'db_name':'system'})
                firstInteractionCheck = connection.execute(f"select * from tokenAddressMapping where tokenAddress='{outputlist[0]}' and token='{parsed_data['tokenIdentification']}'").fetchall()

                if len(firstInteractionCheck) == 0:
                    connection.execute(f"INSERT INTO tokenAddressMapping (tokenAddress, token, transactionHash, blockNumber, blockHash) VALUES ('{outputlist[0]}', '{parsed_data['tokenIdentification']}', '{transaction_data['txid']}', '{transaction_data['blockheight']}', '{transaction_data['blockhash']}')")

                connection.close()

                # Pass information to SSE channel
                headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
                # r = requests.post(tokenapi_sse_url, json={f"message': 'Token Transfer | name:{parsed_data['tokenIdentification']} | transactionHash:{transaction_data['txid']}"}, headers=headers)

                returnval = transferToken(contractStructure['selling_token'], swapPrice, outputlist[0], inputlist[0], transaction_data, parsed_data)
                if returnval is None:
                    logger.info("Something went wrong in the token transfer method")
                    pushData_SSEapi(f"Error | Something went wrong while doing the internal db transactions for {transaction_data['txid']}")
                    return 0
                else:
                    updateLatestTransaction(transaction_data, parsed_data)
                
                # If this is the first interaction of the outputlist's address with the given token name, add it to token mapping
                connection = create_database_connection('system_dbs', {'db_name':'system'})
                firstInteractionCheck = connection.execute(f"select * from tokenAddressMapping where tokenAddress='{outputlist[0]}' and token='{parsed_data['tokenIdentification']}'").fetchall()

                if len(firstInteractionCheck) == 0:
                    connection.execute(f"INSERT INTO tokenAddressMapping (tokenAddress, token, transactionHash, blockNumber, blockHash) VALUES ('{outputlist[0]}', '{parsed_data['tokenIdentification']}', '{transaction_data['txid']}', '{transaction_data['blockheight']}', '{transaction_data['blockhash']}')")

                connection.close()

                # Push the Swap Participation transaction into contract database 
                session = create_database_session_orm('smart_contract', {'contract_name': f"{parsed_data['contractName']}", 'contract_address': f"{outputlist[0]}"}, ContinuosContractBase)
                blockchainReference = neturl + 'tx/' + transaction_data['txid']

                session.add(ContractParticipants1(participantAddress = inputadd,
                                                tokenAmount = swapPrice,
                                                transactionHash = transaction_data['txid'],
                                                blockNumber = transaction_data['blockheight'],
                                                blockHash = transaction_data['blockhash']
                                                ))
                session.add(ContractTransactionHistory1(transactionType = 'smartContractDeposit',
                                                        transactionSubType = None,
                                                        sourceFloAddress = inputadd,
                                                        destFloAddress = outputlist[0],
                                                        transferAmount = parsed_data['depositAmount'],
                                                        blockNumber = transaction_data['blockheight'],
                                                        blockHash = transaction_data['blockhash'],
                                                        time = transaction_data['blocktime'],
                                                        transactionHash = transaction_data['txid'],
                                                        blockchainReference = blockchainReference,
                                                        jsonData = json.dumps(transaction_data),
                                                        parsedFloData = json.dumps(parsed_data)
                                                        ))
                session.commit()
                session.close()
                pushData_SSEapi(f"Deposit Smart Contract Transaction {transaction_data['txid']} rejected as maximum subscription amount has been reached for the Smart contract named {parsed_data['contractName']} at the address {outputlist[0]}")
                return 0

                # Pass information to SSE channel
                headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
                # r = requests.post(tokenapi_sse_url, json={f"message': 'Token Transfer | name:{parsed_data['tokenIdentification']} | transactionHash:{transaction_data['txid']}"}, headers=headers)               

                return 1


            else:
                logger.info(f"Transaction {transaction_data['txid']} rejected as a Smart Contract with the name {parsed_data['contractName']} at address {outputlist[0]} doesnt exist")
                # Store transfer as part of RejectedContractTransactionHistory
                session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                blockchainReference = neturl + 'tx/' + transaction_data['txid']
                session.add(RejectedContractTransactionHistory(transactionType='participation',
                                                       contractName=parsed_data['contractName'],
                                                       contractAddress=outputlist[0],
                                                       sourceFloAddress=inputadd,
                                                       destFloAddress=outputlist[0],
                                                       transferAmount=None,
                                                       blockNumber=transaction_data['blockheight'],
                                                       blockHash=transaction_data['blockhash'],
                                                       time=transaction_data['blocktime'],
                                                       transactionHash=transaction_data['txid'],
                                                       blockchainReference=blockchainReference,
                                                       jsonData=json.dumps(transaction_data),
                                                       rejectComment=f"Transaction {transaction_data['txid']} rejected as a Smart Contract with the name {parsed_data['contractName']} at address {outputlist[0]} doesnt exist",
                                                       parsedFloData=json.dumps(parsed_data)
                                                       ))
                session.commit()
                session.close()

                headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
                '''r = requests.post(tokenapi_sse_url, json={
                    'message': f"Error | Contract transaction {transaction_data['txid']} rejected as a smartcontract with same name {parsed_data['contractName']}-{parsed_data['contractAddress']} dosent exist "},
                                  headers=headers)'''
                return 0

        elif parsed_data['transferType'] == 'nft':
            pass

    # todo Rule 47 - If the parsed data type is token incorporation, then check if the name hasn't been taken already
    #  if it has been taken then reject the incorporation. Else incorporate it
    elif parsed_data['type'] == 'tokenIncorporation':
        if not check_database_existence('token', {'token_name':f"{parsed_data['tokenIdentification']}"}):
            session = create_database_session_orm('token', {'token_name': f"{parsed_data['tokenIdentification']}"}, Base)
            session.add(ActiveTable(address=inputlist[0], parentid=0, transferBalance=parsed_data['tokenAmount']))
            session.add(TransferLogs(sourceFloAddress=inputadd, destFloAddress=outputlist[0],
                                     transferAmount=parsed_data['tokenAmount'], sourceId=0, destinationId=1,
                                     blockNumber=transaction_data['blockheight'], time=transaction_data['blocktime'],
                                     transactionHash=transaction_data['txid']))
            blockchainReference = neturl + 'tx/' + transaction_data['txid']
            session.add(TransactionHistory(sourceFloAddress=inputadd, destFloAddress=outputlist[0],
                                           transferAmount=parsed_data['tokenAmount'],
                                           blockNumber=transaction_data['blockheight'],
                                           blockHash=transaction_data['blockhash'],
                                           time=transaction_data['blocktime'],
                                           transactionHash=transaction_data['txid'],
                                           blockchainReference=blockchainReference,
                                           jsonData=json.dumps(transaction_data), transactionType=parsed_data['type'],
                                           parsedFloData=json.dumps(parsed_data)))
            session.commit()
            session.close()

            # add it to token address to token mapping db table
            connection = create_database_connection('system_dbs', {'db_name':'system'})
            connection.execute(f"INSERT INTO tokenAddressMapping (tokenAddress, token, transactionHash, blockNumber, blockHash) VALUES ('{inputadd}', '{parsed_data['tokenIdentification']}', '{transaction_data['txid']}', '{transaction_data['blockheight']}', '{transaction_data['blockhash']}');")
            connection.execute(f"INSERT INTO tokenAddressMapping (tokenAddress, token, transactionHash, blockNumber, blockHash) VALUES ('{inputadd}', '{parsed_data['tokenIdentification']}', '{transaction_data['txid']}', '{transaction_data['blockheight']}', '{transaction_data['blockhash']}');")
            connection.close()

            updateLatestTransaction(transaction_data, parsed_data)

            pushData_SSEapi(f"Token | Succesfully incorporated token {parsed_data['tokenIdentification']} at transaction {transaction_data['txid']}")
            return 1
        else:
            logger.info(f"Transaction {transaction_data['txid']} rejected as a token with the name {parsed_data['tokenIdentification']} has already been incorporated")
            session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
            blockchainReference = neturl + 'tx/' + transaction_data['txid']
            session.add(RejectedTransactionHistory(tokenIdentification=parsed_data['tokenIdentification'],
                                                   sourceFloAddress=inputadd, destFloAddress=outputlist[0],
                                                   transferAmount=parsed_data['tokenAmount'],
                                                   blockNumber=transaction_data['blockheight'],
                                                   blockHash=transaction_data['blockhash'],
                                                   time=transaction_data['blocktime'],
                                                   transactionHash=transaction_data['txid'],
                                                   blockchainReference=blockchainReference,
                                                   jsonData=json.dumps(transaction_data),
                                                   rejectComment=f"Transaction {transaction_data['txid']} rejected as a token with the name {parsed_data['tokenIdentification']} has already been incorporated",
                                                   transactionType=parsed_data['type'],
                                                   parsedFloData=json.dumps(parsed_data)
                                                   ))
            session.commit()
            session.close()
            pushData_SSEapi(f"Error | Token incorporation rejected at transaction {transaction_data['txid']} as token {parsed_data['tokenIdentification']} already exists")
            return 0

    # todo Rule 48 - If the parsed data type if smart contract incorporation, then check if the name hasn't been taken already
    #      if it has been taken then reject the incorporation.
    elif parsed_data['type'] == 'smartContractIncorporation':
        if not check_database_existence('smart_contract', {'contract_name':f"{parsed_data['contractName']}", 'contract_address':f"{parsed_data['contractAddress']}"}):
            # todo Rule 49 - If the contract name hasn't been taken before, check if the contract type is an authorized type by the system
            if parsed_data['contractType'] == 'one-time-event':
                logger.info("Smart contract is of the type one-time-event")

                # either userchoice or payeeAddress condition should be present. Check for it
                if 'userchoices' not in parsed_data['contractConditions'] and 'payeeAddress' not in parsed_data['contractConditions']:
                    logger.info(f"Either userchoice or payeeAddress should be part of the Contract conditions.\nSmart contract incorporation on transaction {transaction_data['txid']} rejected")
                    # Store transfer as part of RejectedContractTransactionHistory
                    session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                    blockchainReference = neturl + 'tx/' + transaction_data['txid']
                    session.add(
                        RejectedContractTransactionHistory(transactionType='incorporation',
                                                           contractName=parsed_data['contractName'],
                                                           contractAddress=outputlist[0],
                                                           sourceFloAddress=inputadd,
                                                           destFloAddress=outputlist[0],
                                                           transferAmount=None,
                                                           blockNumber=transaction_data['blockheight'],
                                                           blockHash=transaction_data['blockhash'],
                                                           time=transaction_data['blocktime'],
                                                           transactionHash=transaction_data['txid'],
                                                           blockchainReference=blockchainReference,
                                                           jsonData=json.dumps(transaction_data),
                                                           rejectComment=f"Either userchoice or payeeAddress should be part of the Contract conditions.\nSmart contract incorporation on transaction {transaction_data['txid']} rejected",

                                                           parsedFloData=json.dumps(parsed_data)
                                                           ))
                    session.commit()
                    session.close()
                    return 0

                # userchoice and payeeAddress conditions cannot come together. Check for it
                if 'userchoices' in parsed_data['contractConditions'] and 'payeeAddress' in parsed_data['contractConditions']:
                    logger.info(f"Both userchoice and payeeAddress provided as part of the Contract conditions.\nSmart contract incorporation on transaction {transaction_data['txid']} rejected")
                    # Store transfer as part of RejectedContractTransactionHistory 
                    session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                    blockchainReference = neturl + 'tx/' + transaction_data['txid']
                    session.add(RejectedContractTransactionHistory(transactionType='incorporation',
                                                           contractName=parsed_data['contractName'],
                                                           contractAddress=outputlist[0],
                                                           sourceFloAddress=inputadd,
                                                           destFloAddress=outputlist[0],
                                                           transferAmount=None,
                                                           blockNumber=transaction_data['blockheight'],
                                                           blockHash=transaction_data['blockhash'],
                                                           time=transaction_data['blocktime'],
                                                           transactionHash=transaction_data['txid'],
                                                           blockchainReference=blockchainReference,
                                                           jsonData=json.dumps(transaction_data),
                                                           rejectComment=f"Both userchoice and payeeAddress provided as part of the Contract conditions.\nSmart contract incorporation on transaction {transaction_data['txid']} rejected",

                                                           parsedFloData=json.dumps(parsed_data)
                                                           ))
                    session.commit()
                    session.close()
                    return 0

                # todo Rule 50 - Contract address mentioned in flodata field should be same as the receiver FLO address on the output side
                #    henceforth we will not consider any flo private key initiated comment as valid from this address
                #    Unlocking can only be done through smart contract system address
                if parsed_data['contractAddress'] == inputadd:
                    session = create_database_session_orm('smart_contract', {'contract_name': f"{parsed_data['contractName']}", 'contract_address': f"{parsed_data['contractAddress']}"}, ContractBase)
                    session.add(ContractStructure(attribute='contractType', index=0, value=parsed_data['contractType']))
                    session.add(ContractStructure(attribute='contractName', index=0, value=parsed_data['contractName']))
                    session.add(
                        ContractStructure(attribute='tokenIdentification', index=0,
                                          value=parsed_data['tokenIdentification']))
                    session.add(
                        ContractStructure(attribute='contractAddress', index=0, value=parsed_data['contractAddress']))
                    session.add(
                        ContractStructure(attribute='flodata', index=0,
                                          value=parsed_data['flodata']))
                    session.add(
                        ContractStructure(attribute='expiryTime', index=0,
                                          value=parsed_data['contractConditions']['expiryTime']))
                    if 'contractAmount' in parsed_data['contractConditions']:
                        session.add(
                            ContractStructure(attribute='contractAmount', index=0,
                                              value=parsed_data['contractConditions']['contractAmount']))

                    if 'minimumsubscriptionamount' in parsed_data['contractConditions']:
                        session.add(
                            ContractStructure(attribute='minimumsubscriptionamount', index=0,
                                              value=parsed_data['contractConditions']['minimumsubscriptionamount']))
                    if 'maximumsubscriptionamount' in parsed_data['contractConditions']:
                        session.add(
                            ContractStructure(attribute='maximumsubscriptionamount', index=0,
                                              value=parsed_data['contractConditions']['maximumsubscriptionamount']))
                    if 'userchoices' in parsed_data['contractConditions']:
                        for key, value in parsed_data['contractConditions']['userchoices'].items():
                            session.add(ContractStructure(attribute='exitconditions', index=key, value=value))

                    if 'payeeAddress' in parsed_data['contractConditions']:
                        # in this case, expirydate( or maximumamount) is the trigger internally. Keep a track of expiry dates
                        session.add(
                            ContractStructure(attribute='payeeAddress', index=0,
                                              value=parsed_data['contractConditions']['payeeAddress']))

                    session.commit()

                    # Store transfer as part of ContractTransactionHistory
                    blockchainReference = neturl + 'tx/' + transaction_data['txid']
                    session.add(ContractTransactionHistory(transactionType='incorporation', sourceFloAddress=inputadd,
                                                           destFloAddress=outputlist[0],
                                                           transferAmount=None,
                                                           blockNumber=transaction_data['blockheight'],
                                                           blockHash=transaction_data['blockhash'],
                                                           time=transaction_data['blocktime'],
                                                           transactionHash=transaction_data['txid'],
                                                           blockchainReference=blockchainReference,
                                                           jsonData=json.dumps(transaction_data),

                                                           parsedFloData=json.dumps(parsed_data)
                                                           ))
                    session.commit()
                    session.close()

                    # add Smart Contract name in token contract association
                    session = create_database_session_orm('token', {'token_name': f"{parsed_data['tokenIdentification']}"}, Base)
                    session.add(TokenContractAssociation(tokenIdentification=parsed_data['tokenIdentification'],
                                                         contractName=parsed_data['contractName'],
                                                         contractAddress=parsed_data['contractAddress'],
                                                         blockNumber=transaction_data['blockheight'],
                                                         blockHash=transaction_data['blockhash'],
                                                         time=transaction_data['blocktime'],
                                                         transactionHash=transaction_data['txid'],
                                                         blockchainReference=blockchainReference,
                                                         jsonData=json.dumps(transaction_data),
                                                         transactionType=parsed_data['type'],
                                                         parsedFloData=json.dumps(parsed_data)))
                    session.commit()
                    session.close()

                    # Store smart contract address in system's db, to be ignored during future transfers
                    session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                    session.add(ActiveContracts(contractName=parsed_data['contractName'],
                                                contractAddress=parsed_data['contractAddress'], status='active',
                                                tokenIdentification=parsed_data['tokenIdentification'],
                                                contractType=parsed_data['contractType'],
                                                transactionHash=transaction_data['txid'],
                                                blockNumber=transaction_data['blockheight'],
                                                blockHash=transaction_data['blockhash'],
                                                incorporationDate=transaction_data['blocktime']))
                    session.commit()

                    session.add(ContractAddressMapping(address=inputadd, addressType='incorporation',
                                                       tokenAmount=None,
                                                       contractName=parsed_data['contractName'],
                                                       contractAddress=inputadd,
                                                       transactionHash=transaction_data['txid'],
                                                       blockNumber=transaction_data['blockheight'],
                                                       blockHash=transaction_data['blockhash']))
                    session.commit()

                    session.close()

                    updateLatestTransaction(transaction_data, parsed_data)

                    pushData_SSEapi('Contract | Contract incorporated at transaction {} with name {}-{}'.format(
                        transaction_data['txid'], parsed_data['contractName'], parsed_data['contractAddress']))
                    return 1
                else:
                    logger.info(
                        f"Contract Incorporation on transaction {transaction_data['txid']} rejected as contract address in Flodata and input address are different")
                    # Store transfer as part of RejectedContractTransactionHistory
                    session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                    blockchainReference = neturl + 'tx/' + transaction_data['txid']
                    session.add(
                        RejectedContractTransactionHistory(transactionType='incorporation',
                                                           contractName=parsed_data['contractName'],
                                                           contractAddress=outputlist[0],
                                                           sourceFloAddress=inputadd,
                                                           destFloAddress=outputlist[0],
                                                           transferAmount=None,
                                                           blockNumber=transaction_data['blockheight'],
                                                           blockHash=transaction_data['blockhash'],
                                                           time=transaction_data['blocktime'],
                                                           transactionHash=transaction_data['txid'],
                                                           blockchainReference=blockchainReference,
                                                           jsonData=json.dumps(transaction_data),
                                                           rejectComment=f"Contract Incorporation on transaction {transaction_data['txid']} rejected as contract address in flodata and input address are different",

                                                           parsedFloData=json.dumps(parsed_data)
                                                           ))
                    session.commit()
                    session.close()
                    pushData_SSEapi(
                        'Error | Contract Incorporation rejected as address in Flodata and input address are different at transaction {}'.format(
                            transaction_data['txid']))
                    return 0
        
            if parsed_data['contractType'] == 'continuous-event':
                logger.debug("Smart contract is of the type continuous-event")
                # Add checks to reject the creation of contract
                if parsed_data['contractAddress'] == inputadd:
                    session = create_database_session_orm('smart_contract', {'contract_name': f"{parsed_data['contractName']}", 'contract_address': f"{parsed_data['contractAddress']}"}, ContinuosContractBase)
                    session.add(ContractStructure1(attribute='contractType', index=0, value=parsed_data['contractType']))
                    session.add(ContractStructure1(attribute='contractName', index=0, value=parsed_data['contractName']))
                    session.add(ContractStructure1(attribute='contractAddress', index=0, value=parsed_data['contractAddress']))
                    session.add(ContractStructure1(attribute='flodata', index=0, value=parsed_data['flodata']))
                    if 'subtype' in parsed_data['contractConditions']:
                        # todo: Check if the both the tokens mentioned exist if its a token swap
                        if (parsed_data['contractConditions']['subtype'] == 'tokenswap') and (check_database_existence('token', {'token_name':f"{parsed_data['contractConditions']['accepting_token'].split('#')[0]}"})) and (check_database_existence('token', {'token_name':f"{parsed_data['contractConditions']['selling_token'].split('#')[0]}"})):
                            #if (parsed_data['contractConditions']['subtype'] == 'tokenswap'):
                            if parsed_data['contractConditions']['priceType'] in ['predetermined','determined']:
                                session.add(ContractStructure1(attribute='subtype', index=0, value=parsed_data['contractConditions']['subtype'])) 
                                session.add(ContractStructure1(attribute='accepting_token', index=0, value=parsed_data['contractConditions']['accepting_token']))
                                session.add(ContractStructure1(attribute='selling_token', index=0, value=parsed_data['contractConditions']['selling_token']))
                                # determine price
                                session.add(ContractStructure1(attribute='priceType', index=0, value=parsed_data['contractConditions']['priceType']))
                                session.add(ContractStructure1(attribute='price', index=0, value=parsed_data['contractConditions']['price']))

                                
                                # Store transfer as part of ContractTransactionHistory
                                blockchainReference = neturl + 'tx/' + transaction_data['txid']
                                session.add(ContractTransactionHistory1(transactionType='incorporation', sourceFloAddress=inputadd,
                                                                        destFloAddress=outputlist[0],
                                                                        transferAmount=None,
                                                                        blockNumber=transaction_data['blockheight'],
                                                                        blockHash=transaction_data['blockhash'],
                                                                        time=transaction_data['blocktime'],
                                                                        transactionHash=transaction_data['txid'],
                                                                        blockchainReference=blockchainReference,
                                                                        jsonData=json.dumps(
                                                                            transaction_data),
                                                                        parsedFloData=json.dumps(
                                                                            parsed_data)
                                                                        ))
                                session.commit()
                                session.close()

                                # add Smart Contract name in token contract association
                                accepting_sending_tokenlist = [parsed_data['contractConditions']['accepting_token'], parsed_data['contractConditions']['selling_token']]
                                for token_name in accepting_sending_tokenlist:
                                    token_name = token_name.split('#')[0]
                                    session = create_database_session_orm('token', {'token_name': f"{token_name}"}, Base)
                                    session.add(TokenContractAssociation(tokenIdentification=token_name,
                                                                            contractName=parsed_data['contractName'],
                                                                            contractAddress=parsed_data['contractAddress'],
                                                                            blockNumber=transaction_data['blockheight'],
                                                                            blockHash=transaction_data['blockhash'],
                                                                            time=transaction_data['blocktime'],
                                                                            transactionHash=transaction_data['txid'],
                                                                            blockchainReference=blockchainReference,
                                                                            jsonData=json.dumps(transaction_data),
                                                                            transactionType=parsed_data['type'],
                                                                            parsedFloData=json.dumps(parsed_data)))
                                    session.commit()
                                    session.close()

                                # Store smart contract address in system's db, to be ignored during future transfers
                                session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                                session.add(ActiveContracts(contractName=parsed_data['contractName'],
                                                            contractAddress=parsed_data['contractAddress'], status='active',
                                                            tokenIdentification=str(accepting_sending_tokenlist),
                                                            contractType=parsed_data['contractType'],
                                                            transactionHash=transaction_data['txid'],
                                                            blockNumber=transaction_data['blockheight'],
                                                            blockHash=transaction_data['blockhash'],
                                                            incorporationDate=transaction_data['blocktime']))
                                session.commit()

                                # todo - Add a condition for rejected contract transaction on the else loop for this condition 
                                session.add(ContractAddressMapping(address=inputadd, addressType='incorporation',
                                                                    tokenAmount=None,
                                                                    contractName=parsed_data['contractName'],
                                                                    contractAddress=inputadd,
                                                                    transactionHash=transaction_data['txid'],
                                                                    blockNumber=transaction_data['blockheight'],
                                                                    blockHash=transaction_data['blockhash']))
                                session.commit()
                                session.close()

                                updateLatestTransaction(transaction_data, parsed_data)

                                pushData_SSEapi('Contract | Contract incorporated at transaction {} with name {}-{}'.format(transaction_data['txid'], parsed_data['contractName'], parsed_data['contractAddress']))
                                return 1
                        
                                '''else if (parsed_data['contractConditions']['subtype'] == 'bitbonds'):
                                    # Check if both the tokens mentioned in the bond exist 
                                    pass                        
                                    '''
                            else:
                                logger.info(f"priceType is not part of accepted parameters for a continuos event contract of the type token swap.\nSmart contract incorporation on transaction {transaction_data['txid']} rejected")
                                # Store transfer as part of RejectedContractTransactionHistory
                                session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                                blockchainReference = neturl + 'tx/' + transaction_data['txid']
                                session.add(RejectedContractTransactionHistory(transactionType='incorporation',
                                                                                contractName=parsed_data['contractName'],
                                                                                contractAddress=outputlist[0],
                                                                                sourceFloAddress=inputadd,
                                                                                destFloAddress=outputlist[0],
                                                                                transferAmount=None,
                                                                                blockNumber=transaction_data['blockheight'],
                                                                                blockHash=transaction_data['blockhash'],
                                                                                time=transaction_data['blocktime'],
                                                                                transactionHash=transaction_data['txid'],
                                                                                blockchainReference=blockchainReference,
                                                                                jsonData=json.dumps(
                                                                                    transaction_data),
                                                                                rejectComment=f"priceType is not part of accepted parameters for a continuos event contract of the type token swap.\nSmart contract incorporation on transaction {transaction_data['txid']} rejected",
                                                                                parsedFloData=json.dumps(
                                                                                    parsed_data)
                                                                                ))
                                session.commit()
                                session.close()
                                return 0
                    
                    else:
                        logger.info(f"No subtype provided || mentioned tokens do not exist for the Contract of type continuos event.\nSmart contract incorporation on transaction {transaction_data['txid']} rejected")
                        # Store transfer as part of RejectedContractTransactionHistory
                        session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                        blockchainReference = neturl + 'tx/' + transaction_data['txid']
                        session.add(RejectedContractTransactionHistory(transactionType='incorporation',
                                                                        contractName=parsed_data['contractName'],
                                                                        contractAddress=outputlist[0],
                                                                        sourceFloAddress=inputadd,
                                                                        destFloAddress=outputlist[0],
                                                                        transferAmount=None,
                                                                        blockNumber=transaction_data['blockheight'],
                                                                        blockHash=transaction_data['blockhash'],
                                                                        time=transaction_data['blocktime'],
                                                                        transactionHash=transaction_data['txid'],
                                                                        blockchainReference=blockchainReference,
                                                                        jsonData=json.dumps(
                                                                            transaction_data),
                                                                        rejectComment=f"No subtype provided for the Contract of type continuos event.\nSmart contract incorporation on transaction {transaction_data['txid']} rejected",
                                                                        parsedFloData=json.dumps(
                                                                            parsed_data)
                                                                        ))
                        session.commit()
                        session.close()
                        return 0

                session.commit()
                session.close()

        else:
            logger.info(f"Transaction {transaction_data['txid']} rejected as a Smart Contract with the name {parsed_data['contractName']} at address {parsed_data['contractAddress']} already exists")
            # Store transfer as part of RejectedContractTransactionHistory
            session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
            blockchainReference = neturl + 'tx/' + transaction_data['txid']
            session.add(RejectedContractTransactionHistory(transactionType='incorporation',
                                                           contractName=parsed_data['contractName'],
                                                           contractAddress=outputlist[0], sourceFloAddress=inputadd,
                                                           destFloAddress=outputlist[0],
                                                           transferAmount=None,
                                                           blockNumber=transaction_data['blockheight'],
                                                           blockHash=transaction_data['blockhash'],
                                                           time=transaction_data['blocktime'],
                                                           transactionHash=transaction_data['txid'],
                                                           blockchainReference=blockchainReference,
                                                           jsonData=json.dumps(transaction_data),
                                                           rejectComment=f"Transaction {transaction_data['txid']} rejected as a Smart Contract with the name {parsed_data['contractName']} at address {parsed_data['contractAddress']} already exists",
                                                           parsedFloData=json.dumps(parsed_data)
                                                           ))
            session.commit()
            session.close()

            headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
            '''r = requests.post(tokenapi_sse_url, json={
                'message': 'Error | Contract Incorporation rejected as a smartcontract with same name {}-{} is active currentlyt at transaction {}'.format(parsed_data['contractName'], parsed_data['contractAddress'], transaction_data['txid'])}, headers=headers)
            '''
            return 0

    elif parsed_data['type'] == 'smartContractPays':
        logger.info(f"Transaction {transaction_data['txid']} is of the type smartContractPays")

        # Check if input address is a committee address
        if inputlist[0] in committeeAddressList:
            # check if the contract exists
            if check_database_existence('smart_contract', {'contract_name':f"{parsed_data['contractName']}", 'contract_address':f"{outputlist[0]}"}):
                # Check if the transaction hash already exists in the contract db (Safety check)
                connection = create_database_connection('smart_contract', {'contract_name':f"{parsed_data['contractName']}", 'contract_address':f"{outputlist[0]}"})
                participantAdd_txhash = connection.execute(
                    f"select sourceFloAddress, transactionHash from contractTransactionHistory where transactionType != 'incorporation'").fetchall()
                participantAdd_txhash_T = list(zip(*participantAdd_txhash))

                if len(participantAdd_txhash) != 0 and transaction_data['txid'] in list(participantAdd_txhash_T[1]):
                    logger.warning(
                        f"Transaction {transaction_data['txid']} rejected as it already exists in the Smart Contract db. This is unusual, please check your code")
                    pushData_SSEapi(
                        f"Error | Transaction {transaction_data['txid']} rejected as it already exists in the Smart Contract db. This is unusual, please check your code")
                    return 0

                # pull out the contract structure into a dictionary
                connection = create_database_connection('smart_contract', {'contract_name':f"{parsed_data['contractName']}", 'contract_address':f"{outputlist[0]}"})
                attributevaluepair = connection.execute("select attribute, value from contractstructure where attribute != 'contractName' and attribute != 'flodata' and attribute != 'contractAddress'").fetchall()
                contractStructure = {}
                conditionDict = {}
                counter = 0
                for item in attributevaluepair:
                    if list(item)[0] == 'exitconditions':
                        conditionDict[counter] = list(item)[1]
                        counter = counter + 1
                    else:
                        contractStructure[list(item)[0]] = list(item)[1]
                if len(conditionDict) > 0:
                    contractStructure['exitconditions'] = conditionDict
                del counter, conditionDict

                # if contractAddress has been passed, check if output address is contract Incorporation address
                if 'contractAddress' in contractStructure:
                    if outputlist[0] != contractStructure['contractAddress']:
                        logger.warning(
                            f"Transaction {transaction_data['txid']} rejected as Smart Contract named {parsed_data['contractName']} at the address {outputlist[0]} hasn't expired yet")
                        # Store transfer as part of RejectedContractTransactionHistory
                        session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                        blockchainReference = neturl + 'tx/' + transaction_data['txid']
                        session.add(
                            RejectedContractTransactionHistory(transactionType='trigger',
                                                               contractName=parsed_data['contractName'],
                                                               contractAddress=outputlist[0],
                                                               sourceFloAddress=inputadd,
                                                               destFloAddress=outputlist[0],
                                                               transferAmount=None,
                                                               blockNumber=transaction_data['blockheight'],
                                                               blockHash=transaction_data['blockhash'],
                                                               time=transaction_data['blocktime'],
                                                               transactionHash=transaction_data['txid'],
                                                               blockchainReference=blockchainReference,
                                                               jsonData=json.dumps(transaction_data),
                                                               rejectComment=f"Transaction {transaction_data['txid']} rejected as Smart Contract named {parsed_data['contractName']} at the address {outputlist[0]} hasn't expired yet",

                                                               parsedFloData=json.dumps(parsed_data)
                                                               ))
                        session.commit()
                        session.close()
                        pushData_SSEapi(
                            f"Error | Transaction {transaction_data['txid']} rejected as Smart Contract named {parsed_data['contractName']} at the address {outputlist[0]} hasn't expired yet")
                        return 0

                # check the type of smart contract ie. external trigger or internal trigger
                if 'payeeAddress' in contractStructure:
                    logger.warning(
                        f"Transaction {transaction_data['txid']} rejected as Smart Contract named {parsed_data['contractName']} at the address {outputlist[0]} has an internal trigger")
                    # Store transfer as part of RejectedContractTransactionHistory
                    session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                    blockchainReference = neturl + 'tx/' + transaction_data['txid']
                    session.add(
                        RejectedContractTransactionHistory(transactionType='trigger',
                                                           contractName=parsed_data['contractName'],
                                                           contractAddress=outputlist[0],
                                                           sourceFloAddress=inputadd,
                                                           destFloAddress=outputlist[0],
                                                           transferAmount=None,
                                                           blockNumber=transaction_data['blockheight'],
                                                           blockHash=transaction_data['blockhash'],
                                                           time=transaction_data['blocktime'],
                                                           transactionHash=transaction_data['txid'],
                                                           blockchainReference=blockchainReference,
                                                           jsonData=json.dumps(transaction_data),
                                                           rejectComment=f"Transaction {transaction_data['txid']} rejected as Smart Contract named {parsed_data['contractName']} at the address {outputlist[0]} has an internal trigger",

                                                           parsedFloData=json.dumps(parsed_data)
                                                           ))
                    session.commit()
                    session.close()
                    pushData_SSEapi(
                        f"Error | Transaction {transaction_data['txid']} rejected as Smart Contract named {parsed_data['contractName']} at the address {outputlist[0]} has an internal trigger")
                    return 0

                # check the status of the contract
                connection = create_database_connection('system_dbs', {'db_name':'system'})
                contractStatus = connection.execute(
                    f"select status from activecontracts where contractName=='{parsed_data['contractName']}' and contractAddress='{outputlist[0]}'").fetchall()[
                    0][0]
                connection.close()
                contractList = []

                if contractStatus == 'closed':
                    logger.info(
                        f"Transaction {transaction_data['txid']} closed as Smart contract {parsed_data['contractName']} at the {outputlist[0]} is closed")
                    # Store transfer as part of RejectedContractTransactionHistory
                    session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                    blockchainReference = neturl + 'tx/' + transaction_data['txid']
                    session.add(
                        RejectedContractTransactionHistory(transactionType='trigger',
                                                           contractName=parsed_data['contractName'],
                                                           contractAddress=outputlist[0],
                                                           sourceFloAddress=inputadd,
                                                           destFloAddress=outputlist[0],
                                                           transferAmount=None,
                                                           blockNumber=transaction_data['blockheight'],
                                                           blockHash=transaction_data['blockhash'],
                                                           time=transaction_data['blocktime'],
                                                           transactionHash=transaction_data['txid'],
                                                           blockchainReference=blockchainReference,
                                                           jsonData=json.dumps(transaction_data),
                                                           rejectComment=f"Transaction {transaction_data['txid']} closed as Smart contract {parsed_data['contractName']} at the {outputlist[0]} is closed",

                                                           parsedFloData=json.dumps(parsed_data)
                                                           ))
                    session.commit()
                    session.close()

                    headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
                    '''r = requests.post(tokenapi_sse_url, json={
                        'message': f"Error | Transaction {transaction_data['txid']} closed as Smart contract {parsed_data['contractName']} at the {outputlist[0]} is closed"},
                                      headers=headers)'''
                    return 0
                else:
                    session = create_database_session_orm('smart_contract', {'contract_name': f"{parsed_data['contractName']}", 'contract_address': f"{outputlist[0]}"}, ContractBase)
                    result = session.query(ContractStructure).filter_by(attribute='expiryTime').all()
                    session.close()
                    if result:
                        # now parse the expiry time in python
                        expirytime = result[0].value.strip()
                        expirytime_split = expirytime.split(' ')
                        parse_string = '{}/{}/{} {}'.format(expirytime_split[3],
                                                            parsing.months[expirytime_split[1]],
                                                            expirytime_split[2], expirytime_split[4])
                        expirytime_object = parsing.arrow.get(parse_string, 'YYYY/M/D HH:mm:ss').replace(
                            tzinfo=expirytime_split[5][3:])
                        blocktime_object = parsing.arrow.get(transaction_data['blocktime']).to('Asia/Kolkata')

                        if blocktime_object <= expirytime_object:
                            logger.info(
                                f"Transaction {transaction_data['txid']} rejected as Smart contract {parsed_data['contractName']}-{outputlist[0]} has not expired and will not trigger")
                            # Store transfer as part of RejectedContractTransactionHistory
                            session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                            blockchainReference = neturl + 'tx/' + transaction_data['txid']
                            session.add(
                                RejectedContractTransactionHistory(transactionType='trigger',
                                                                   contractName=parsed_data['contractName'],
                                                                   contractAddress=outputlist[0],
                                                                   sourceFloAddress=inputadd,
                                                                   destFloAddress=outputlist[0],
                                                                   transferAmount=None,
                                                                   blockNumber=transaction_data['blockheight'],
                                                                   blockHash=transaction_data['blockhash'],
                                                                   time=transaction_data['blocktime'],
                                                                   transactionHash=transaction_data['txid'],
                                                                   blockchainReference=blockchainReference,
                                                                   jsonData=json.dumps(transaction_data),
                                                                   rejectComment=f"Transaction {transaction_data['txid']} rejected as Smart contract {parsed_data['contractName']}-{outputlist[0]} has not expired and will not trigger",

                                                                   parsedFloData=json.dumps(parsed_data)
                                                                   ))
                            session.commit()
                            session.close()
                            pushData_SSEapi(
                                f"Error| Transaction {transaction_data['txid']} rejected as Smart contract {parsed_data['contractName']}-{outputlist[0]} has not expired and will not trigger")
                            return 0

                # check if the user choice passed is part of the contract structure
                tempchoiceList = []
                for item in contractStructure['exitconditions']:
                    tempchoiceList.append(contractStructure['exitconditions'][item])

                if parsed_data['triggerCondition'] not in tempchoiceList:
                    logger.info(
                        f"Transaction {transaction_data['txid']} rejected as triggerCondition, {parsed_data['triggerCondition']}, has been passed to Smart Contract named {parsed_data['contractName']} at the address {outputlist[0]} which doesn't accept any userChoice of the given name")
                    # Store transfer as part of RejectedContractTransactionHistory
                    session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                    blockchainReference = neturl + 'tx/' + transaction_data['txid']
                    session.add(
                        RejectedContractTransactionHistory(transactionType='trigger',
                                                           contractName=parsed_data['contractName'],
                                                           contractAddress=outputlist[0],
                                                           sourceFloAddress=inputadd,
                                                           destFloAddress=outputlist[0],
                                                           transferAmount=None,
                                                           blockNumber=transaction_data['blockheight'],
                                                           blockHash=transaction_data['blockhash'],
                                                           time=transaction_data['blocktime'],
                                                           transactionHash=transaction_data['txid'],
                                                           blockchainReference=blockchainReference,
                                                           jsonData=json.dumps(transaction_data),
                                                           rejectComment=f"Transaction {transaction_data['txid']} rejected as triggerCondition, {parsed_data['triggerCondition']}, has been passed to Smart Contract named {parsed_data['contractName']} at the address {outputlist[0]} which doesn't accept any userChoice of the given name",

                                                           parsedFloData=json.dumps(parsed_data)
                                                           ))
                    session.commit()
                    session.close()
                    pushData_SSEapi(
                        f"Error | Transaction {transaction_data['txid']} rejected as triggerCondition, {parsed_data['triggerCondition']}, has been passed to Smart Contract named {parsed_data['contractName']} at the address {outputlist[0]} which doesn't accept any userChoice of the given name")
                    return 0

                # check if minimumsubscriptionamount exists as part of the contract structure
                if 'minimumsubscriptionamount' in contractStructure:
                    # if it has not been reached, close the contract and return money
                    minimumsubscriptionamount = float(contractStructure['minimumsubscriptionamount'])
                    session = create_database_session_orm('smart_contract', {'contract_name': f"{parsed_data['contractName']}", 'contract_address': f"{outputlist[0]}"}, ContractBase)
                    amountDeposited = session.query(func.sum(ContractParticipants.tokenAmount)).all()[0][0]
                    session.close()

                    if amountDeposited is None:
                        amountDeposited = 0

                    if amountDeposited < minimumsubscriptionamount:
                        # close the contract and return the money
                        logger.info(
                            'Minimum subscription amount hasn\'t been reached\n The token will be returned back')
                        # Initialize payback to contract participants
                        connection = create_database_connection('smart_contract', {'contract_name':f"{parsed_data['contractName']}", 'contract_address':f"{outputlist[0]}"})
                        contractParticipants = connection.execute(
                            'select participantAddress, tokenAmount, transactionHash from contractparticipants').fetchall()[
                            0][0]

                        for participant in contractParticipants:
                            tokenIdentification = connection.execute(
                                'select * from contractstructure where attribute="tokenIdentification"').fetchall()[0][
                                0]
                            contractAddress = connection.execute(
                                'select * from contractstructure where attribute="contractAddress"').fetchall()[0][0]
                            returnval = transferToken(tokenIdentification, participant[1], contractAddress,
                                                      participant[0], transaction_data, parsed_data)
                            if returnval is None:
                                logger.info(
                                    "CRITICAL ERROR | Something went wrong in the token transfer method while doing local Smart Contract Trigger")
                                return 0

                            connection.execute(
                                'update contractparticipants set winningAmount="{}" where participantAddress="{}" and transactionHash="{}"'.format(
                                    (participant[1], participant[0], participant[4])))

                        # add transaction to ContractTransactionHistory
                        blockchainReference = neturl + 'tx/' + transaction_data['txid']
                        session = create_database_session_orm('smart_contract', {'contract_name': f"{parsed_data['contractName']}", 'contract_address': f"{outputlist[0]}"}, ContractBase)
                        session.add(ContractTransactionHistory(transactionType='trigger',
                                                               transactionSubType='minimumsubscriptionamount-payback',
                                                               sourceFloAddress=inputadd,
                                                               destFloAddress=outputlist[0],
                                                               transferAmount=None,
                                                               blockNumber=transaction_data['blockheight'],
                                                               blockHash=transaction_data['blockhash'],
                                                               time=transaction_data['blocktime'],
                                                               transactionHash=transaction_data['txid'],
                                                               blockchainReference=blockchainReference,
                                                               jsonData=json.dumps(transaction_data),

                                                               parsedFloData=json.dumps(parsed_data)
                                                               ))
                        session.commit()
                        session.close()

                        connection = create_database_connection('system_dbs', {'db_name':'system'})
                        connection.execute(
                            'update activecontracts set status="closed" where contractName="{}" and contractAddress="{}"'.format(
                                parsed_data['contractName'], outputlist[0]))
                        connection.execute(
                            'update activecontracts set status="{}" where contractName="{}" and contractAddress="{}"'.format(
                                transaction_data['blocktime'],
                                parsed_data['contractName'], outputlist[0]))
                        connection.close()

                        updateLatestTransaction(transaction_data, parsed_data)

                        pushData_SSEapi(
                            'Trigger | Minimum subscription amount not reached at contract {}-{} at transaction {}. Tokens will be refunded'.format(
                                parsed_data['contractName'], outputlist[0], transaction_data['txid']))
                        return 1

                # Trigger the contract
                connection = create_database_connection('smart_contract', {'contract_name':f"{parsed_data['contractName']}", 'contract_address':f"{outputlist[0]}"})
                contractWinners = connection.execute(
                    'select * from contractparticipants where userChoice="{}"'.format(
                        parsed_data['triggerCondition'])).fetchall()
                tokenSum = connection.execute('select sum(tokenAmount) from contractparticipants').fetchall()[0][0]
                winnerSum = connection.execute(
                    'select sum(tokenAmount) from contractparticipants where userChoice="{}"'.format(
                        parsed_data['triggerCondition'])).fetchall()[0][0]
                tokenIdentification = connection.execute(
                    'select value from contractstructure where attribute="tokenIdentification"').fetchall()[0][0]

                for winner in contractWinners:
                    winnerAmount = "%.8f" % ((winner[2] / winnerSum) * tokenSum)
                    returnval = transferToken(tokenIdentification, winnerAmount,
                                              outputlist[0], winner[1], transaction_data, parsed_data)
                    if returnval is None:
                        logger.critical(
                            "Something went wrong in the token transfer method while doing local Smart Contract Trigger")
                        return 0
                    connection.execute(
                        f"update contractparticipants set winningAmount='{winnerAmount}' where participantAddress='{winner[1]}' and transactionHash='{winner[4]}'")

                # add transaction to ContractTransactionHistory
                blockchainReference = neturl + 'tx/' + transaction_data['txid']
                session.add(ContractTransactionHistory(transactionType='trigger',
                                                       transactionSubType='committee',
                                                       sourceFloAddress=inputadd,
                                                       destFloAddress=outputlist[0],
                                                       transferAmount=None,
                                                       blockNumber=transaction_data['blockheight'],
                                                       blockHash=transaction_data['blockhash'],
                                                       time=transaction_data['blocktime'],
                                                       transactionHash=transaction_data['txid'],
                                                       blockchainReference=blockchainReference,
                                                       jsonData=json.dumps(transaction_data),

                                                       parsedFloData=json.dumps(parsed_data)
                                                       ))
                session.commit()
                session.close()

                connection = create_database_connection('system_dbs', {'db_name':'system'})
                connection.execute(
                    'update activecontracts set status="closed" where contractName="{}" and contractAddress="{}"'.format(
                        parsed_data['contractName'], outputlist[0]))
                connection.execute(
                    'update activecontracts set closeDate="{}" where contractName="{}" and contractAddress="{}"'.format(
                        transaction_data['blocktime'],
                        parsed_data['contractName'], outputlist[0]))
                connection.close()

                updateLatestTransaction(transaction_data, parsed_data)

                pushData_SSEapi(
                    'Trigger | Contract triggered of the name {}-{} is active currently at transaction {}'.format(
                        parsed_data['contractName'], outputlist[0], transaction_data['txid']))
                return 1
            else:
                logger.info(
                    f"Transaction {transaction_data['txid']} rejected as Smart Contract named {parsed_data['contractName']} at the address {outputlist[0]} doesn't exist")
                # Store transfer as part of RejectedContractTransactionHistory
                session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                blockchainReference = neturl + 'tx/' + transaction_data['txid']
                session.add(
                    RejectedContractTransactionHistory(transactionType='trigger',
                                                       contractName=parsed_data['contractName'],
                                                       contractAddress=outputlist[0],
                                                       sourceFloAddress=inputadd,
                                                       destFloAddress=outputlist[0],
                                                       transferAmount=None,
                                                       blockNumber=transaction_data['blockheight'],
                                                       blockHash=transaction_data['blockhash'],
                                                       time=transaction_data['blocktime'],
                                                       transactionHash=transaction_data['txid'],
                                                       blockchainReference=blockchainReference,
                                                       jsonData=json.dumps(transaction_data),
                                                       rejectComment=f"Transaction {transaction_data['txid']} rejected as Smart Contract named {parsed_data['contractName']} at the address {outputlist[0]} doesn't exist",

                                                       parsedFloData=json.dumps(parsed_data)
                                                       ))
                session.commit()
                session.close()
                pushData_SSEapi(
                    f"Error | Transaction {transaction_data['txid']} rejected as Smart Contract named {parsed_data['contractName']} at the address {outputlist[0]} doesn't exist")
                return 0

        else:
            logger.info(
                f"Transaction {transaction_data['txid']} rejected as input address, {inputlist[0]}, is not part of the committee address list")
            # Store transfer as part of RejectedContractTransactionHistory
            session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
            blockchainReference = neturl + 'tx/' + transaction_data['txid']
            session.add(RejectedContractTransactionHistory(transactionType='trigger',
                                                           contractName=parsed_data['contractName'],
                                                           contractAddress=outputlist[0],
                                                           sourceFloAddress=inputadd,
                                                           destFloAddress=outputlist[0],
                                                           transferAmount=None,
                                                           blockNumber=transaction_data['blockheight'],
                                                           blockHash=transaction_data['blockhash'],
                                                           time=transaction_data['blocktime'],
                                                           transactionHash=transaction_data['txid'],
                                                           blockchainReference=blockchainReference,
                                                           jsonData=json.dumps(transaction_data),
                                                           rejectComment=f"Transaction {transaction_data['txid']} rejected as input address, {inputlist[0]}, is not part of the committee address list",

                                                           parsedFloData=json.dumps(parsed_data)
                                                           ))
            session.commit()
            session.close()
            pushData_SSEapi(
                f"Transaction {transaction_data['txid']} rejected as input address, {inputlist[0]}, is not part of the committee address list")
            return 0

    elif parsed_data['type'] == 'smartContractDeposit':
        if check_database_existence('smart_contract', {'contract_name':f"{parsed_data['contractName']}", 'contract_address':f"{outputlist[0]}"}):
            # Check if the transaction hash already exists in the contract db (Safety check)
            connection = create_database_connection('smart_contract', {'contract_name':f"{parsed_data['contractName']}", 'contract_address':f"{outputlist[0]}"})
            participantAdd_txhash = connection.execute('select participantAddress, transactionHash from contractparticipants').fetchall()
            participantAdd_txhash_T = list(zip(*participantAdd_txhash))

            if len(participantAdd_txhash) != 0 and transaction_data['txid'] in list(participantAdd_txhash_T[1]):
                logger.warning(f"Transaction {transaction_data['txid']} rejected as it already exists in the Smart Contract db. This is unusual, please check your code")
                pushData_SSEapi(f"Error | Transaction {transaction_data['txid']} rejected as it already exists in the Smart Contract db. This is unusual, please check your code")
                return 0

            # if contractAddress was passed, then check if it matches the output address of this contract
            if 'contractAddress' in parsed_data:
                if parsed_data['contractAddress'] != outputlist[0]:
                    logger.info(f"Contract participation at transaction {transaction_data['txid']} rejected as contractAddress specified in flodata, {parsed_data['contractAddress']}, doesnt not match with transaction's output address {outputlist[0]}")
                    # Store transfer as part of RejectedContractTransactionHistory
                    session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
                    blockchainReference = neturl + 'tx/' + transaction_data['txid']
                    session.add(RejectedContractTransactionHistory(transactionType='participation',
                                                            contractName=parsed_data['contractName'],
                                                            contractAddress=outputlist[0],
                                                            sourceFloAddress=inputadd,
                                                            destFloAddress=outputlist[0],
                                                            transferAmount=None,
                                                            blockNumber=transaction_data['blockheight'],
                                                            blockHash=transaction_data['blockhash'],
                                                            time=transaction_data['blocktime'],
                                                            transactionHash=transaction_data['txid'],
                                                            blockchainReference=blockchainReference,
                                                            jsonData=json.dumps(transaction_data),
                                                            rejectComment=f"Contract participation at transaction {transaction_data['txid']} rejected as contractAddress specified in flodata, {parsed_data['contractAddress']}, doesnt not match with transaction's output address {outputlist[0]}",
                                                            parsedFloData=json.dumps(parsed_data)))
                    session.commit()
                    session.close()

                    headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
                    '''r = requests.post(tokenapi_sse_url, json={'message': f"Error | Contract participation at transaction {transaction_data['txid']} rejected as contractAddress specified in flodata, {parsed_data['contractAddress']}, doesnt not match with transaction's output address {outputlist[0]}"}, headers=headers)'''

                    # Pass information to SSE channel
                    pushData_SSEapi('Error| Mismatch in contract address specified in flodata and the output address of the transaction {}'.format(transaction_data['txid']))
                    return 0

            # pull out the contract structure into a dictionary
            connection = create_database_connection('smart_contract', {'contract_name':f"{parsed_data['contractName']}", 'contract_address':f"{outputlist[0]}"})
            attributevaluepair = connection.execute("select attribute, value from contractstructure where attribute != 'contractName' and attribute != 'flodata' and attribute != 'contractAddress'").fetchall()
            contractStructure = {}
            conditionDict = {}
            counter = 0
            for item in attributevaluepair:
                if list(item)[0] == 'exitconditions':
                    conditionDict[counter] = list(item)[1]
                    counter = counter + 1
                else:
                    contractStructure[list(item)[0]] = list(item)[1]
            if len(conditionDict) > 0:
                contractStructure['exitconditions'] = conditionDict
            del counter, conditionDict


            # Push the deposit transaction into deposit database contract database 
            session = create_database_session_orm('smart_contract', {'contract_name': f"{parsed_data['contractName']}", 'contract_address': f"{outputlist[0]}"}, ContinuosContractBase)
            blockchainReference = neturl + 'tx/' + transaction_data['txid']
            session.add(ContractDeposits1(depositorAddress = inputadd,
                                            depositAmount = parsed_data['depositAmount'],
                                            expiryTime = parsed_data['depositConditions']['expiryTime'],
                                            transactionHash = transaction_data['txid'],
                                            blockNumber = transaction_data['blockheight'],
                                            blockHash = transaction_data['blockhash']
                                            ))
            session.add(ContractTransactionHistory1(transactionType = 'smartContractDeposit',
                                                    transactionSubType = None,
                                                    sourceFloAddress = inputadd,
                                                    destFloAddress = outputlist[0],
                                                    transferAmount = parsed_data['depositAmount'],
                                                    blockNumber = transaction_data['blockheight'],
                                                    blockHash = transaction_data['blockhash'],
                                                    time = transaction_data['blocktime'],
                                                    transactionHash = transaction_data['txid'],
                                                    blockchainReference = blockchainReference,
                                                    jsonData = json.dumps(transaction_data),
                                                    parsedFloData = json.dumps(parsed_data)
                                                    ))
            session.commit()
            session.close()
            pushData_SSEapi(f"Deposit Smart Contract Transaction {transaction_data['txid']} rejected as maximum subscription amount has been reached for the Smart contract named {parsed_data['contractName']} at the address {outputlist[0]}")
            return 0

        else:
            logger.info(f"Transaction {transaction_data['txid']} rejected as a Smart Contract with the name {parsed_data['contractName']} at address {outputlist[0]} doesnt exist")
            # Store transfer as part of RejectedContractTransactionHistory
            session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
            blockchainReference = neturl + 'tx/' + transaction_data['txid']
            session.add(RejectedContractTransactionHistory(transactionType='smartContractDeposit',
                                                    contractName=parsed_data['contractName'],
                                                    contractAddress=outputlist[0],
                                                    sourceFloAddress=inputadd,
                                                    destFloAddress=outputlist[0],
                                                    transferAmount=None,
                                                    blockNumber=transaction_data['blockheight'],
                                                    blockHash=transaction_data['blockhash'],
                                                    time=transaction_data['blocktime'],
                                                    transactionHash=transaction_data['txid'],
                                                    blockchainReference=blockchainReference,
                                                    jsonData=json.dumps(transaction_data),
                                                    rejectComment=f"Transaction {transaction_data['txid']} rejected as a Smart Contract with the name {parsed_data['contractName']} at address {outputlist[0]} doesnt exist",

                                                    parsedFloData=json.dumps(parsed_data)
                                                    ))
            session.commit()
            session.close()

            headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
            '''r = requests.post(tokenapi_sse_url, json={'message': f"Error | Contract transaction {transaction_data['txid']} rejected as a smartcontract with same name {parsed_data['contractName']}-{parsed_data['contractAddress']} dosent exist "}, headers=headers)'''
            return 0
    
    elif parsed_data['type'] == 'nftIncorporation':
        '''
            DIFFERENT BETWEEN TOKEN AND NFT
            System.db will have a different entry
            in creation nft word will be extra
            NFT Hash must be  present
            Creation and transfer amount .. only integer parts will be taken
            Keyword nft must be present in both creation and transfer
        '''
        if not check_database_existence('token', {'token_name':f"{parsed_data['tokenIdentification']}"}):
            session = create_database_session_orm('token', {'token_name': f"{parsed_data['tokenIdentification']}"}, Base)
            session.add(ActiveTable(address=inputlist[0], parentid=0, transferBalance=parsed_data['tokenAmount']))
            session.add(TransferLogs(sourceFloAddress=inputadd, destFloAddress=outputlist[0],
                                     transferAmount=parsed_data['tokenAmount'], sourceId=0, destinationId=1,
                                     blockNumber=transaction_data['blockheight'], time=transaction_data['blocktime'],
                                     transactionHash=transaction_data['txid']))
            blockchainReference = neturl + 'tx/' + transaction_data['txid']
            session.add(TransactionHistory(sourceFloAddress=inputadd, destFloAddress=outputlist[0],
                                           transferAmount=parsed_data['tokenAmount'],
                                           blockNumber=transaction_data['blockheight'],
                                           blockHash=transaction_data['blockhash'],
                                           time=transaction_data['blocktime'],
                                           transactionHash=transaction_data['txid'],
                                           blockchainReference=blockchainReference,
                                           jsonData=json.dumps(transaction_data), transactionType=parsed_data['type'],
                                           parsedFloData=json.dumps(parsed_data)))
            session.commit()
            session.close()

            # add it to token address to token mapping db table
            connection = create_database_connection('system_dbs', {'db_name':'system'})
            connection.execute(f"INSERT INTO tokenAddressMapping (tokenAddress, token, transactionHash, blockNumber, blockHash) VALUES ('{inputadd}', '{parsed_data['tokenIdentification']}', '{transaction_data['txid']}', '{transaction_data['blockheight']}', '{transaction_data['blockhash']}');")
            nft_data = {'sha256_hash': f"{parsed_data['nftHash']}"}
            connection.execute(f"INSERT INTO databaseAddressMapping (db_name, db_type, keyword, object_format) VALUES ('{parsed_data['tokenIdentification']}', 'nft', '', '{nft_data}'")
            connection.close()

            updateLatestTransaction(transaction_data, parsed_data)

            pushData_SSEapi(f"Token | Succesfully incorporated token {parsed_data['tokenIdentification']} at transaction {transaction_data['txid']}")
            return 1
        else:
            logger.info(f"Transaction {transaction_data['txid']} rejected as a token with the name {parsed_data['tokenIdentification']} has already been incorporated")
            session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
            blockchainReference = neturl + 'tx/' + transaction_data['txid']
            session.add(RejectedTransactionHistory(tokenIdentification=parsed_data['tokenIdentification'],
                                                   sourceFloAddress=inputadd, destFloAddress=outputlist[0],
                                                   transferAmount=parsed_data['tokenAmount'],
                                                   blockNumber=transaction_data['blockheight'],
                                                   blockHash=transaction_data['blockhash'],
                                                   time=transaction_data['blocktime'],
                                                   transactionHash=transaction_data['txid'],
                                                   blockchainReference=blockchainReference,
                                                   jsonData=json.dumps(transaction_data),
                                                   rejectComment=f"Transaction {transaction_data['txid']} rejected as a token with the name {parsed_data['tokenIdentification']} has already been incorporated",
                                                   transactionType=parsed_data['type'],
                                                   parsedFloData=json.dumps(parsed_data)
                                                   ))
            session.commit()
            session.close()
            pushData_SSEapi(f"Error | Token incorporation rejected at transaction {transaction_data['txid']} as token {parsed_data['tokenIdentification']} already exists")
            return 0


    ''' {'type': 'smartContractDeposit', 'tokenIdentification': hashList[0][:-1], 'contractName': atList[0][:-1], 'flodata': string, 'depositConditions': deposit_conditions} '''


def scanBlockchain():
    # Read start block no
    session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
    startblock = int(session.query(SystemData).filter_by(attribute='lastblockscanned').all()[0].value) + 1
    session.commit()
    session.close()

    # todo Rule 6 - Find current block height
    #      Rule 7 - Start analysing the block contents from starting block to current height

    # Find current block height
    current_index = -1
    while(current_index == -1):
        response = newMultiRequest('blocks?limit=1')
        try:
            current_index = response['blocks'][0]['height']
        except:
            logger.info('Latest block count response from multiRequest() is not in the right format. Displaying the data received in the log below')
            logger.info(response)
            logger.info('Program will wait for 1 seconds and try to reconnect')
            time.sleep(1)
        else:
            logger.info("Current block height is %s" % str(current_index))
            break
            
    for blockindex in range(startblock, current_index):
        processBlock(blockindex=blockindex) 

    # At this point the script has updated to the latest block
    # Now we connect to flosight's websocket API to get information about the latest blocks


def switchNeturl(currentneturl):
    neturlindex = serverlist.index(currentneturl)
    if neturlindex+1 >= len(serverlist):
        return serverlist[neturlindex+1  - len(serverlist)]
    else:
        return serverlist[neturlindex+1]


def reconnectWebsocket(socket_variable):
    # Switch a to different flosight
    # neturl = switchNeturl(neturl)
    # Connect to Flosight websocket to get data on new incoming blocks
    i=0
    newurl = serverlist[0]
    while(not socket_variable.connected):
        logger.info(f"While loop {i}")
        logger.info(f"Sleeping for 3 seconds before attempting reconnect to {newurl}")
        time.sleep(3)
        try:
            scanBlockchain()
            logger.info(f"Websocket endpoint which is being connected to {newurl}socket.io/socket.io.js")
            socket_variable.connect(f"{newurl}socket.io/socket.io.js")
            i=i+1
        except:
            logger.info(f"disconnect block: Failed reconnect attempt to {newurl}")
            newurl = switchNeturl(newurl)
            i=i+1


# MAIN EXECUTION STARTS
# Configuration of required variables 
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

file_handler = logging.FileHandler('tracking.log')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(stream_handler)


#  Rule 1 - Read command line arguments to reset the databases as blank
#  Rule 2     - Read config to set testnet/mainnet
#  Rule 3     - Set flo blockexplorer location depending on testnet or mainnet
#  Rule 4     - Set the local flo-cli path depending on testnet or mainnet ( removed this feature | Flosights are the only source )
#  Rule 5     - Set the block number to scan from


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

# todo - write all assertions to make sure default configs are right 
if (config['DEFAULT']['NET'] != 'mainnet') and (config['DEFAULT']['NET'] != 'testnet'):
    logger.error("NET parameter in config.ini invalid. Options are either 'mainnet' or 'testnet'. Script is exiting now")
    sys.exit(0)

# Specify mainnet and testnet server list for API calls and websocket calls 
serverlist = None
if config['DEFAULT']['NET'] == 'mainnet':
    serverlist = config['DEFAULT']['MAINNET_FLOSIGHT_SERVER_LIST']
elif config['DEFAULT']['NET'] == 'testnet':
    serverlist = config['DEFAULT']['TESTNET_FLOSIGHT_SERVER_LIST']
serverlist = serverlist.split(',')
neturl = config['DEFAULT']['FLOSIGHT_NETURL']
tokenapi_sse_url = config['DEFAULT']['TOKENAPI_SSE_URL']

# Delete database and smartcontract directory if reset is set to 1
if args.reset == 1:
    logger.info("Resetting the database. ")
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
    dirpath = os.path.join(apppath, 'latestCache.db')
    if os.path.exists(dirpath):
        os.remove(dirpath)

    # Read start block no
    startblock = int(config['DEFAULT']['START_BLOCK'])
    session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
    session.add(SystemData(attribute='lastblockscanned', value=startblock - 1))
    session.commit()
    session.close()

    # Initialize latest cache DB
    session = create_database_session_orm('system_dbs', {'db_name': "latestCache"}, LatestCacheBase)
    session.commit()
    session.close()


# MAIN LOGIC STARTS
# scan from the latest block saved locally to latest network block
scanBlockchain()

# At this point the script has updated to the latest block
# Now we connect to flosight's websocket API to get information about the latest blocks
# Neturl is the URL for Flosight API whose websocket endpoint is being connected to

sio = socketio.Client()
# Connect to a websocket endpoint and wait for further events
reconnectWebsocket(sio)
#sio.connect(f"{neturl}socket.io/socket.io.js")

@sio.on('connect')
def token_connect():
    current_time=datetime.now().strftime('%H:%M:%S')
    logger.info(f"Token Tracker has connected to websocket endpoint. Time : {current_time}")
    sio.emit('subscribe', 'inv')

@sio.on('disconnect')
def token_disconnect():
    current_time = datetime.now().strftime('%H:%M:%S')
    logger.info(f"disconnect block: Token Tracker disconnected from websocket endpoint. Time : {current_time}")
    logger.info('disconnect block: Triggering client disconnect')
    sio.disconnect()
    logger.info('disconnect block: Finished triggering client disconnect')
    reconnectWebsocket(sio)

@sio.on('connect_error')
def connect_error():
    current_time = datetime.now().strftime('%H:%M:%S')
    logger.info(f"connection error block: Token Tracker disconnected from websocket endpoint. Time : {current_time}")
    logger.info('connection error block: Triggering client disconnect')
    sio.disconnect()
    logger.info('connection error block: Finished triggering client disconnect')
    reconnectWebsocket(sio)

@sio.on('block')
def on_block(data):
    logger.info('New block received')
    logger.info(str(data))
    processBlock(blockhash=data)
