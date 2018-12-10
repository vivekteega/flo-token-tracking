import requests
import json 
import sqlite3


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
		text = data["tx-comment"]
		text = text[5:]
		comment_list = text.split("#")

		if comment_list[0] == 'ranchimalltest':

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

def update():
	conn = sqlite3.connect('tree.db')
	c = conn.cursor()
	# get current block count 
	response = requests.get("https://testnet.florincoin.info/api/getblockcount")
	current_index = json.loads(response.content.decode("utf-8"))

	c.execute("SELECT lastblockscanned FROM extra WHERE id=1")
	lastblockscanned = c.fetchall()[0][0]

	#print("last scanned block " + str(lastblockscanned))
	for blockindex in range(lastblockscanned + 1, current_index+1):
	 	print(blockindex)
	 	#dothemagic(blockindex)
	 	#c.execute("UPDATE extra SET lastblockscanned=? WHERE id=?", (blockindex,1))

	conn.commit()
	conn.close()

update()