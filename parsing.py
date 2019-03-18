import re

marker = None
operation = None
address = None
amount = None


def isTransfer(text):
    wordlist = ['transfer','send','give'] #keep everything lowercase
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
        if word[-1] == '@':
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


def extractOperation(text):
    operationList = ['send', 'transfer', 'give'] # keep everything lowercase
    count = 0
    returnval = None
    for operation in operationList:
        count = count + text.count(operation)
        if count > 1:
            return 'Too many'
        if count == 1 and (returnval is None):
            returnval = operation
    return returnval


# todo pass marker to the function and support all types
def extractAmount(text):
    count = 0
    returnval = None
    splitText = re.split("\W+", text)

    for word in splitText:
        word = word.replace('rmt', '')
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
        if word[-1] == '#':
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
            return res
        except:
            continue


def extractAddress(text):
    textList = text.split(' ')
    for word in textList:
        if word[-1] == '$':
            return word
    return False


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
    return text.split("contractcondition:")[1][1:-1]


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


        return extractedRules
    return False


# Combine test
def parse_flodata(string):

    if string[0:5] == 'text:':
        string = string.split('text:')[1]

    nospacestring = re.sub(' +', ' ', string)
    cleanstring = nospacestring.lower()


    if isTransfer(cleanstring):
        if isSmartContract(cleanstring):
            contractname = isSmartContract(cleanstring)
            marker = extractMarker(cleanstring)
            operation = extractOperation(cleanstring)
            amount = extractAmount(cleanstring)
            contractcondition = extractContractCondition(cleanstring)
            parsed_data = { 'type': 'transfer', 'transferType': 'smartContract', 'flodata': string, 'tokenIdentification': marker[:-1],
                           'operation': operation, 'tokenAmount': amount, 'contractName': contractname, 'contractCondition': contractcondition}
        else:
            marker = extractMarker(cleanstring)
            operation = extractOperation(cleanstring)
            amount = extractAmount(cleanstring)
            address = extractAddress(nospacestring)
            parsed_data = {'type': 'transfer', 'transferType': 'token', 'flodata': string, 'tokenIdentification': marker[:-1], 'operation': operation,
                           'amount': amount, 'address': address}

    elif isSmartContractPay(nospacestring):
        contractConditions = isSmartContractPay(nospacestring)
        parsed_data = {'type': 'smartContractPays', 'flodata': string, 'smartContractTrigger':contractConditions['smartContractTrigger'], 'smartContractName':contractConditions['smartContractName']}

    elif isSmartContract(cleanstring):
        contractname = isSmartContract(cleanstring)
        marker = extractMarker(cleanstring)
        contracttype = extractContractType(cleanstring)
        contractaddress = extractAddress(nospacestring)
        contractconditions = extractContractConditions(cleanstring, 'betting*', marker)
        parsed_data = {'type': 'smartContractIncorporation', 'contractType': contracttype[:-1], 'tokenIdentification': marker[:-1], 'contractName': contractname[:-1], 'contractAddress':contractaddress[:-1], 'flodata': string, 'contractConditions': contractconditions}

    elif isIncorp(cleanstring):
        incMarker = extractMarker(cleanstring)
        initTokens = extractInitTokens(cleanstring)
        parsed_data = {'type': 'tokenIncorporation', 'flodata': string, 'tokenIdentification': incMarker[:-1], 'tokenAmount': initTokens}

    else:
        parsed_data = {'type': 'noise'}

    return parsed_data

result = parse_flodata('create electionbetting@ at address oM4pCYsbT5xg7bqLNCTXmoADUs6zBwLfXi$ of type betting* using the token rmt# with contractconditions: 1. userAssetCommitment="1rmt" 2. smartContractPays="NAMO=WIN | NAMO=LOOSE 3. expirydate=1553040000"')
print(result)