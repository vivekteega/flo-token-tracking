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
        pass


connection = create_database_connection('token', {'token_name':"rupee"})
print(check_database_existence('token', {'token_name':"rupee"}))