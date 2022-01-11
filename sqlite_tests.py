from sqlalchemy import create_engine, func
import pdb
import os 

def create_database_connection(type, parameters):
    if type == 'token':
        engine = create_engine(f"sqlite:///tokens/{parameters['token_name']}.db", echo=True)
        connection = engine.connect()
        return connection
    if type == 'smart_contract':
        pass


def check_database_existence(type, parameters):
    if type == 'token':
        return os.path.isfile(f"./tokens/{parameters['token_name']}.db")

    if type == 'smart_contract':
        return os.path.isfile(f"./smartContracts/{parameters['contract_name']}-{parameters['contract_address']}.db")


print(check_database_existence('smart_contract', {'contract_name': f"india-elections-2019", 'contract_address': f"F7osBpjDDV1mSSnMNrLudEQQ3cwDJ2dPR1"}))