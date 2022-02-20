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
from ast import literal_eval 
import pdb 
from models import SystemData, ActiveTable, ConsumedTable, TransferLogs, TransactionHistory, RejectedTransactionHistory, Base, ContractStructure, ContractBase, ContractParticipants, SystemBase, ActiveContracts, ContractAddressMapping, LatestCacheBase, ContractTransactionHistory, RejectedContractTransactionHistory, TokenContractAssociation, ContinuosContractBase, ContractStructure1, ContractParticipants1, ContractDeposits1, ContractTransactionHistory1, DatabaseTypeMapping, TimeActions


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


contract_session = create_database_session_orm('smart_contract', {'contract_name':f"swap-rupee-bioscope", 'contract_address':f"oRRCHWouTpMSPuL6yZRwFCuh87ZhuHoL78"}, ContractBase)

pdb.set_trace()