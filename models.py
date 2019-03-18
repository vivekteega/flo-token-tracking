from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Float, String, ForeignKey

Base = declarative_base()
ContractBase = declarative_base()

class Extra(Base):
    __tablename__ = "extra"

    id = Column('id', Integer, primary_key=True)
    lastblockscanned = Column('lastblockscanned', Integer)

class TransactionHistory(Base):
    __tablename__ = "transactionhistory"

    id = Column('id', Integer, primary_key=True)
    blockno = Column('blockno', Integer)
    fromAddress = Column('fromAddress', String)
    toAddress = Column('toAddress', String)
    amount = Column('amount', Float)
    blockchainReference = Column('blockchainReference', String)

class TransactionTable(Base):
    __tablename__ = "transactiontable"

    id = Column('id', Integer, primary_key=True)
    address = Column('address', String)
    parentid = Column('parentid', Integer)
    transferBalance = Column('transferBalance', Float)

class TransferLogs(Base):
    __tablename__ = "transferlogs"

    id = Column('id', Integer, primary_key=True)
    primaryIDReference = Column('primaryIDReference', Integer)
    transferDescription = Column('transferDescription', String)
    transferIDConsumed = Column('transferIDConsumed', Integer)
    blockchainReference = Column('blockchainReference', String)

class Webtable(Base):
    __tablename__ = "webtable"

    id = Column('id', Integer, primary_key=True)
    transferDescription = Column('transferDescription', String)
    blockchainReference = Column('blockchainReference', String)

class ContractStructure(ContractBase):
    __tablename__ = "contractstructure"

    id = Column('id', Integer, primary_key=True)
    attribute = Column('attribute', String)
    index = Column('index', Integer)
    value = Column('value', String)


