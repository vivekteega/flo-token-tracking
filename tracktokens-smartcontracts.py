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
from models import SystemData, ActiveTable, ConsumedTable, TransferLogs, TransactionHistory, Base, ContractStructure, ContractBase, ContractParticipants, SystemBase, ActiveContracts, ContractParticipantMapping


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


def checkLocaltriggerContracts(blockinfo):
    engine = create_engine('sqlite:///system.db', echo=False)
    connection = engine.connect()
    # todo : filter activeContracts which only have local triggers
    activeContracts = connection.execute('select contractName, contractAddress from activecontracts where status=="active" ').fetchall()
    connection.close()

    for contract in activeContracts:
        # Check if the contract has blockchain trigger or committee trigger
        engine = create_engine('sqlite:///smartContracts/{}-{}.db'.format(contract[0],contract[1]), echo=False)
        connection = engine.connect()
        # todo : filter activeContracts which only have local triggers
        contractStructure = connection.execute('select * from contractstructure').fetchall()
        contractStructure_T = list(zip(*contractStructure))

        if 'exitconditions' in list(contractStructure_T[1]):
            # This is a committee trigger contract
            expiryTime = connection.execute('select value from contractstructure where attribute=="expiryTime"').fetchall()[0][0]
            expirytime_split = expiryTime.split(' ')
            parse_string = '{}/{}/{} {}'.format(expirytime_split[3], parsing.months[expirytime_split[1]],
                                                expirytime_split[2], expirytime_split[4])
            expirytime_object = parsing.arrow.get(parse_string, 'YYYY/M/D HH:mm:ss').replace(
                tzinfo=expirytime_split[5])
            blocktime_object = parsing.arrow.get(blockinfo['time'])

            if blocktime_object > expirytime_object:
                if 'minimumsubscriptionamount' in list(contractStructure_T[1]):
                    minimumsubscriptionamount = connection.execute('select value from contractstructure where attribute=="minimumsubscriptionamount"').fetchall()[0][0]
                    tokenAmount_sum = connection.execute('select sum(tokenAmount) from contractparticipants').fetchall()[0][0]
                    if tokenAmount_sum < minimumsubscriptionamount:
                        # Initialize payback to contract participants
                        contractParticipants = connection.execute('select participantAddress, tokenAmount from contractparticipants').fetchall()[0][0]

                        for participant in contractParticipants:
                            tokenIdentification = connection.execute('select * from contractstructure where attribute="tokenIdentification"').fetchall()[0][0]
                            contractAddress = connection.execute('select * from contractstructure where attribute="contractAddress"').fetchall()[0][0]
                            returnval = transferToken(tokenIdentification, participant[1], contractAddress, participant[0])
                            if returnval is None:
                                print("Something went wrong in the token transfer method while doing local Smart Contract Trigger")
                        engine = create_engine('sqlite:///system.db', echo=True)
                        connection = engine.connect()
                        connection.execute(
                            'update activecontracts set status="closed" where contractName="{}" and contractAddress="{}"'.format(contract[0], contract[1]))
                        connection.close()


        else:
            # This is a blockchain trigger contract
            if 'maximumsubscriptionamount' in list(contractStructure_T[1]):
                maximumsubscriptionamount = connection.execute('select value from contractstructure where attribute=="maximumsubscriptionamount"').fetchall()[0][0]
                tokenAmount_sum = connection.execute('select sum(tokenAmount) from contractparticipants').fetchall()[0][0]
                if tokenAmount_sum >= maximumsubscriptionamount:
                    # Trigger the contract
                    payeeAddress = connection.execute('select * from contractstructure where attribute="payeeAddress"').fetchall()[0][0]
                    tokenIdentification = connection.execute('select * from contractstructure where attribute="tokenIdentification"').fetchall()[0][0]
                    contractAddress = connection.execute('select * from contractstructure where attribute="contractAddress"').fetchall()[0][0]
                    returnval = transferToken(tokenIdentification, tokenAmount_sum, contractAddress, payeeAddress)
                    if returnval is None:
                        print("Something went wrong in the token transfer method while doing local Smart Contract Trigger")
                        return
                    engine = create_engine('sqlite:///system.db', echo=False)
                    connection = engine.connect()
                    connection.execute(
                        'update activecontracts set status="closed" where contractName="{}" and contractAddress="{}"'.format(
                            contract[0], contract[1]))
                    connection.close()

            expiryTime = connection.execute('select value from contractstructure where attribute=="expiryTime"').fetchall()[0][0]
            expirytime_split = expiryTime.split(' ')
            parse_string = '{}/{}/{} {}'.format(expirytime_split[3], parsing.months[expirytime_split[1]], expirytime_split[2], expirytime_split[4])
            expirytime_object = parsing.arrow.get(parse_string, 'YYYY/M/D HH:mm:ss').replace(
                tzinfo=expirytime_split[5])
            blocktime_object = parsing.arrow.get(blockinfo['time'])

            if blocktime_object > expirytime_object:
                if 'minimumsubscriptionamount' in list(contractStructure_T[1]):
                    minimumsubscriptionamount = connection.execute('select value from contractstructure where attribute=="minimumsubscriptionamount"').fetchall()[0][0]
                    tokenAmount_sum = connection.execute('select sum(tokenAmount) from contractparticipants').fetchall()[0][0]
                    if tokenAmount_sum < minimumsubscriptionamount:
                        # Initialize payback to contract participants
                        contractParticipants = connection.execute(
                            'select participantAddress, tokenAmount from contractparticipants').fetchall()[0][0]

                        for participant in contractParticipants:
                            tokenIdentification = connection.execute(
                                'select * from contractstructure where attribute="tokenIdentification"').fetchall()[0][
                                0]
                            contractAddress = connection.execute(
                                'select * from contractstructure where attribute="contractAddress"').fetchall()[0][0]
                            returnval = transferToken(tokenIdentification, participant[1], contractAddress,
                                                      participant[0])
                            if returnval is None:
                                print(
                                    "Something went wrong in the token transfer method while doing local Smart Contract Trigger")
                                return
                        engine = create_engine('sqlite:///system.db', echo=False)
                        connection = engine.connect()
                        connection.execute(
                            'update activecontracts set status="closed" where contractName="{}" and contractAddress="{}"'.format(
                                contract[0], contract[1]))
                        connection.close()

                # Trigger the contract
                payeeAddress = connection.execute('select * from contractstructure where attribute="payeeAddress"').fetchall()[0][0]
                tokenIdentification = connection.execute('select * from contractstructure where attribute="tokenIdentification"').fetchall()[0][0]
                contractAddress = connection.execute('select * from contractstructure where attribute="contractAddress"').fetchall()[0][0]
                returnval = transferToken(tokenIdentification, tokenAmount_sum, contractAddress, payeeAddress)
                if returnval is None:
                    print("Something went wrong in the token transfer method while doing local Smart Contract Trigger")
                    return
                engine = create_engine('sqlite:///system.db', echo=False)
                connection = engine.connect()
                connection.execute(
                    'update activecontracts set status="closed" where contractName="{}" and contractAddress="{}"'.format(
                        contract[0], contract[1]))
                connection.close()



def startWorking(transaction_data, parsed_data, blockinfo):

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
            print('This transaction will be rejected')
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
            # Check if the transaction hash already exists in the token db
            engine = create_engine('sqlite:///tokens/{}.db'.format(parsed_data['tokenIdentification']), echo=True)
            connection = engine.connect()

            blockno_txhash = connection.execute('select blockNumber, transactionHash from transactionHistory').fetchall()
            blockno_txhash_T = list(zip(*blockno_txhash))

            if transaction_data['txid'] in list(blockno_txhash_T[1]):
                print('Transaction already exists in the db. This is unusual, please check your code')
                return

            returnval = transferToken(parsed_data['tokenIdentification'], parsed_data['tokenAmount'], inputlist[0], outputlist[0])
            if returnval is None:
                print("Something went wrong in the token transfer method")

        # todo Rule 46 - If the transfer type is smart contract, then call the function transferToken to do sanity checks & lock the balance
        elif parsed_data['transferType'] == 'smartContract':

            #if contractAddress was passed check if it matches the output address of this contract
            if 'contractAddress' in parsed_data:
                if parsed_data['contractAddress'] != outputlist[0]:
                    print('Mismatch in contract address specified in flodata and the output address of the transaction')
                    print('This contract transfer will be rejected')
                    return

            # check if the contract is active
            engine = create_engine('sqlite:///system.db', echo=True)
            connection = engine.connect()
            contractDetails = connection.execute(
                'select contractName, contractAddress from activecontracts where status=="active"').fetchall()
            connection.close()
            contractList = []

            counter = 0
            for contract in contractDetails:
                if contract[0] == parsed_data['contractName'] and contract[1] == outputlist[0]:
                    counter = counter + 1

            if counter != 1:
                print('Active Smart contract with the given name doesn\'t exist')
                return

            # Check if the contract has expired
            engine = create_engine('sqlite:///smartContracts/{}-{}.db'.format(parsed_data['contractName'], outputlist[0]), echo=True)
            ContractBase.metadata.create_all(bind=engine)
            session = sessionmaker(bind=engine)()
            result = session.query(ContractStructure).filter_by(attribute='expiryTime').all()
            session.close()
            if result:
                #now parse the expiry time in python
                expirytime = result[0].value.strip()
                expirytime_split = expirytime.split(' ')
                parse_string = '{}/{}/{} {}'.format( expirytime_split[3], parsing.months[expirytime_split[1]], expirytime_split[2], expirytime_split[4])
                expirytime_object = parsing.arrow.get(parse_string, 'YYYY/M/D HH:mm:ss').replace(tzinfo=expirytime_split[5])
                blocktime_object = parsing.arrow.get(blockinfo['time'])

                if blocktime_object > expirytime_object:
                    print('Contract has expired and will not accept any user participation')
                    return


            # Check if exitcondition exists as part of contractstructure and is given in right format
            engine = create_engine('sqlite:///smartContracts/{}-{}.db'.format(parsed_data['contractName'], outputlist[0]), echo=True)
            connection = engine.connect()

            contractAttributes = connection.execute('select attribute, value from contractstructure').fetchall()
            contractAttributes_T = list(zip(*contractAttributes))

            if 'exitconditions' in contractAttributes_T[0]:
                exitconditions = connection.execute('select id,value from contractstructure where attribute=="exitconditions"').fetchall()
                exitconditions_T = list(zip(*exitconditions))
                if parsed_data['userChoice'] not in list(exitconditions_T[1]):
                    print("Wrong userchoice entered\nThis smartContract pariticipation will be rejected")
                    return

            # Check if contractAmount is part of the contract structure, and enforce it if it is
            engine = create_engine('sqlite:///smartContracts/{}-{}.db'.format(parsed_data['contractName'], outputlist[0]), echo=True)
            connection = engine.connect()
            contractAmount = connection.execute('select value from contractstructure where attribute=="contractAmount"').fetchall()
            connection.close()

            if len(contractAmount) != 0:
                if float(contractAmount[0][0]) != float(parsed_data['tokenAmount']):
                    print('Token amount being transferred is not part of the contract structure\nThis transaction will be discarded')
                    return


            # Check if maximum subscription amount has reached
            engine = create_engine('sqlite:///smartContracts/{}-{}.db'.format(parsed_data['contractName'], outputlist[0]), echo=True)
            ContractBase.metadata.create_all(bind=engine)
            session = sessionmaker(bind=engine)()
            result = session.query(ContractStructure).filter_by(attribute='maximumsubscriptionamount').all()
            if result:
                # now parse the expiry time in python
                maximumsubscriptionamount = float(result[0].value.strip())
                amountDeposited = session.query(func.sum(ContractParticipants.tokenAmount)).all()[0][0]

                if amountDeposited is None:
                    amountDeposited = 0

                if amountDeposited >= maximumsubscriptionamount:
                    print('Maximum subscription amount reached\n Money will be refunded')
                    return
                else:
                    if parsed_data['tokenAmount'] + amountDeposited <= maximumsubscriptionamount:
                        # Check if the tokenAmount being transferred exists in the address & do the token transfer
                        returnval = transferToken(parsed_data['tokenIdentification'], parsed_data['tokenAmount'], inputlist[0], outputlist[0])
                        if returnval is not None:
                            # Store participant details in the smart contract's db
                            session.add(ContractParticipants(participantAddress=inputadd, tokenAmount=parsed_data['tokenAmount'], userChoice=parsed_data['userChoice']))
                            session.commit()
                            session.close()

                            # Store a mapping of participant address -> Contract participated in
                            engine = create_engine('sqlite:///system.db', echo=True)
                            SystemBase.metadata.create_all(bind=engine)
                            session = sessionmaker(bind=engine)()
                            session.add(ContractParticipantMapping(participantAddress=inputadd, tokenAmount=parsed_data['tokenAmount'],
                                                             contractName = parsed_data['contractName'], contractAddress = outputlist[0]))
                            session.commit()
                            return

                        else:
                            print("Something went wrong in the smartcontract token transfer method")
                            return
                    else:
                        # Transfer only part of the tokens users specified, till the time it reaches maximumamount
                        returnval = transferToken(parsed_data['tokenIdentification'], maximumsubscriptionamount-amountDeposited,
                                                  inputlist[0], outputlist[0])
                        if returnval is not None:
                            # Store participant details in the smart contract's db
                            session.add(ContractParticipants(participantAddress=inputadd,
                                                             tokenAmount=maximumsubscriptionamount-amountDeposited,
                                                             userChoice=parsed_data['userChoice']))
                            session.commit()
                            session.close()

                            # Store a mapping of participant address -> Contract participated in
                            engine = create_engine('sqlite:///system.db', echo=True)
                            SystemBase.metadata.create_all(bind=engine)
                            session = sessionmaker(bind=engine)()
                            session.add(ContractParticipantMapping(participantAddress=inputadd,
                                                                   tokenAmount=maximumsubscriptionamount-amountDeposited,
                                                                   contractName=parsed_data['contractName'], contractAddress = outputlist[0]))
                            session.commit()
                            session.close()
                            return

                        else:
                            print("Something went wrong in the smartcontract token transfer method")
                            return

            ###############################3
            # Check if the tokenAmount being transferred exists in the address & do the token transfer
            returnval = transferToken(parsed_data['tokenIdentification'], parsed_data['tokenAmount'],
                                      inputlist[0], outputlist[0])
            if returnval is not None:
                # Store participant details in the smart contract's db
                session.add(ContractParticipants(participantAddress=inputadd,
                                                 tokenAmount=parsed_data['tokenAmount'],
                                                 userChoice=parsed_data['userChoice']))
                session.commit()
                session.close()

                # Store a mapping of participant address -> Contract participated in
                engine = create_engine('sqlite:///system.db', echo=True)
                SystemBase.metadata.create_all(bind=engine)
                session = sessionmaker(bind=engine)()
                session.add(ContractParticipantMapping(participantAddress=inputadd,
                                                       tokenAmount=parsed_data['tokenAmount'],
                                                       contractName=parsed_data['contractName'],
                                                       contractAddress=outputlist[0]))
                session.commit()
                return


    # todo Rule 47 - If the parsed data type is token incorporation, then check if the name hasn't been taken already
    #  if it has been taken then reject the incorporation. Else incorporate it
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
        engine = create_engine('sqlite:///system.db', echo=True)
        connection = engine.connect()
        contractDetails = connection.execute('select contractName, contractAddress from activecontracts').fetchall()
        connection.close()

        counter = 0
        # Check if the combination of contract name and address exists
        for contract in contractDetails:
            if contract[0] == parsed_data['contractName'] and contract[1] == parsed_data['contractAddress']:
                counter = counter + 1


        if counter == 0:
            # todo Rule 49 - If the contract name hasn't been taken before, check if the contract type is an authorized type by the system
            if parsed_data['contractType'] == 'one-time-event':
                print("Smart contract is of the type one-time-event")

                # userchoice and payeeAddress conditions cannot come together. Check for it
                if 'userchoices' in parsed_data['contractConditions'] and 'payeeAddress' in parsed_data['contractConditions']:
                    print('Both userchoice and payeeAddress provided as part of the Contract conditions\nIncorporation of Smart Contract with the name {} will be rejected'.format(parsed_data['contractName']))
                    return

                # todo Rule 50 - Contract address mentioned in flodata field should be same as the receiver FLO address on the output side
                #    henceforth we will not consider any flo private key initiated comment as valid from this address
                #    Unlocking can only be done through smart contract system address
                if parsed_data['contractAddress'] == inputadd:
                    dbName = '{}-{}'.format(parsed_data['contractName'], parsed_data['contractAddress'])
                    engine = create_engine('sqlite:///smartContracts/{}.db'.format(dbName), echo=True)
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

                    elif 'payeeAddress' in parsed_data['contractConditions']:
                        # in this case, expirydate( or maximumamount) is the trigger internally. Keep a track of expiry dates
                        session.add(
                            ContractStructure(attribute='payeeAddress', index=0,
                                              value=parsed_data['contractConditions']['payeeAddress']))
                    else:
                        print('Neither userchoice nor payeeAddress provided as part of Smart Contract incorporation of the name {}\n This contract incorporation will be rejected'.format(parsed_data['contractName']))
                        return

                    session.commit()
                    session.close()

                    # Store smart contract address in system's db, to be ignored during future transfers
                    engine = create_engine('sqlite:///system.db', echo=True)
                    SystemBase.metadata.create_all(bind=engine)
                    session = sessionmaker(bind=engine)()
                    session.add(ActiveContracts(contractName=parsed_data['contractName'],
                                                contractAddress=parsed_data['contractAddress'], status='active'))
                    session.commit()
                    session.close()
                else:
                    print('Contract Incorporation rejected as address in Flodata and input address are different')

        else:
            print('Transaction rejected as a smartcontract with same name is active currently')

    elif parsed_data['type'] == 'smartContractPays':
        print('Found a transaction of the type smartContractPays')

        # Check if input address is a committee address
        if inputlist[0] in committeeAddressList:

            # Check if the output address is an active Smart contract address
            engine = create_engine('sqlite:///system.db', echo=True)
            connection = engine.connect()
            # todo : Get only activeContracts which have non-local trigger ie. committee triggers them

            contractDetails = connection.execute('select contractName, contractAddress from activecontracts where status=="active"').fetchall()
            connection.close()
            contractList = []

            counter = 0
            for contract in contractDetails:
                if contract[0] == parsed_data['contractName'] and contract[1] == outputlist[0]:
                    counter = counter + 1

            if counter != 1:
                print('Active Smart contract with the given name doesn\'t exist\n This committee trigger will be rejected')
                return

            # Check if the contract has maximumsubscriptionamount and if it has reached it
            engine = create_engine('sqlite:///smartContracts/{}-{}.db'.format(parsed_data['contractName'], outputlist[0]), echo=True)
            connection = engine.connect()
            # todo : filter activeContracts which only have local triggers
            contractStructure = connection.execute('select * from contractstructure').fetchall()
            contractStructure_T = list(zip(*contractstructure))

            if 'maximumsubscriptionamount' in list(contractStructure_T[1]):
                maximumsubscriptionamount = connection.execute('select value from contractstructure where attribute=="maximumsubscriptionamount"').fetchall()[0][0]
                tokenAmount_sum = connection.execute('select sum(tokenAmount) from contractparticipants').fetchall()[0][0]
                if tokenAmount_sum >= maximumsubscriptionamount:
                    # Trigger the contract
                    contractWinners = connection.execute(
                        'select * from contractparticipants where userChoice="{}"'.format(
                            parsed_data['triggerCondition'])).fetchall()
                    tokenSum = connection.execute('select sum(tokenAmount) from contractparticipants').fetchall()[0][0]
                    winnerSum = connection.execute(
                        'select sum(tokenAmount) from contractparticipants where userChoice="{}"'.format(
                            parsed_data['triggerCondition'])).fetchall()
                    tokenIdentification = connection.execute(
                        'select value from contractstructure where attribute="tokenIdentification"').fetchall()[0][0]
                    connection.close()

                    for winner in contractWinners:
                        returnval = transferToken(tokenIdentification, (winner[2] / winnerSum) * tokenSum,
                                                  outputlist[0], winner[1])
                        if returnval is None:
                            print("CRITICAL ERROR | Something went wrong in the token transfer method while doing local Smart Contract Trigger")
                            return
                    engine = create_engine('sqlite:///system.db', echo=True)
                    connection = engine.connect()
                    connection.execute(
                        'update activecontracts set status="closed" where contractName="{}" and contractAddress="{}"'.format(parsed_data['contractName'], outputlist[0]))
                    connection.close()
                    return


            # Check if contract has passed expiry time
            expiryTime = connection.execute('select value from contractstructure where attibute=="expiryTime"').fetchall()[0][0]
            expirytime_split = expiryTime.split(' ')
            parse_string = '{}/{}/{} {}'.format(expirytime_split[3], parsing.months[expirytime_split[1]],
                                                expirytime_split[2], expirytime_split[4])
            expirytime_object = parsing.arrow.get(parse_string, 'YYYY/M/D HH:mm:ss').replace(
                tzinfo=expirytime_split[5])
            blocktime_object = parsing.arrow.get(blockinfo['time'])
            connection.close()

            if blocktime_object > expirytime_object:
                # Check if the minimum subscription amount has been reached if it exists as part of the structure
                engine = create_engine('sqlite:///smartContracts/{}-{}.db'.format(parsed_data['contractName'], outputlist[0]), echo=True)
                ContractBase.metadata.create_all(bind=engine)
                session = sessionmaker(bind=engine)()
                result = session.query(ContractStructure).filter_by(attribute='minimumsubscriptionamount').all()
                session.close()
                if result:
                    minimumsubscriptionamount = float(result[0].value.strip())
                    engine = create_engine('sqlite:///smartContracts/{}-{}.db'.format(parsed_data['contractName'], outputlist[0]),
                                           echo=True)
                    ContractBase.metadata.create_all(bind=engine)
                    session = sessionmaker(bind=engine)()
                    result = session.query(ContractStructure).filter_by(attribute='minimumsubscriptionamount').all()
                    amountDeposited = session.query(func.sum(ContractParticipants.tokenAmount)).all()[0][0]
                    session.close()

                    if amountDeposited is None:
                        amountDeposited = 0

                    if amountDeposited < minimumsubscriptionamount:
                        print('Minimum subscription amount hasn\'t been reached\n The token will be returned back')
                        # Initialize payback to contract participants
                        engine = create_engine('sqlite:///smartContracts/{}-{}.db'.format(parsed_data['contractName'], outputlist[0]),
                                               echo=True)
                        connection = engine.connect()
                        contractParticipants = connection.execute(
                            'select participantAddress, tokenAmount from contractparticipants').fetchall()[0][0]

                        for participant in contractParticipants:
                            tokenIdentification = connection.execute(
                                'select * from contractstructure where attribute="tokenIdentification"').fetchall()[0][
                                0]
                            contractAddress = connection.execute(
                                'select * from contractstructure where attribute="contractAddress"').fetchall()[0][0]
                            returnval = transferToken(tokenIdentification, participant[1], contractAddress,
                                                      participant[0])
                            if returnval is None:
                                print(
                                    "CRITICAL ERROR | Something went wrong in the token transfer method while doing local Smart Contract Trigger")
                                return
                            engine = create_engine('sqlite:///system.db', echo=True)
                            connection = engine.connect()
                            connection.execute(
                                'update activecontracts set status="closed" where contractName="{}" and contractAddress="{}"'.format(
                                    parsed_data['contractName'], outputlist[0]))
                            connection.close()
                        return

                engine = create_engine('sqlite:///smartContracts/{}-{}.db'.format(parsed_data['contractName'], outputlist[0]), echo=True)
                connection = engine.connect()
                contractWinners = connection.execute('select * from contractparticipants where userChoice="{}"'.format(parsed_data['triggerCondition'])).fetchall()
                tokenSum = connection.execute('select sum(tokenAmount) from contractparticipants').fetchall()[0][0]
                winnerSum = connection.execute('select sum(tokenAmount) from contractparticipants where userChoice="{}"'.format(parsed_data['triggerCondition'])).fetchall()
                tokenIdentification = connection.execute('select value from contractstructure where attribute="tokenIdentification"').fetchall()[0][0]
                connection.close()

                for winner in contractWinners:
                    returnval = transferToken(tokenIdentification, (winner[2]/winnerSum)*tokenSum, outputlist[0], winner[1])
                    if returnval is None:
                        print(
                            "CRITICAL ERROR | Something went wrong in the token transfer method while doing local Smart Contract Trigger")
                        return
                engine = create_engine('sqlite:///system.db', echo=True)
                connection = engine.connect()
                connection.execute(
                    'update activecontracts set status="closed" where contractName="{}" and contractAddress="{}"'.format(
                        parsed_data['contractName'], outputlist[0]))
                connection.close()
        else:
            print('Input address is not part of the committee address list. This trigger is rejected')



# todo Rule 1 - Read command line arguments to reset the databases as blank
#  Rule 2     - Read config to set testnet/mainnet
#  Rule 3     - Set flo blockexplorer location depending on testnet or mainnet
#  Rule 4     - Set the local flo-cli path depending on testnet or mainnet
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
startblock = int(session.query(SystemData).filter_by(attribute='lastblockscanned').all()[0].value) + 1
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

    if blockindex == 606098:
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
        text = text.replace("\n"," \n ")

    # todo Rule 9 - Reject all noise transactions. Further rules are in parsing.py

        parsed_data = parsing.parse_flodata(text, blockinfo)
        if parsed_data['type'] != 'noise':
            print(blockindex)
            print(parsed_data['type'])
            startWorking(transaction_data, parsed_data, blockinfo)

    engine = create_engine('sqlite:///system.db')
    SystemBase.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    entry = session.query(SystemData).filter(SystemData.attribute == 'lastblockscanned').all()[0]
    entry.value = str(blockindex)
    session.commit()
    session.close()

    # Check smartContracts which will be triggered locally, and not by the contract committee
    checkLocaltriggerContracts(blockinfo)

