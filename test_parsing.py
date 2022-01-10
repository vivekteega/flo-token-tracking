from input_classifier import super_main_function
import pdb


token_incorporation_test_cases = [
    ['create 1000 rmt#', {'type': 'tokenIncorporation','flodata': 'create 1000 rmt#', 'tokenIdentification': 'rmt', 'tokenAmount': 1000.0}],
    ['create 100 rmt#', {'type' : 'tokenIncorporation','flodata': 'create 100 rmt#', 'tokenIdentification': 'rmt', 'tokenAmount': 100.0}],
    ['create 100 rmt$', {'type':'noise'}]
    ]

def test_token_incorporation():
    for test_case in token_incorporation_test_cases:
        parsed_data = super_main_function(test_case[0])
        expected_parsed_data = test_case[1]
        assert parsed_data == expected_parsed_data


conflict_smart_contract_participation_deposit_test_cases = [
    ["send 0.001 rmt# to india-elections-2019@ to FLO address F7osBpjDDV1mSSnMNrLudEQQ3cwDJ2dPR1 with the userchoice:'narendra modi wins'", {
            'type': 'transfer', 
            'transferType': 'smartContract', 
            'flodata': "send 0.001 rmt# to india-elections-2019@ to FLO address F7osBpjDDV1mSSnMNrLudEQQ3cwDJ2dPR1 with the userchoice:'narendra modi wins'",
            'tokenIdentification': 'rmt',
            'operation': 'transfer', 
            'tokenAmount': 0.001, 
            'contractName': 'india-elections-2019@', 
            'userChoice': 'narendra modi wins'
            }]
]

def test_conflict_smart_contract_participation_deposit():
    for test_case in conflict_smart_contract_participation_deposit_test_cases:
        parsed_data = super_main_function(test_case[0])
        expected_parsed_data = test_case[1]
        


