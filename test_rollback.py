import argparse 
from sqlalchemy import create_engine, func 
from sqlalchemy.orm import sessionmaker 
from models import SystemData, ActiveTable, ConsumedTable, TransferLogs, TransactionHistory, RejectedTransactionHistory, Base, ContractStructure, ContractBase, ContractParticipants, SystemBase, ActiveContracts, ContractAddressMapping, LatestCacheBase, ContractTransactionHistory, RejectedContractTransactionHistory, TokenContractAssociation, ContinuosContractBase, ContractStructure1, ContractParticipants1, ContractDeposits1, ContractTransactionHistory1, LatestTransactions, LatestBlocks, DatabaseTypeMapping, TokenAddressMapping 
from ast import literal_eval 
import os 
import json 
import logging 
import pdb 
import sys 

apppath = os.path.dirname(os.path.realpath(__file__))

# helper functions
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


def inspect_parsed_flodata(parsed_flodata, inputAddress, outputAddress):
    if parsed_flodata['type'] == 'transfer':
        if parsed_flodata['transferType'] == 'token':
            return {'type':'tokentransfer', 'token_db':f"{parsed_flodata['tokenIdentification']}", 'token_amount':f"{parsed_flodata['tokenAmount']}"}
    if parsed_flodata['type'] == 'tokenIncorporation':
        return {'type':'tokenIncorporation', 'token_db':f"{parsed_flodata['tokenIdentification']}", 'token_amount':f"{parsed_flodata['tokenAmount']}"}
    if parsed_flodata['type'] == 'smartContractPays':
        # contract address, token | both of them come from 
        sc_session = create_database_session_orm('smart_contract', {'contract_name':f"{parsed_flodata['contractName']}", 'contract_address':f"{outputAddress}"}, ContractBase)
        token_db = sc_session.query(ContractStructure.value).filter(ContractStructure.attribute=='tokenIdentification').first()[0]
        return {'type':'smartContractPays', 'token_db':f"{token_db}" , 'contract_db':f"{parsed_flodata['contractName']}-{outputAddress}", 'triggerCondition':f"{parsed_flodata['triggerCondition']}"}

'''
Steps to do the rollback 

1. Find out the transaction details from transaction history table ie. inputAddress, 
2. Find out the last entry from the activeTable 
3. Parse pid and consumedpids from the entry 
4. For each consumedpid number, pull put database entry from the consumedtable and then add to activeTable 
    4.1. After adding the database entry back, add consumedpid number's value to transferBalance of the entry
    4.2. What will happen to addressBalance?
    4.3. 
'''


def undo_last_single_transaction():
    consumedpid_entry = db_session.query(ConsumedTable).filter(ConsumedTable.id == key).all()
    newTransferBalance = consumedpid_entry[0].transferBalance + consumedpid[key]
    db_session.add(ActiveTable(id=consumedpid_entry[0].id, address=consumedpid_entry[0].address, consumedpid=consumedpid_entry[0].consumedpid, transferBalance=newTransferBalance, addressBalance = consumedpid_entry[0].addressBalance))
    db_session.commit()


def calc_pid_amount(transferBalance, consumedpid):
    consumedpid_sum = 0
    for key in list(consumedpid.keys()):
        consumedpid_sum = consumedpid_sum + float(consumedpid[key])
    return transferBalance - consumedpid_sum


def find_addressBalance_from_floAddress(database_session, floAddress):
    query_output = database_session.query(ActiveTable).filter(ActiveTable.address==floAddress, ActiveTable.addressBalance!=None).first()
    if query_output is None:
        return 0
    else:
        return query_output.addressBalance


def rollback_address_balance_processing(db_session, senderAddress, receiverAddress, transferBalance):
    # Find out total sum of address
    # Find out the last entry where address balance is not null, if exists make it null 
    
    # Calculation phase 
    current_receiverBalance = find_addressBalance_from_floAddress(db_session, receiverAddress)
    current_senderBalance = find_addressBalance_from_floAddress(db_session ,senderAddress)
    new_receiverBalance = current_receiverBalance - transferBalance
    new_senderBalance = current_senderBalance + transferBalance

    # Insertion phase 
    # if new receiver balance is 0, then only insert sender address balance 
    # if receiver balance is not 0, then update previous occurence of the receiver address and sender balance 
    # for sender, find out weather the last occurence of senderfloid has an addressBalance 
    # either query out will not come or the last occurence will have address
    # for sender, in all cases we will update the addressBalance of last occurences of senderfloaddress
    # for receiver, if the currentaddressbalance is 0 then do nothing .. and if the currentaddressbalance is not 0 then update the last occurence of receiver address 

    sender_query = db_session.query(ActiveTable).filter(ActiveTable.address==senderAddress).order_by(ActiveTable.id.desc()).first()
    sender_query.addressBalance = new_senderBalance

    if new_receiverBalance != 0 and new_receiverBalance > 0:
        receiver_query = db_session.query(ActiveTable).filter(ActiveTable.address==receiverAddress).order_by(ActiveTable.id.desc()).limit(2)
        receiver_query[1].addressBalance = new_receiverBalance


def undo_smartContractPays(tokenIdentification, inputAddress, outputAddress, transaction_data):
    # Token database 
    '''
        * rollback each pid transaction 
        * the addressBalance will have to be calculated after each loop, NOT at the end of the loop 
    '''
    tokendb_session = create_database_session_orm('token', {'token_name':tokenIdentification}, Base)
    transaction_history_entry = tokendb_session.query(TransactionHistory).filter(TransactionHistory.transactionHash == transaction_data.transactionHash).order_by(TransactionHistory.blockNumber.desc()).all()

    active_table_last_entries = tokendb_session.query(ActiveTable).order_by(ActiveTable.id.desc()).limit(len(transaction_history_entry))
    pdb.set_trace()

    # Smart Contract database
    '''
        * 
    '''
    print('')


def undo_transferToken(tokenIdentification, tokenAmount, inputAddress, outputAddress, transaction_data):
    # Connect to database
    db_session = create_database_session_orm('token', {'token_name':tokenIdentification}, Base)
    transaction_history_entry = db_session.query(TransactionHistory).filter(TransactionHistory.transactionHash == transaction_data.transactionHash).order_by(TransactionHistory.blockNumber.desc()).all()

    active_table_last_entries = db_session.query(ActiveTable).order_by(ActiveTable.id.desc()).limit(len(transaction_history_entry))
    
    for idx, activeTable_entry in enumerate(active_table_last_entries):
        # Find out consumedpid and partially consumed pids 
        parentid = None 
        orphaned_parentid = None 
        consumedpid = None 
        if activeTable_entry.parentid is not None:
            parentid = activeTable_entry.parentid
        if activeTable_entry.orphaned_parentid is not None:
            orphaned_parentid = activeTable_entry.orphaned_parentid
        if activeTable_entry.consumedpid is not None:
            consumedpid = literal_eval(activeTable_entry.consumedpid)

        # filter out based on consumped pid and partially consumed pids 
        if parentid is not None:
            # find query in activeTable with the parentid
            activeTable_pid_entry = db_session.query(ActiveTable).filter(ActiveTable.id == parentid).all()[0]
            # calculate the amount taken from parentid 
            activeTable_pid_entry.transferBalance = activeTable_pid_entry.transferBalance + calc_pid_amount(activeTable_entry.transferBalance, consumedpid)

        if consumedpid != {}:
            # each key of the pid is totally consumed and with its corresponding value written in the end 
            # how can we maintain the order of pid consumption? The bigger pid number will be towards the end 
            # 1. pull the pid number and its details from the consumedpid table 
            for key in list(consumedpid.keys()):
                consumedpid_entry = db_session.query(ConsumedTable).filter(ConsumedTable.id == key).all()[0]
                newTransferBalance = consumedpid_entry.transferBalance + consumedpid[key]
                db_session.add(ActiveTable(id=consumedpid_entry.id, address=consumedpid_entry.address, parentid=consumedpid_entry.parentid ,consumedpid=consumedpid_entry.consumedpid, transferBalance=newTransferBalance, addressBalance = None))
                db_session.delete(consumedpid_entry)

                orphaned_parentid_entries = db_session.query(ActiveTable).filter(ActiveTable.orphaned_parentid == key).all()
                for orphan_entry in orphaned_parentid_entries:
                    orphan_entry.parentid = orphan_entry.orphaned_parentid
                    orphan_entry.orphaned_parentid = None

        # update addressBalance 
        rollback_address_balance_processing(db_session, inputAddress, outputAddress, transaction_history_entry[idx].transferAmount)

        # delete operations 
        # delete the last row in activeTable and transactionTable 
        db_session.delete(activeTable_entry)
        db_session.delete(transaction_history_entry[idx])

    db_session.commit()


def find_input_output_addresses(transaction_data):
    # Create vinlist and outputlist
    vinlist = []
    querylist = []
    
    for vin in transaction_data["vin"]:
        vinlist.append([vin["addr"], float(vin["value"])])

    totalinputval = float(transaction_data["valueIn"])

    # todo Rule 41 - Check if all the addresses in a transaction on the input side are the same
    for idx, item in enumerate(vinlist):
        if idx == 0:
            temp = item[0]
            continue
        if item[0] != temp:
            print(f"System has found more than one address as part of vin. Transaction {transaction_data['txid']} is rejected")
            return 0

    inputlist = [vinlist[0][0], totalinputval]
    inputadd = vinlist[0][0]

    # todo Rule 42 - If the number of vout is more than 2, reject the transaction
    if len(transaction_data["vout"]) > 2:
        print(f"System has found more than 2 address as part of vout. Transaction {transaction_data['txid']} is rejected")
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
        print(f"Transaction's change is not coming back to the input address. Transaction {transaction_data['txid']} is rejected")
        return 0
    else:
        outputlist = outputlist[0]

    input_output_list = [inputlist, outputlist]
    return input_output_list


def delete_token_database(token_name):
    dirpath = os.path.join(apppath, 'tokens', f"{token_name}.db")
    if os.path.exists(dirpath):
        os.remove(dirpath)


def perform_rollback(transaction):
    latestCache = create_database_session_orm('system_dbs', {'db_name': 'latestCache'}, LatestCacheBase)
    # categorize transaction and find out the databases it will affect 
    transaction_data = json.loads(transaction.jsonData) 
    input_output_list = find_input_output_addresses(transaction_data) 
    inputAddress = input_output_list[0][0] 
    outputAddress = input_output_list[1][0] 
    parsed_flodata = literal_eval(transaction.parsedFloData) 
    inspected_flodata = inspect_parsed_flodata(parsed_flodata, inputAddress, outputAddress)
    
    if inspected_flodata['type'] == 'tokentransfer':
        # undo the transaction in token database
        undo_transferToken(inspected_flodata['token_db'], inspected_flodata['token_amount'], inputAddress, outputAddress, transaction) 
    elif inspected_flodata['type'] == 'tokenIncorporation':
        # note - if you want you can do checks to make sure the database has only 1 entry 
        # delete the token database
        delete_token_database(inspected_flodata['token_db'])
    elif inspected_flodata['type'] == 'smartContractPays':
        undo_smartContractPays(inspected_flodata[''], inputAddress, outputAddress, transaction_data)
    else:
        print("Transaction not in any inspected_flodata category until now.. Exiting")
        sys.exit(0)


# Take input from user reg how many blocks to go back in the blockchain
parser = argparse.ArgumentParser(description='Script tracks RMT using FLO data on the FLO blockchain - https://flo.cash') 
parser.add_argument('-b', '--toblocknumer', nargs='?', type=int, help='Rollback the script to the specified block number') 
parser.add_argument('-n', '--blockcount', nargs='?', type=int, help='Rollback the script to the number of blocks specified') 
args = parser.parse_args() 


# Get all the transaction and blockdetails from latestCache reg the transactions in the block
systemdb_session = create_database_session_orm('system_dbs', {'db_name': 'system'}, SystemBase) 
lastscannedblock = systemdb_session.query(SystemData.value).filter(SystemData.attribute=='lastblockscanned').first() 
systemdb_session.close() 
lastscannedblock = int(lastscannedblock.value) 


#number_blocks_to_rollback = 1754000
if (args.blockcount and args.toblocknumber):
    print("You can only specify one of the options -b or -c")
    sys.exit(0)
elif args.blockcount:
    rollback_block = lastscannedblock - args.blockcount
elif args.toblocknumer:
    rollback_block = args.toblocknumer
else:
    print("Please specify the number of blocks to rollback")
    sys.exit(0)
    

latestcache_session = create_database_session_orm('system_dbs', {'db_name': 'latestCache'}, LatestCacheBase) 
latestBlocks = latestcache_session.query(LatestBlocks).filter(LatestBlocks.blockNumber >= rollback_block).all() 
lblocks_dict = {}
blocknumber_list = []
for block in latestBlocks:
    block_dict = block.__dict__
    lblocks_dict[block_dict['blockNumber']] = {'blockHash':f"{block_dict['blockHash']}", 'jsonData':f"{block_dict['jsonData']}"}
    blocknumber_list.insert(0,block_dict['blockNumber'])


# Rollback block will be excluded 
for blockindex in blocknumber_list:
 #   if blockindex >= rollback_block:'''
#for blockindex in range(lastscannedblock, rollback_block, -1):
    # Find the all the transactions that happened in this block 
    print(blockindex)
    try:
        block_tx_hashes = json.loads(lblocks_dict[str(blockindex)]['jsonData'])['tx']
    except:
        print(f"Block {blockindex} is not found in latestCache. Skipping this block")
        continue
    
    print("Block tx hashes")
    print(block_tx_hashes)

    if 'b57cf412c8cb16e473d04bae44214705c64d2c25146be22695bf1ac36e166ee0' in block_tx_hashes:
        pdb.set_trace()

    for tx in block_tx_hashes:
        transaction = latestcache_session.query(LatestTransactions).filter(LatestTransactions.transactionHash == tx).all()
        print(transaction) 
        if len(transaction) == 1:
            perform_rollback(transaction[0]) 
        latestcache_session.delete(transaction[0]) 
    
    # delete latestBlocks entry
    block_entry = latestcache_session.query(LatestBlocks).filter(LatestBlocks.blockNumber == blockindex).first()
    latestcache_session.delete(block_entry)

    # delete activeContracts, contractAddressMapping, DatabaseAddressMapping, rejectedContractTransactionHistory, rejectedTransactionHistory, tokenAddressMapping
    systemdb_session = create_database_session_orm('system_dbs', {'db_name': 'system'}, SystemBase)
    activeContracts_session = systemdb_session.query(ActiveContracts).filter(ActiveContracts.blockNumber==blockindex).all()
    contractAddressMapping_queries = systemdb_session.query(ContractAddressMapping).filter(ContractAddressMapping.blockNumber==blockindex).all()
    databaseTypeMapping_queries = systemdb_session.query(DatabaseTypeMapping).filter(DatabaseTypeMapping.blockNumber==blockindex).all()
    rejectedContractTransactionHistory_queries = systemdb_session.query(RejectedContractTransactionHistory).filter(RejectedContractTransactionHistory.blockNumber==blockindex).all()
    rejectedTransactionHistory_queries = systemdb_session.query(RejectedTransactionHistory).filter(RejectedTransactionHistory.blockNumber==blockindex).all()
    tokenAddressMapping_queries = systemdb_session.query(TokenAddressMapping).filter(TokenAddressMapping.blockNumber==blockindex).all()
    
    for dbentry in activeContracts_session:
        systemdb_session.delete(dbentry)

    for dbentry in contractAddressMapping_queries:
        systemdb_session.delete(dbentry)
    
    for dbentry in databaseTypeMapping_queries:
        systemdb_session.delete(dbentry)
    
    for dbentry in rejectedContractTransactionHistory_queries:
        systemdb_session.delete(dbentry)

    for dbentry in rejectedTransactionHistory_queries:
        systemdb_session.delete(dbentry)

    for dbentry in tokenAddressMapping_queries:
        systemdb_session.delete(dbentry)
    
    systemdb_session.query(SystemData).filter(SystemData.attribute=='lastblockscanned').update({SystemData.value:str(blockindex)})

    latestcache_session.commit()
    systemdb_session.commit()
    latestcache_session.close()
    systemdb_session.close()
