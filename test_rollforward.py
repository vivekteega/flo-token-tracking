from sqlalchemy import create_engine, func 
from sqlalchemy.orm import sessionmaker 
from models import SystemData, ActiveTable, ConsumedTable, TransferLogs, TransactionHistory, RejectedTransactionHistory, Base, ContractStructure, ContractBase, ContractParticipants, SystemBase, ActiveContracts, ContractAddressMapping, LatestCacheBase, ContractTransactionHistory, RejectedContractTransactionHistory, TokenContractAssociation, ContinuosContractBase, ContractStructure1, ContractParticipants1, ContractDeposits1, ContractTransactionHistory1, LatestTransactions, LatestBlocks, DatabaseTypeMapping 
import json 
from tracktokens_smartcontracts import processTransaction, processBlock 
import os 
import logging 
import argparse 
import configparser 
import pdb 
import shutil 
import sys 


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
parser.add_argument('-r', '--reset', nargs='?', const=1, type=int, help='Purge existing db and rebuild it from scratch')
parser.add_argument('-rb', '--rebuild', nargs='?', const=1, type=int, help='Rebuild it')
parser.add_argument('-f', '--forwardblock', nargs='?', type=int, help='Forward block number')
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


'''# Initialize latest cache DB
session = create_database_session_orm('system_dbs', {'db_name': "latestCache"}, LatestCacheBase)
session.commit()
session.close() 

# get all blocks and transaction data 
latestCache_session = create_database_session_orm('system_dbs', {'db_name':'latestCache1'}, LatestCacheBase)
lblocks = latestCache_session.query(LatestBlocks).all()
ltransactions = latestCache_session.query(LatestTransactions).all()
latestCache_session.close()

lblocks_dict = {}
for block in lblocks:
    block_dict = block.__dict__
    lblocks_dict[block_dict['blockNumber']] = {'blockHash':f"{block_dict['blockHash']}", 'jsonData':f"{block_dict['jsonData']}"}

# process and rebuild all transactions 
for transaction in ltransactions:
    transaction_dict = transaction.__dict__
    transaction_data = json.loads(transaction_dict['jsonData'])
    parsed_flodata = json.loads(transaction_dict['parsedFloData'])
    block_info = json.loads(lblocks_dict[transaction_dict['blockNumber']]['jsonData'])
    processTransaction(transaction_data, parsed_flodata, block_info)

# copy the old block data 
old_latest_cache = create_database_connection('system_dbs', {'db_name':'latestCache1'})
old_latest_cache.execute("ATTACH DATABASE 'latestCache.db' AS new_db")
old_latest_cache.execute("INSERT INTO new_db.latestBlocks SELECT * FROM latestBlocks")
old_latest_cache.close()

# delete 
# system.db , latestCache.db, smartContracts, tokens 
if os.path.isfile('./system1.db'):
    os.remove('system1.db')
if os.path.isfile('./latestCache1.db'):
    os.remove('latestCache1.db')
if os.path.isfile('./smartContracts1'):
    shutil.rmtree('smartContracts1')
if os.path.isfile('./tokens1'):
    shutil.rmtree('tokens1')
    '''

# Read start block no
session = create_database_session_orm('system_dbs', {'db_name': "system"}, SystemBase)
startblock = int(session.query(SystemData).filter_by(attribute='lastblockscanned').all()[0].value) + 1
session.commit()
session.close()

for blockindex in range(startblock, args.forwardblock):
    processBlock(blockindex=blockindex) 

    # Update system.db's last scanned block 
    connection = create_database_connection('system_dbs', {'db_name': "system"})
    connection.execute(f"UPDATE systemData SET value = {blockindex} WHERE attribute = 'lastblockscanned';")
    connection.close()