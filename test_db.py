import argparse 
import configparser 
import json 
import logging 
import os 
import shutil 
import sys 
import pyflo 
import requests 
import socketio 
from sqlalchemy import create_engine, func 
from sqlalchemy.orm import sessionmaker 
import time 
import arrow 
import parsing 
from config import * 
from datetime import datetime 
from ast import literal_eval 
from models import SystemData, TokenBase, ActiveTable, ConsumedTable, TransferLogs, TransactionHistory, TokenContractAssociation, RejectedTransactionHistory, ContractBase, ContractStructure, ContractParticipants, ContractTransactionHistory, ContractDeposits, ConsumedInfo, ContractWinners, ContinuosContractBase, ContractStructure2, ContractParticipants2, ContractDeposits2, ContractTransactionHistory2, SystemBase, ActiveContracts, SystemData, ContractAddressMapping, TokenAddressMapping, DatabaseTypeMapping, TimeActions, RejectedContractTransactionHistory, RejectedTransactionHistory, LatestCacheBase, LatestTransactions, LatestBlocks
from statef_processing import process_stateF 
import pdb 

# Configuration of required variables 
config = configparser.ConfigParser()
config.read('config.ini')

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')
file_handler = logging.FileHandler(os.path.join(config['DEFAULT']['DATA_PATH'],'tracking.log'))
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(stream_handler)

def create_database_connection(type, parameters):
    if type == 'token':
        path = os.path.join(config['DEFAULT']['DATA_PATH'], 'tokens', f"{parameters['token_name']}.db")
        engine = create_engine(f"sqlite:///{path}", echo=True)
    elif type == 'smart_contract':
        path = os.path.join(config['DEFAULT']['DATA_PATH'], 'smartContracts', f"{parameters['contract_name']}-{parameters['contract_address']}.db")
        engine = create_engine(f"sqlite:///{path}", echo=True)
    elif type == 'system_dbs':
        path = os.path.join(config['DEFAULT']['DATA_PATH'], f"system.db")
        engine = create_engine(f"sqlite:///{path}", echo=False)
    elif type == 'latest_cache':
        path = os.path.join(config['DEFAULT']['DATA_PATH'], f"latestCache.db")
        engine = create_engine(f"sqlite:///{path}", echo=False)

    connection = engine.connect()
    return connection


def create_database_session_orm(type, parameters, base):
    if type == 'token':
        path = os.path.join(config['DEFAULT']['DATA_PATH'], 'tokens', f"{parameters['token_name']}.db")
        engine = create_engine(f"sqlite:///{path}", echo=True)
        base.metadata.create_all(bind=engine)
        session = sessionmaker(bind=engine)()

    elif type == 'smart_contract':
        path = os.path.join(config['DEFAULT']['DATA_PATH'], 'smartContracts', f"{parameters['contract_name']}-{parameters['contract_address']}.db")
        engine = create_engine(f"sqlite:///{path}", echo=True)
        base.metadata.create_all(bind=engine)
        session = sessionmaker(bind=engine)()

    elif type == 'system_dbs':
        path = os.path.join(config['DEFAULT']['DATA_PATH'], f"{parameters['db_name']}.db")
        engine = create_engine(f"sqlite:///{path}", echo=False)
        base.metadata.create_all(bind=engine)
        session = sessionmaker(bind=engine)()
    
    return session


# Connect to system.db with a session 
systemdb_session = create_database_session_orm('system_dbs', {'db_name':'system1'}, SystemBase)
contract_ids = systemdb_session.query(func.max(TimeActions.id)).group_by(TimeActions.contractName, TimeActions.contractAddress).all()
time = systemdb_session.query(TimeActions).filter(TimeActions.id.in_(contract_ids[0])).all()
#SELECT contractName, status FROM time_actions WHERE id IN (RESULT) AND status='active';

pdb.set_trace()
#active_contracts = systemdb_session.query(TimeActions).group_by(TimeActions.contractName, TimeActions.contractAddress).all()
#timeactions_tx_hashes = []
#activeContracts = systemdb_session.query(ActiveContracts).all()

#SELECT contractName, status FROM time_actions WHERE id IN (SELECT max(id) FROM time_actions GROUP BY contractName, contractAddress) AND status='active';
