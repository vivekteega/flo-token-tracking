# Noise categorization 
parsed_data = {'type': 'noise'}


# Token incorporation
flodata="create 10 million "
parsed_data = {
    'type': 'tokenIncorporation', 
    'flodata': string, 
    'tokenIdentification': hashList[0][:-1], 
    'tokenAmount': initTokens
    }

'''
    one # | create/start/incorporate keyword | integer or float number 
'''


# Token transfer 
parsed_data = {
    'type': 'transfer', 
    'transferType': 'token', 
    'flodata': string,
    'tokenIdentification': hashList[0][:-1],
    'tokenAmount': amount
    }

'''
    one # | send/give/transfer keyword | integer or float number 
'''


# Smart Contract Incorporation - One time event - with userchoice 
parsed_data = {
    'type': 'smartContractIncorporation', 
    'contractType': 'one-time-event',
    'tokenIdentification': hashList[0][:-1], 
    'contractName': atList[0][:-1],
    'contractAddress': contractaddress[:-1], 
    'flodata': string,
    'contractConditions': {
        'contractamount' : ,
        'minimumsubscriptionamount' : ,
        'maximumsubscriptionamount' : ,
        'payeeaddress' : ,
        'userchoice' : ,
        'expiryTime' : 
    }
}


# Smart Contract Participation - one time event - userchoice  
parsed_data = {
    'type': 'transfer', 
    'transferType': 'smartContract', 
    'flodata': string,
    'tokenIdentification': hashList[0][:-1],
    'operation': 'transfer', 
    'tokenAmount': amount, 
    'contractName': atList[0][:-1],
    'userChoice': userChoice
    }


# Smart Contract Trigger - one time event - userchoice 
parsed_data = {
    'type': 'smartContractPays', 
    'contractName': atList[0][:-1], 
    'triggerCondition': triggerCondition.group().strip()[1:-1]
    }


# Smart Contract Incorporation - One time event - with time as trigger  
parsed_data = {
    'type': 'smartContractIncorporation', 
    'contractType': 'one-time-event',
    'tokenIdentification': hashList[0][:-1], 
    'contractName': atList[0][:-1],
    'contractAddress': contractaddress[:-1], 
    'flodata': string,
    'contractConditions': {
        'contractamount' : ,
        'minimumsubscriptionamount' : ,
        'maximumsubscriptionamount' : ,
        'payeeaddress' : ,
        'expiryTime' : 
    }
}


# Smart Contract Participation - one time event - time trigger  
parsed_data = {
    'type': 'transfer', 
    'transferType': 'smartContract', 
    'flodata': string,
    'tokenIdentification': hashList[0][:-1],
    'operation': 'transfer', 
    'tokenAmount': amount, 
    'contractName': atList[0][:-1]
    }


# Smart Contract Incorporation - Continuos event - Token swap 
parsed_data = {
    'type': 'smartContractIncorporation', 
    'contractType': 'continuos-event',
    'tokenIdentification': hashList[0][:-1], 
    'contractName': atList[0][:-1],
    'contractAddress': contractaddress[:-1], 
    'flodata': string,
    'contractConditions': {
        'subtype' : 'tokenswap',
        'accepting_token' : ,
        'selling_token' : ,
        'pricetype' : ,
        'price' : ,
    }
}


# Smart Contract Deposit - Token swap 
parsed_data = {
    'type': 'smartContractDeposit',
    'tokenIdentification': hashList[0][:-1], 
    'depositAmount': depositAmount, 
    'contractName': atList[0][:-1], 
    'flodata': string,
    'depositConditions': {
        'expiryTime'
    }
}