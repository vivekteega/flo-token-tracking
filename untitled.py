import requests
import json 
import sqlite3

conn = sqlite3.connect('tree.db')
c = conn.cursor()

c.execute("DROP TABLE IF EXISTS transactiontable")
c.execute("""CREATE TABLE transactiontable (
			id INTEGER PRIMARY KEY AUTOINCREMENT, 
			address TEXT,
			parentid INT,
			transferBalance INT
	)""")

c.execute("DROP TABLE IF EXISTS transferlogs")
c.execute("""CREATE TABLE transferlogs (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			primaryIDReference INTEGER,
			transferDescription TEXT,
			transferIDConsumed INT,
			blockchainReference TEXT
	)""")

c.execute("DROP TABLE IF EXISTS webtable")
c.execute("""CREATE TABLE webtable (
			id INTEGER PRIMARY KEY AUTOINCREMENT, 
			transferDescription TEXT,
			blockchainReference TEXT
	)""")

c.execute("DROP TABLE IF EXISTS transactionHistory")
c.execute("""CREATE TABLE transactionHistory (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			fromAddress TEXT,
			toAddress TEXT,
			amount INT,
			blockchainReference TEXT
	)""")

c.execute("DROP TABLE IF EXISTS extra")
c.execute("CREATE TABLE extra ( id INTEGER PRIMARY KEY , lastblockscanned INT)")
conn.commit()


#take in root address
root_address = "oPounjEbJxY7YCBaVBm61Lf2ym9DgFnAdu"
root_init_value = 21000

c.execute("INSERT INTO transactiontable ( address, parentid, transferBalance) VALUES (?,?,?)", (root_address, 0, root_init_value ))
conn.commit()

transferDescription = "Root address = " + str(root_address) + " has been initialized with "+ str(root_init_value)+ " tokens"
blockchainReference = 'https://testnet.florincoin.info/tx/'
c.execute("""INSERT INTO transferlogs (primaryIDReference, transferDescription, transferIDConsumed, blockchainReference)
											VALUES (?,?,?,?)""", ( 1, transferDescription, 0, blockchainReference))

#find root address's block 
string = "https://testnet.florincoin.info/ext/getaddress/" + str(root_address)
response = requests.get(string)
content = json.loads(response.content.decode("utf-8"))
root_trans_hash = ''
for cur in content["last_txs"]:
	if cur["type"] == "vout":
		root_trans_hash = cur["addresses"]
		break


string = "https://testnet.florincoin.info/api/getrawtransaction?txid=" + str(root_trans_hash) +"&decrypt=1"
response = requests.get(string)
content = json.loads(response.content.decode("utf-8"))
root_block_hash = content["blockhash"]

string = "https://testnet.florincoin.info/api/getblock?hash=" + str(root_block_hash)
response = requests.get(string)
content = json.loads(response.content.decode("utf-8"))
root_block_index = content["height"]
#root_block_index = 26066

print("root_block_index = " + str(root_block_index))

# get current block count 
response = requests.get("https://testnet.florincoin.info/api/getblockcount")
current_index = json.loads(response.content.decode("utf-8"))
print("current_block_index : " + str(current_index))

def listcheck(lst):
	for element in lst:
		try:
			float(element)
		except ValueError:
			print("values to be transferred aren't in the right format")
			return 1
	return 0

def dothemagic(blockindex):
	string = "https://testnet.florincoin.info/api/getblockhash?index=" + str(blockindex)
	response = requests.get(string)
	blockhash = response.content.decode("utf-8")

	string = "https://testnet.florincoin.info/api/getblock?hash=" + str(blockhash)
	response = requests.get(string)
	blockinfo = json.loads(response.content.decode("utf-8"))

	for transaction in blockinfo["tx"]:
		string = "https://testnet.florincoin.info/api/getrawtransaction?txid="+ str(transaction) +"&decrypt=1"
		response = requests.get(string)
		data = json.loads(response.content.decode("utf-8"))
		text = data["floData"]
		text = text[5:]
		comment_list = text.split("#")

		if comment_list[0] == 'ranchimalltest':
			print("I just saw ranchimalltest")
			commentTransferAmount = comment_list[1:]
			
			#if not all(isinstance(x, (int, float)) for x in commentTransferAmount):
			#	print("Values to be transffered aren't in the right format")
			#	continue

			if len(commentTransferAmount) == 0:
				print("Value for token transfer has not been specified")
				continue

			returnval = listcheck(commentTransferAmount)
			if returnval == 1:
				continue

			commentTransferAmount = list(map(float, commentTransferAmount))

			inputlist = []
			querylist = []

			for obj in data["vin"]:
				querylist.append([obj["txid"], obj["vout"]])

			inputval = 0
			inputadd = ''

			for query in querylist:
				string = "https://testnet.florincoin.info/api/getrawtransaction?txid="+ str(query[0]) +"&decrypt=1"
				response = requests.get(string)
				content = json.loads(response.content.decode("utf-8"))

				for objec in content["vout"]:
					if objec["n"] == query[1]:
						inputadd = objec["scriptPubKey"]["addresses"][0]
						inputval = inputval + objec["value"]

			inputlist = [[inputadd, inputval]]

			if len(inputlist) > 1:
				print("Program has detected more than one input address ")
				print("This transaction will be discarded")
				continue

			outputlist = []
			for obj in data["vout"]:
				if obj["scriptPubKey"]["type"] == "pubkeyhash":
					if inputlist[0][0] == obj["scriptPubKey"]["addresses"][0]:
						continue
					temp = []
					temp.append(obj["scriptPubKey"]["addresses"][0]) 
					temp.append(obj["value"])

					outputlist.append(temp)


			print("\n\nInput List")
			print(inputlist)
			print("\nOutput List")
			print(outputlist)

			if len(inputlist) > 1:
				print("Program has detected more than one input address ")
				print("This transaction will be discarded")
				continue

			c.execute("SELECT sum(transferBalance) FROM transactiontable WHERE address=?" , (inputlist[0][0],))
			availableTokens = c.fetchall()
			availableTokens = availableTokens[0][0] 

			if availableTokens is None:
				print("The input address dosen't exist in our database ")

			elif availableTokens < sum(commentTransferAmount):
				print("\nThe transfer amount passed in the comments is more than the user owns\nThis transaction will be discarded\n")
				continue

				# commentTransferAmount = availableTokens

				# for output in outputlist:
				# 	if output[0] == inputlist[0][0]:
				# 		continue

				# 	c.execute("SELECT * FROM transactiontable WHERE address=?",(inputlist[0][0],))
				# 	table = c.fetchall()

				# 	pidlst = []
				# 	checksum = 0
				# 	for row in table:
				# 		if checksum >= outputlist[0][1]:
				# 			break
				# 		pidlst.append(row[0])
				# 		checksum = checksum + row[3]

				# 	balance = commentTransferAmount

				# 	for pid in pidlst:
				# 			c.execute("SELECT transferBalance FROM transactiontable WHERE id=?", (pid,))
				# 			temp = c.fetchall()
				# 			temp = temp[0][0]

				# 			if balance <= temp:
				# 				c.execute("INSERT INTO transactiontable (address, parentid, transferBalance) VALUES (?,?,?)", (output[0],pid,balance))
				# 				c.execute("UPDATE transactiontable SET transferBalance=? WHERE id=?", (temp-balance, pid))
								
				# 				c.execute("SELECT id FROM transactiontable ORDER BY id DESC LIMIT 1")
				# 				lastid = c.fetchall()[0][0]
				# 				transferDescription = "$$ " +str(balance) + " tokens transferred to " + str(output[0]) + " from pid = " + str(pid)
				# 				blockchainReference = 'https://testnet.florincoin.info/tx/' + str(transaction)
				# 				c.execute("""INSERT INTO transferlogs (primaryIDReference, transferDescription, transferIDConsumed, blockchainReference)
				# 							VALUES (?,?,?,?)""", ( lastid, transferDescription, pid, blockchainReference))

				# 				transferDescription = "$$ balance in id = " + str(pid) + " UPDATED from " + str(temp) + " to " + str(temp-balance)
				# 				blockchainReference = 'https://testnet.florincoin.info/tx/' + str(transaction)
				# 				c.execute("""INSERT INTO transferlogs (primaryIDReference, transferDescription)
				# 							VALUES (?,?)""", ( pid, transferDescription))

				# 				balance = 0
				# 				conn.commit()
				# 			elif balance > temp:
				# 				c.execute("INSERT INTO transactiontable (address, parentid, transferBalance) VALUES (?,?,?)", (output[0], pid, temp ))
				# 				c.execute("UPDATE transactiontable SET transferBalance=? WHERE id=?", (0, pid))

				# 				c.execute("SELECT id FROM transactiontable ORDER BY id DESC LIMIT 1")
				# 				lastid = c.fetchall()[0][0]
				# 				transferDescription = "$$ " + str(temp) + " tokens transferred to " + str(output[0]) + " from pid = " + str(pid)
				# 				blockchainReference = 'https://testnet.florincoin.info/tx/' + str(transaction)
				# 				c.execute("""INSERT INTO transferlogs (primaryIDReference, transferDescription, transferIDConsumed, blockchainReference)
				# 							VALUES (?,?,?,?)""", ( lastid, transferDescription, pid, blockchainReference))

				# 				transferDescription = "$$ balance in id = " + str(pid) + " UPDATED from " + str(temp) + " to " + str(0)
				# 				blockchainReference = 'https://testnet.florincoin.info/tx/' + str(transaction)
				# 				c.execute("""INSERT INTO transferlogs (primaryIDReference, transferDescription)
				# 							VALUES (?,?)""", ( pid, transferDescription))

				# 				balance = balance - temp
				# 				conn.commit()

			elif availableTokens >= sum(commentTransferAmount):
				if len(commentTransferAmount) != len(outputlist):
					print("The parameters in the comments aren't enough")
					print("This transaction will be discarded")
					continue

				for i in range(len(commentTransferAmount)):
					# if output[0] == inputlist[0][0]:
					# 	continue

					c.execute("SELECT * FROM transactiontable WHERE address=?",(inputlist[0][0],))
					table = c.fetchall()

					pidlst = []
					checksum = 0
					for row in table:
						if checksum >= commentTransferAmount[i]:
							break
						pidlst.append(row[0])
						checksum = checksum + row[3]

					balance = commentTransferAmount[i]
					c.execute("SELECT sum(transferBalance) FROM transactiontable WHERE address=?", ( outputlist[i][0],))
					opbalance = c.fetchall()[0][0]
					if opbalance is None:
						opbalance = 0

					c.execute("SELECT sum(transferBalance) FROM transactiontable WHERE address=?", ( inputlist[0][0],))
					ipbalance = c.fetchall()[0][0]

					for pid in pidlst:
							c.execute("SELECT transferBalance FROM transactiontable WHERE id=?", (pid,))
							temp = c.fetchall()
							temp = temp[0][0]

							if balance <= temp:
								c.execute("INSERT INTO transactiontable (address, parentid, transferBalance) VALUES (?,?,?)", (outputlist[i][0],pid,balance))
								c.execute("UPDATE transactiontable SET transferBalance=? WHERE id=?", (temp-balance, pid))

								## transaction logs section ##
								c.execute("SELECT id FROM transactiontable ORDER BY id DESC LIMIT 1")
								lastid = c.fetchall()[0][0]
								transferDescription = str(balance) + " tokens transferred to " + str(outputlist[i][0]) + " from " + str(inputlist[0][0])
								blockchainReference = 'https://testnet.florincoin.info/tx/' + str(transaction)
								c.execute("""INSERT INTO transferlogs (primaryIDReference, transferDescription, transferIDConsumed, blockchainReference)
											VALUES (?,?,?,?)""", ( lastid, transferDescription, pid, blockchainReference))

								transferDescription = str(inputlist[0][0]) + " balance UPDATED from " + str(temp) + " to " + str(temp-balance)
								blockchainReference = 'https://testnet.florincoin.info/tx/' + str(transaction)
								c.execute("""INSERT INTO transferlogs (primaryIDReference, transferDescription, blockchainReference)
											VALUES (?,?,?)""", ( pid, transferDescription, blockchainReference))

								##webpage table section ##
								transferDescription = str(commentTransferAmount[i]) + " tokens transferred from " + str(inputlist[0][0]) + " to " + str(outputlist[i][0]) 
								c.execute("""INSERT INTO webtable (transferDescription, blockchainReference) 
											VALUES (?,?)""", ( transferDescription, blockchainReference))

								transferDescription = "UPDATE " + str(outputlist[i][0]) + " balance from " + str(opbalance) + " to " + str(opbalance + commentTransferAmount[i])
								c.execute("""INSERT INTO webtable (transferDescription, blockchainReference) 
											VALUES (?,?)""", ( transferDescription, blockchainReference))

								transferDescription = "UPDATE " + str(inputlist[0][0]) + " balance from " + str(ipbalance) + " to " + str(ipbalance - commentTransferAmount[i])
								c.execute("""INSERT INTO webtable (transferDescription, blockchainReference) 
											VALUES (?,?)""", ( transferDescription, blockchainReference))

								balance = 0
								conn.commit()
							elif balance > temp:
								c.execute("INSERT INTO transactiontable (address, parentid, transferBalance) VALUES (?,?,?)", (outputlist[i][0], pid, temp ))
								c.execute("UPDATE transactiontable SET transferBalance=? WHERE id=?", (0, pid))

								##transaction logs section ##
								c.execute("SELECT id FROM transactiontable ORDER BY id DESC LIMIT 1")
								lastid = c.fetchall()[0][0]
								transferDescription = str(temp) + " tokens transferred to " + str(outputlist[i][0]) + " from " + str(inputlist[0][0])
								blockchainReference = 'https://testnet.florincoin.info/tx/' + str(transaction)
								c.execute("""INSERT INTO transferlogs (primaryIDReference, transferDescription, transferIDConsumed, blockchainReference)
											VALUES (?,?,?,?)""", ( lastid, transferDescription, pid, blockchainReference))

								transferDescription = str() + " balance UPDATED from " + str(temp) + " to " + str(0)
								blockchainReference = 'https://testnet.florincoin.info/tx/' + str(transaction)
								c.execute("""INSERT INTO transferlogs (primaryIDReference, transferDescription, blockchainReference)
											VALUES (?,?,?)""", ( pid, transferDescription, blockchainReference))


								balance = balance - temp
								conn.commit()


#current_index = 19431
#root_block_index = 19428

c.execute("INSERT INTO extra (id, lastblockscanned) VALUES (?,?)", (1, root_block_index))
# run loop and pass blockno 
for blockindex in range(root_block_index + 1, current_index+1):
	print(blockindex)
	dothemagic(blockindex)
	c.execute("UPDATE extra SET lastblockscanned=? WHERE id=?", (blockindex,1))

conn.commit()
conn.close()