def outputreturn(*argv):
    if argv[0] == 'noise':
        parsed_data = {'type': 'noise'}
        return parsed_data
    elif argv[0] == 'token_incorporation':
        parsed_data = {
            'type': 'tokenIncorporation',
            'flodata': argv[1], #string 
            'tokenIdentification': argv[2], #hashList[0][:-1] 
            'tokenAmount': argv[3] #initTokens
            }
        return parsed_data
    elif argv[0] == 'token_transfer':
        parsed_data = {
            'type': 'transfer', 
            'transferType': 'token', 
            'flodata': argv[1], #string
            'tokenIdentification': argv[2], #hashList[0][:-1]
            'tokenAmount': argv[3] #amount
            }
        return parsed_data
    elif argv[0] == 'one-time-event-userchoice-smartcontract-incorporation':
        parsed_data = {
            'type': 'smartContractIncorporation', 
            'contractType': 'one-time-event',
            'tokenIdentification': argv[1], #hashList[0][:-1] 
            'contractName': argv[2], #atList[0][:-1]
            'contractAddress': argv[3], #contractaddress[:-1] 
            'flodata': argv[4], #string
            'contractConditions': {
                'contractamount' : argv[5],
                'minimumsubscriptionamount' : argv[6],
                'maximumsubscriptionamount' : argv[7],
                'payeeaddress' : argv[8],
                'userchoice' : argv[9],
                'expiryTime' : argv[10]
            }
        }
        return parsed_data
    elif argv[0] == 'one-time-event-userchoice-smartcontract-participation':
        parsed_data = {
            'type': 'transfer', 
            'transferType': 'smartContract', 
            'flodata': argv[1], #string
            'tokenIdentification': argv[2], #hashList[0][:-1]
            'operation': 'transfer', 
            'tokenAmount': argv[3], #amount 
            'contractName': argv[4], #atList[0][:-1]
            'userChoice': argv[5] #userChoice
            }
        return parsed_data
    elif argv[0] == 'one-time-event-userchoice-smartcontract-trigger':
        parsed_data = {
            'type': 'smartContractPays', 
            'contractName': argv[1], #atList[0][:-1] 
            'triggerCondition': argv[2] #triggerCondition.group().strip()[1:-1]
            }
        return parsed_data
    elif argv[0] == 'one-time-event-time-smartcontract-incorporation':
        parsed_data = {
            'type': 'smartContractIncorporation', 
            'contractType': 'one-time-event',
            'tokenIdentification': argv[1], #hashList[0][:-1] 
            'contractName': argv[2], #atList[0][:-1]
            'contractAddress': argv[3], #contractaddress[:-1] 
            'flodata': argv[4], #string
            'contractConditions': {
                'contractamount' : argv[5],
                'minimumsubscriptionamount' : argv[6],
                'maximumsubscriptionamount' : argv[7],
                'payeeaddress' : argv[8],
                'expiryTime' : argv[9]
            }
        }
        return parsed_data
    elif argv[0] == 'one-time-event-time-smartcontract-participation':
        parsed_data = {
            'type': 'transfer', 
            'transferType': 'smartContract', 
            'flodata': argv[1], #string
            'tokenIdentification': argv[2], #hashList[0][:-1]
            'operation': 'transfer', 
            'tokenAmount': argv[3], #amount 
            'contractName': argv[4] #atList[0][:-1]
            }
        return parsed_data
    elif argv[0] == 'continuos-event-token-swap-incorporation':
        parsed_data = {
            'type': 'smartContractIncorporation', 
            'contractType': 'continuos-event',
            'tokenIdentification': argv[1], #hashList[0][:-1] 
            'contractName': argv[2], #atList[0][:-1]
            'contractAddress': argv[3], #contractaddress[:-1] 
            'flodata': argv[4], #string
            'contractConditions': {
                'subtype' : argv[5], #tokenswap
                'accepting_token' : argv[6],
                'selling_token' : argv[7],
                'pricetype' : argv[8],
                'price' : argv[9],
            }
        }
        return parsed_data
    elif argv[0] == 'continuos-event-token-swap-deposit':
        parsed_data = {
            'type': 'smartContractDeposit',
            'tokenIdentification': argv[1], #hashList[0][:-1]
            'depositAmount': argv[2], #depositAmount 
            'contractName': argv[3], #atList[0][:-1] 
            'flodata': argv[4], #string
            'depositConditions': {
                'expiryTime' : argv[5]
            }
        }
        return parsed_data
    elif argv[0] == 'continuos-event-token-swap-participation':
        parsed_data = {
            'type': 'smartContractParticipation',
            'tokenIdentification': argv[1], #hashList[0][:-1]
            'tokenAmount': argv[2], #tokenAmount 
            'contractName': argv[3], #atList[0][:-1] 
            'flodata': argv[4] #string 
        }
        return parsed_data

response_string = outputreturn('token_incorporation','create 5000 rmt#', 'rmt', 5000.0)
print(response_string)

def outputreturn_parameterlist(nameoflist, value):
    # if the name of list does not exist, create it 
    # if the name of list does exist, append value 
    # for eg. for creating tokens, the name of list is "create_token_list" and its elements are create_token_list[0]='tokenincorporation', create_token_list[1]='<flodata>', create_token_list[2]='<tokenname>', create_token_list[1]='<tokenamount>' 
    return nameoflist


outputreturn('token_incorporation',f"{flodata}", f"{tokenname}", f"{tokenamount}")

outputreturn('token_transfer',f"{flodata}", f"{tokenname}", f"{tokenamount}")

outputreturn('one-time-event-userchoice-smartcontract-incorporation',f"{tokenIdentification}", f"{contractName}", f"{contractAddress}", f"{flodata}", f"{contractamount}", f"{minimumsubscriptionamount}", f"{maximumsubscriptionamount}", f"{payeeaddress}", f"{userchoice}", f"{expiryTime}")

outputreturn('one-time-event-userchoice-smartcontract-participation',f"{flodata}", f"{tokenIdentification}", f"{tokenAmount}", f"{contractName}", f"{userChoice}")

outputreturn('one-time-event-userchoice-smartcontract-trigger', f"{contractName}", f"{triggerCondition}")

outputreturn('one-time-event-time-smartcontract-incorporation', f"{tokenIdentification}", f"{contractName}", f"{contractAddress}", f"{flodata}", f"{contractamount}", f"{minimumsubscriptionamount}", f"{maximumsubscriptionamount}", f"{payeeaddress}", f"{expiryTime}")

outputreturn('one-time-event-time-smartcontract-participation', f"{flodata}", f"{tokenIdentification}", f"{tokenAmount}", f"{contractName}")

outputreturn('one-time-event-time-smartcontract-participation', f"{flodata}", f"{tokenIdentification}", f"{tokenAmount}", f"{contractName}")

outputreturn('continuos-event-token-swap-incorporation', f"{tokenIdentification}", f"{contractName}", f"{contractAddress}", f"{flodata}", f"{subtype}", f"{accepting_token}", f"{selling_token}", f"{pricetype}", f"{price}")

outputreturn('continuos-event-token-swap-deposit', f"{tokenIdentification}", f"{depositAmount}", f"{contractName}", f"{flodata}", f"{expiryTime}")

outputreturn('continuos-event-token-swap-participation', f"{tokenIdentification}", f"{tokenAmount}", f"{contractName}", f"{flodata}")

