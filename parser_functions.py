import pdb
import re

def findrule1(rawstring, special_character):
    wordList = []
    for word in rawstring.split(' '):
        if word.endswith(special_character) and len(word) != 1:
            wordList.append(word)
    return wordList

def findrule1_1(rawstring, special_character):
    wordList = []
    for word in rawstring.split(' '):
        if word.endswith(special_character) and len(word) != 1:
            wordList.append(word)
    if len(wordList)==1:
        return wordList[0]
    else:
        False

'''
rawstring = "Create Smart Contract with the name swap-rupee-bioscope@ of the type continuous-event* at the address oRRCHWouTpMSPuL6yZRwFCuh87ZhuHoL78$ with contract-conditions :(1) subtype = tokenswap (2) accepting_token=rupee# (3) selling_token = bioscope# (4) price = '15' (5) priceType = ‘predetermined’ (6) direction = oneway"
rawstring1 = "send 500 rmt1# rmt2# rmt3#"

response = findrule1(rawstring1, '#')
print(f"\n\nResponse for rawstring1 searching #")
print(response)

response = findrule1(rawstring, '#')
print(f"\n\nResponse for rawstring searching #")
print(response)
'''

inputstring = " : rmt3# "
special_character = "#"
marker = ":"
operator = "after_marker"
output = ["rmt1#", "rmt2#"]

def findrule2(inputstring, special_character, marker, operator):
    inputstring_toprocess = None
    if operator=='before_marker':
        inputstring_toprocess = inputstring.split(":")[0]
    elif operator=='after_marker':
        inputstring_toprocess = inputstring.split(":")[1]

    wordList = []
    for word in inputstring_toprocess.split(' '):
        if word.endswith(special_character) and len(word) != 1:
            wordList.append(word)
    return wordList

'''response = findrule2(inputstring, special_character, marker, operator)
print(response)  '''

##########

def findrule3(text):
    base_units = {'thousand': 10 ** 3, 'million': 10 ** 6, 'billion': 10 ** 9, 'trillion': 10 ** 12}
    textList = text.split(' ')
    counter = 0
    value = None
    for idx, word in enumerate(textList):
        try:
            result = float(word)
            if textList[idx + 1] in base_units:
                value = result * base_units[textList[idx + 1]]
                counter = counter + 1
            else:
                value = result
                counter = counter + 1
        except:
            for unit in base_units:
                result = word.split(unit)
                if len(result) == 2 and result[1] == '' and result[0] != '':
                    try:
                        value = float(result[0]) * base_units[unit]
                        counter = counter + 1
                    except:
                        continue

    if counter == 1:
        return value
    else:
        return None


##########

def findWholeWord(w):
    return re.compile(r'\b({0})\b'.format(w), flags=re.IGNORECASE).search

def truefalse_rule2(rawstring, permitted_list, denied_list):
    # Find transfer , send , give
    foundPermitted = None 
    foundDenied = None

    for word in permitted_list:
        if findWholeWord(word)(rawstring):
            foundPermitted = word
            break

    for word in denied_list:
        if findWholeWord(word)(rawstring):
            foundDenied = word
            break
    
    if (foundPermitted is not None) and (foundDenied is None):
        return True
    else:
        return False 

'''teststring = "create 500 rmt# start send "
response = truefalse_rule2(teststring, permitted_list, denied_list)
print(response)'''

# Token incorporation operation 
## Existance of keyword 

def apply_rule1(*argv):
    a = argv[0](*argv[1:])
    if a is False:
        return None
    else:
        return a


rawstring = "create 5 million rmt# transfer"

# desired output format - outputreturn('token_incorporation',f"{flodata}", f"{tokenname}", f"{tokenamount}")
tokenname = apply_rule1(findrule1_1,rawstring,"#")
print(tokenname)
denied_list = ['transfer', 'send', 'give']  # keep everything lowercase
permitted_list = ['incorporate', 'create', 'start']  # keep everything lowercase
if tokenname is not None:
    isIncorporate = apply_rule1(truefalse_rule2, rawstring, permitted_list, denied_list)

operationname = apply_rule1(truefalse_rule2, rawstring, permitted_list, denied_list)
if not operation:
    formatOutput("noise") 

#response_string = outputreturn('token_incorporation','create 5000 rmt#', 'rmt', 5000.0)
#print(response_string)