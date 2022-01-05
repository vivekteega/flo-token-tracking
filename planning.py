'''
    The problem we are facing:

    * Token transactions don't have * or @ symbols 

    * Smart Contract transactions have * , @ , # symbols 

    * Smart Contract transaction of the type one time event have 1 # before colon 

    * Smart Contract transaction of the type continuous event has 2 # after colon 

    * So we are checking for hashes based on the type of smart contract(identified by *)

    * But the above check disregards checking hashes in token transactions 
'''

# Write down all the possible flodata( with all combinations possible) for 
'''
    Token creation 
    create 500 million rmt#
    ['#']

    Token transfer 
    transfer 200 rmt#
    ['#']

    One time event userchoice creation 
    Create Smart Contract with the name India-elections-2019@ of the type one-time-event* using the asset rmt# at the address F7osBpjDDV1mSSnMNrLudEQQ3cwDJ2dPR1$ with contract-conditions: (1) contractAmount=0.001rmt (2) userChoices=Narendra Modi wins| Narendra Modi loses (3) expiryTime= Wed May 22 2019 21:00:00 GMT+0530
    ['@','*','#','$',':']
    ['@','*','#','$',':','#']
    
    One time event userchoice participation
    send 0.001 rmt# to india-elections-2019@ to FLO address F7osBpjDDV1mSSnMNrLudEQQ3cwDJ2dPR1 with the userchoice:'narendra modi wins'
    ['#','@',':']
    ['#','@','$',':']

    One time event userchoice trigger 
    india-elections-2019@ winning-choice:'narendra modi wins'
    ['@',':']

    One time event timeevent creation 
    Create Smart Contract with the name India-elections-2019@ of the type one-time-event* using the asset rmt# at the address F7osBpjDDV1mSSnMNrLudEQQ3cwDJ2dPR1$ with contract-conditions: (1) contractAmount=0.001rmt (2) expiryTime= Wed May 22 2019 21:00:00 GMT+0530
    ['@','*','#','$',':']
    ['@','*','#','$',':','#']

    One time event timeevent participation 
    send 0.001 rmt# to india-elections-2019@ to FLO address F7osBpjDDV1mSSnMNrLudEQQ3cwDJ2dPR1 
    ['#','@']
    ['#','@','$']

    Continuos event token swap creation 
    Create Smart Contract with the name swap-rupee-bioscope@ of the type continuous-event* at the address oRRCHWouTpMSPuL6yZRwFCuh87ZhuHoL78$ with contract-conditions :
    (1) subtype = tokenswap
    (2) accepting_token = rupee#
    (3) selling_token = bioscope#
    (4) price = '15'
    (5) priceType = ‘predetermined’
    (6) direction = oneway
    
    ['@','*','$',':','#','#']

    Continuos event tokenswap deposit 
    Deposit 15 bioscope# to swap-rupee-bioscope@ its FLO address being oRRCHWouTpMSPuL6yZRwFCuh87ZhuHoL78$ with deposit-conditions: (1) expiryTime= Wed Nov 17 2021 21:00:00 GMT+0530 
    ['#','@',':']
    ['#','@','$',':']

    Continuos event tokenswap participation 
    Send 15 rupee# to swap-rupee-article@ its FLO address being FJXw6QGVVaZVvqpyF422Aj4FWQ6jm8p2dL$ 
    ['#','@']
    ['#','@','$']
'''

'''

    ['#']                      -  Token creation 

    ['#']                      -  Token particiation


    ['@','*','#','$',':']      -  Smart contract creation user-choice  
    ['@','*','#','$',':','#']

    ['#','@',':']              -  Smart contract participation  user-choice
    ['#','@','$',':']

    ['@',':']                  -  Smart contract trigger user-choice 


    ['@','*','#','$',':']      -  Smart contract creation - ote-timebased
    ['@','*','#','$',':','#']

    ['#','@']                  -  Smart contract particiation - ote-timebased      
    ['#','@','$']


    ['@','*','$',':','#','#']  -  Smart contract creation - continuos event - tokenswap 

    ['#','@',':']              -  Smart contract deposit - continuos event - tokenswap 
    ['#','@','$',':']

    ['#','@']                  -  Smart contract participation - continuos event - tokenswap 
    ['#','@','$']              -  Smart contract participation - continuos event - tokenswap 

'''

'''

    ['#']                      -  Token creation 

    ['#']                      -  Token particiation


    ['@','*','#','$',':']      -  Smart contract creation ote-userchoice  
    ['@','*','#','$',':','#']

    ['@','*','#','$',':']      -  Smart contract creation - ote-timebased
    ['@','*','#','$',':','#']


    ['#','@',':']              -  Smart contract participation  user-choice
    ['#','@','$',':']

    ['#','@',':']              -  Smart contract deposit - continuos event - tokenswap 
    ['#','@','$',':']


    ['@',':']                  -  Smart contract trigger user-choice 


    ['#','@']                  -  Smart contract particiation - ote-timebased   
    ['#','@','$']

    ['#','@']                  -  Smart contract participation - continuos event - tokenswap 
    ['#','@','$']              -  Smart contract participation - continuos event - tokenswap 

    
    ['@','*','$',':','#','#']  -  Smart contract creation - continuos event - tokenswap 

'''

'''
Conflicts - 

1. Token creation | Token participation 
2. Smart contract CREATION of the type one-time-event-userchoice | one-time-event-timebased 
3. Smart contract PARTICIPATION user-choice | Smart contract DEPOSIT continuos-event token-swap
4. Smart contract PARTICIPATION one-time-event-timebased | Smart contract participation - continuos event - tokenswap 

'''

'''

Emerging parser design 

Phase 1 - Input processing | Special character position based classification and noise detection (FINISHED)
Phase 2 - Conflict recognition (FINISHED)
Phase 3 - Category based keyword checks 
Phase 4 - Parser rules for finding data 
Phase 5 - Rules for applying parser rules 
Phase 6 - Category based data field extraction 
Phase 7 - Output formatting and return (FINISHED)

'''