from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Float, String, ForeignKey

Base = declarative_base()
ContractBase = declarative_base()
SystemBase = declarative_base()

class ActiveTable(Base):
    __tablename__ = "activeTable"

    id = Column('id', Integer, primary_key=True)
    address = Column('address', String)
    parentid = Column('parentid', Integer)
    consumedpid = Column('consumedpid', String)
    transferBalance = Column('transferBalance', Float)

class ConsumedTable(Base):
    __tablename__ = "consumedTable"

    primaryKey = Column('primaryKey', Integer, primary_key=True)
    id = Column('id', Integer)
    address = Column('address', String)
    parentid = Column('parentid', Integer)
    consumedpid = Column('consumedpid', String)
    transferBalance = Column('transferBalance', Float)

class TransferLogs(Base):
    __tablename__ = "transferlogs"

    primary_key = Column('id', Integer, primary_key=True)
    sourceFloAddress = Column('sourceFloAddress', String)
    destFloAddress = Column('destFloAddress', String)
    transferAmount = Column('transferAmount', Float)
    sourceId = Column('sourceId', Integer)
    destinationId = Column('destinationId', Integer)
    blockNumber = Column('blockNumber', Integer)
    time = Column('time', Integer)
    transactionHash = Column('transactionHash', String)

class TransactionHistory(Base):
    __tablename__ = "transactionHistory"

    primary_key = Column('id', Integer, primary_key=True)
    sourceFloAddress = Column('sourceFloAddress', String)
    destFloAddress = Column('destFloAddress', String)
    transferAmount = Column('transferAmount', Float)
    blockNumber = Column('blockNumber', Integer)
    time = Column('time', Integer)
    transactionHash = Column('transactionHash', String)
    blockchainReference = Column('blockchainReference', String)

class ContractStructure(ContractBase):
    __tablename__ = "contractstructure"

    id = Column('id', Integer, primary_key=True)
    attribute = Column('attribute', String)
    index = Column('index', Integer)
    value = Column('value', String)

class ContractParticipants(ContractBase):
    __tablename__ = "contractparticipants"

    id = Column('id', Integer, primary_key=True)
    participantAddress = Column('participantAddress', String)
    tokenAmount = Column('tokenAmount', Float)
    userChoice = Column('userChoice', String)

class ActiveContracts(SystemBase):
    __tablename__ = "activecontracts"

    id = Column('id', Integer, primary_key=True)
    contractName = Column('contractName', String)
    contractAddress = Column('contractAddress', String)
    status = Column('status', String)

class SystemData(SystemBase):
    __tablename__ = "systemData"

    id = Column('id', Integer, primary_key=True)
    attribute = Column('attribute', String)
    value = Column('value', String)

class ContractParticipantMapping(SystemBase):
    __tablename__ = "contractParticipantMapping"

    id = Column('id', Integer, primary_key=True)
    participantAddress = Column('participantAddress', String)
    contractName = Column('contractName', String)
    contractAddress = Column('contractAddress', String)
    tokenAmount = Column('tokenAmount', Float)


