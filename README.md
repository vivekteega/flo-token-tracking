# FLO Token & Smart Contract System 

The python script scans the FLO Blockchain for Token and Smart Contract activity and creates/updates local SQLite databases accordingly. 

339dac6a50bcd973dda4caf43998fc61dd79ea68 
The legacy token and smart contract system running currently on the server 

41c4078db98e878ecef3452007893136c531ba05 ==> WORKING VERSION | Token swap branch 
The latest version with token swap smart contract and token transfer with the following problems:
1. Parsing module is not able to detect token creation and transfer floData 
2. The smart contract system is not moving forward because it is not able to detect token databases as they are created when run form scratch, however it is working with old created token databases

89d96501b9fcdd3c91c8900e1fb3dd5a8d8684c1
Docker-compatibility branch is needed right now because Docker image made for flo-token-tracking required some changes which have been made in that branch. 

