import re

marker = None
operation = None
address = None
amount = None


def isTransfer(text):
    wordlist = ['transfer','send','give'] # keep everything lowercase
    textList = text.split(' ')
    for word in wordlist:
        if word in textList:
            return True
    return False


def isIncorp(text):
    wordlist = ['incorporate','create','start'] # keep everything lowercase
    textList = text.split(' ')
    for word in wordlist:
        if word in textList:
            return True
    return False


def isSmartContract(text):
    textList = text.split(' ')
    for word in textList:
        if word == '':
            continue
        if word.endswith('@'):
            return word
    return False


def isSmartContractPay(text):
    wordlist = text.split(' ')
    if len(wordlist) != 2:
        return False
    smartContractTrigger = re.findall(r"smartContractTrigger:'.*'", text)[0].split('smartContractTrigger:')[1]
    smartContractTrigger = smartContractTrigger[1:-1]
    smartContractName = re.findall(r"smartContractName:.*@", text)[0].split('smartContractName:')[1]
    smartContractName = smartContractName[:-1]

    if smartContractTrigger and smartContractName:
        contractconditions = { 'smartContractTrigger':smartContractTrigger, 'smartContractName':smartContractName }
        return contractconditions
    else:
        return False


def extractAmount(text, marker):
    count = 0
    returnval = None
    splitText = re.split("\W+", text)

    for word in splitText:
        word = word.replace(marker, '')
        try:
            float(word)
            count = count + 1
            returnval = float(word)
        except ValueError:
            pass

        if count > 1:
            return 'Too many'
    return returnval


def extractMarker(text):
    textList = text.split(' ')
    for word in textList:
        if word == '':
            continue
        if word.endswith('#'):
            return word
    return False


def extractInitTokens(text):
    base_units = {'thousand':10**3 , 'million':10**6 ,'billion':10**9, 'trillion':10**12}
    textList = text.split(' ')
    for idx,word in enumerate(textList):
        try:
            result = float(word)
            if textList[idx+1] in base_units:
                return result*base_units[textList[idx+1]]
            return result
        except:
            continue
    return None


def extractAddress(text):
    textList = text.split(' ')
    for word in textList:
        if word == '':
            continue
        if word[-1] == '$':
            return word
    return None


def extractContractType(text):
    operationList = ['betting*'] # keep everything lowercase
    count = 0
    returnval = None
    for operation in operationList:
        count = count + text.count(operation)
        if count > 1:
            return 'Too many'
        if count == 1 and (returnval is None):
            returnval = operation
    return returnval


def extractContractCondition(text):
    result = text.split("contractcondition:")
    if len(result) != 1:
        return result[1].strip()[1:-1]
    else:
        return None


def extractContractConditions(text, contracttype, marker):
    rulestext = re.split('contractconditions:\s*', text)[-1]
    rulelist = re.split('\d\.\s*', rulestext)
    if contracttype == 'betting*':
        extractedRules = {}
        for rule in rulelist:
            if rule=='':
                continue
            elif rule[:19]=='userassetcommitment':
                pattern = re.compile('[^userassetcommitment="].*[^"]')
                searchResult = pattern.search(rule).group(0)
                extractedRules['userassetcommitment'] = searchResult.split(marker)[0]
            elif rule[:17]=='smartcontractpays':
                conditions = rule.split('smartcontractpays=')[1]
                if conditions[0]=='"' or conditions[0]=="'" or conditions[-1]=='"' or conditions[-1]=="'":
                    conditionlist = conditions[1:-1].split('|')
                    extractedRules['smartcontractpays'] = {}
                    for idx, condition in enumerate(conditionlist):
                        extractedRules['smartcontractpays'][idx] = condition.strip()
                else:
                    print("something is wrong with smartcontractpays conditions")

        if 'userassetcommitment' in extractedRules and 'smartcontractpays' in extractedRules:
            return extractedRules
        else:
            return None
    return None


def extractTriggerCondition(text):
    searchResult = re.search('\".*\"', text)
    if searchResult is None:
        searchResult = re.search('\'.*\'', text)
        return searchResult
    return searchResult


# Combine test
def parse_flodata(string):

    if string[0:5] == 'text:':
        string = string.split('text:')[1]

    nospacestring = re.sub(' +', ' ', string)
    cleanstring = nospacestring.lower()

    atList = []
    hashList = []

    for word in cleanstring.split(' '):
        if word.endswith('@'):
            atList.append(word)
        if word.endswith('#'):
            hashList.append(word)

    # Filter noise first - check if the words end with either @ or #
    if (len(atList)==0 and len(hashList)==0) or len(atList)>1 or len(hashList)>1:
        parsed_data = {'type': 'noise'}

    elif len(hashList)==1 and len(atList)==0:
        # Passing the above check means token creation or transfer
        incorporation = isIncorp(cleanstring)
        transfer = isTransfer(cleanstring)

        if incorporation and not transfer:
            initTokens = extractInitTokens(cleanstring)
            if initTokens is not None:
                parsed_data = {'type': 'tokenIncorporation', 'flodata': string, 'tokenIdentification': hashList[0][:-1],
                           'tokenAmount': initTokens}
            else:
                parsed_data = {'type': 'noise'}
        elif not incorporation and transfer:
            amount = extractAmount(cleanstring, hashList[0][:-1])
            address = extractAddress(nospacestring)
            if None not in [amount, address]:
                parsed_data = {'type': 'transfer', 'transferType': 'token', 'flodata': string,
                           'tokenIdentification': hashList[0][:-1],
                           'tokenAmount': amount, 'address': address[:-1]}
            else:
                parsed_data = {'type': 'noise'}
        else:
            parsed_data = {'type': 'noise'}

    elif len(hashList)==1 and len(atList)==1:
        # Passing the above check means Smart Contract creation or transfer
        incorporation = isIncorp(cleanstring)
        transfer = isTransfer(cleanstring)

        if incorporation and not transfer:
            contracttype = extractContractType(cleanstring)
            contractaddress = extractAddress(nospacestring)
            contractconditions = extractContractConditions(cleanstring, 'betting*', marker)

            if None not in [contracttype, contractaddress, contractconditions]:
                parsed_data = {'type': 'smartContractIncorporation', 'contractType': contracttype[:-1],
                           'tokenIdentification': hashList[0][:-1], 'contractName': atList[0][:-1],
                           'contractAddress': contractaddress[:-1], 'flodata': string,
                           'contractConditions': contractconditions}
            else:
                parsed_data = {'type': 'noise'}
        elif not incorporation and transfer:
            amount = extractAmount(cleanstring, hashList[0][:-1])
            contractcondition = extractContractCondition(cleanstring)
            if None not in [amount, contractcondition]:
                parsed_data = {'type': 'transfer', 'transferType': 'smartContract', 'flodata': string,
                           'tokenIdentification': hashList[0][:-1],
                           'operation': 'transfer', 'tokenAmount': amount, 'contractName': atList[0][:-1],
                           'contractCondition': contractcondition}
            else:
                parsed_data = {'type': 'noise'}
        else:
            parsed_data = {'type': 'noise'}


    elif len(hashList)==0 and len(atList)==1:
        # Passing the above check means Smart Contract pays | exitcondition triggered from the committee
        triggerCondition = extractTriggerCondition(cleanstring)
        if triggerCondition is not None:
            parsed_data = {'type': 'smartContractPays', 'contractName': atList[0][:-1], 'triggerCondition': triggerCondition.group().strip()[1:-1]}
        else:
            parsed_data = {'type':'noise'}

    return parsed_data

result = parse_flodata("for contractname@ Smart Contract System says 'NAMO=WIN'")
print(result)