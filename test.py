import pdb

""" 
Find make lists of #, *, @ words 

If only 1 hash word and nothing else, then it is token related ( tokencreation or tokentransfer )

If @ is present, then we know it is smart contract related 
    @ (#)pre:       -  participation , deposit 
    @ * (#)pre:     -  one time event creation 
    @ * (# #)post:  -  token swap creation 
    @               -  trigger 

Check for 1 @ only 
Check for 1 # only 
Check for @ (#)pre: 
Check for @ * (#)pre: 
Check for @ * (# #)post: 

special_character_frequency = { 
    'precolon': { 
        '#':0, 
        '*':0,
        '@':0,
        ':':0
}

for word in allList:
    if word.endswith('#'):
        special_character_frequency['#'] = special_character_frequency['#'] + 1
    elif word.endswith('*'):
        special_character_frequency['*'] = special_character_frequency['*'] + 1
    elif word.endswith('@'):
        special_character_frequency['@'] = special_character_frequency['@'] + 1
    elif word.endswith(':'):
        special_character_frequency[':'] = special_character_frequency[':'] + 1

""" 


def findrules(rawstring, special_characters):
    wordList = []
    for word in rawstring.split(' '):
        if word[-1] in special_characters and (len(word) != 1 or word==":"):
            wordList.append(word)
    return wordList


def checkSearchPattern1(parsed_list, searchpatterns):
    for firstCategorization in searchpatterns.keys():
        counter = 0
        for key in searchpatterns[firstCategorization].keys():
            if len(parsed_list) != len(searchpatterns[firstCategorization][key]):
                continue
            else:
                pdb.set_trace()
                for idx,val in enumerate(parsed_list):
                    if not parsed_list[idx].endswith(searchpatterns[firstCategorization][key][idx]):
                        return False 
                return True 
        if counter >= 1:
            return firstCategorization
    return 'noise'


def checkSearchPattern(parsed_list, searchpattern):
    if len(parsed_list)!=len(searchpattern):
        return False
    else:
        for idx,val in enumerate(parsed_list):
            if not parsed_list[idx].endswith(searchpattern[idx]):
                return False
        return True


def className(rawstring):
    # Create a list that contains @ , # , * and : ; in actual order of occurence with their words. Only : is allowed to exist without a word in front of it. 
    # Check for 1 @ only followed by :, and the class is trigger
    # Check for 1 # only, then the class is tokensystem
    # Check for @ in the first position, * in the second position, # in the third position and : in the fourth position, then class is one time event creation 
    # Check for @ in the first position, * in the second position and : in the third position, then hash is in 4th position, then hash in 5th position | Token swap creation 

    allList = findrules(rawstring,['#','*','@',':'])

    allList = ['rmt@','rmt*',':',"rmt#","rmt#"]
    allList1 = ['rmt#',':',"rmt@"]

    search_patterns = {
        'tokensystem-C':{
            1:['#']
        },
        'smart-contract-creation-C':{
            1:['@','*','#','$',':'],
            2:['@','*','#','$',':','#']
        },
        'smart-contract-participation-deposit-C':{
            1:['#','@',':'],
            2:['#','@','$',':']
        },
        'userchoice-trigger':{
            1:['@',':']
        },
        'smart-contract-participation-ote-ce-C':{
            1:['#','@'],
            2:['#','@','$']
        },
        'smart-contract-creation-ce-tokenswap':{
            1:['@','*','$',':','#','#']
        }
    }

    patternmatch = checkSearchPattern(allList1, ['#',':','@','@'])
    print(f"Patternmatch is {patternmatch}")


rawstring = "test rmt# rmt@ rmt* : rmt# rmt# test" 
className(rawstring)