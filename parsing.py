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


# Combine test
def parse_flodata(string):

    if string[0:5] == 'text:':
        string = string.split('text:')[1]

    cleanstring = re.sub(' +', ' ', string)
    cleanstring = cleanstring.lower()

    if isTransfer(cleanstring):
        marker = extractMarker(cleanstring)
        operation = extractOperation(cleanstring)
        amount = extractAmount(cleanstring)
        parsed_data = {'type': 'transfer', 'flodata': string, 'marker': marker, 'operation': operation,
                       'amount': amount}
    elif isIncorp(cleanstring):
        incMarker = extractMarker(cleanstring)
        initTokens = extractInitTokens(cleanstring)
        parsed_data = {'type': 'incorporation', 'flodata': string, 'marker': incMarker, 'initTokens': initTokens}
    else:
        parsed_data = {'type': 'noise'}


    return parsed_data