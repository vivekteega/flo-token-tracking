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

conn.commit()


#take in root address
root_address = "oaL5KH7UzkN8kGv2fWsrE2JFYYP5uLtHvz"
root_init_value = 1000

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

print("root_block_index = " + str(root_block_index))

# get current block count 
response = requests.get("https://testnet.florincoin.info/api/getblockcount")
current_index = json.loads(response.content.decode("utf-8"))

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

			commentTransferAmount = int(comment_list[1])

			outputlist = []
			for obj in data["vout"]:
				if obj["scriptPubKey"]["type"] == "pubkeyhash":
					temp = []
					temp.append(obj["scriptPubKey"]["addresses"][0]) 
					temp.append(obj["value"])

					outputlist.append(temp)

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

			elif availableTokens < commentTransferAmount:
				print("\nThe transfer amount passed in the comments is more than the user owns\nHence we will be transfer all the user has\n")

				commentTransferAmount = availableTokens

				for output in outputlist:
					if output[0] == inputlist[0][0]:
						continue

					c.execute("SELECT * FROM transactiontable WHERE address=?",(inputlist[0][0],))
					table = c.fetchall()

					pidlst = []
					checksum = 0
					for row in table:
						if checksum >= outputlist[0][1]:
							break
						pidlst.append(row[0])
						checksum = checksum + row[3]

					balance = commentTransferAmount

					for pid in pidlst:
							c.execute("SELECT transferBalance FROM transactiontable WHERE id=?", (pid,))
							temp = c.fetchall()
							temp = temp[0][0]

							if balance <= temp:
								c.execute("INSERT INTO transactiontable (address, parentid, transferBalance) VALUES (?,?,?)", (output[0],pid,balance))
								c.execute("UPDATE transactiontable SET transferBalance=? WHERE id=?", (temp-balance, pid))
								
								c.execute("SELECT id FROM transactiontable ORDER BY id DESC LIMIT 1")
								lastid = c.fetchall()[0][0]
								transferDescription = "$$ " +str(balance) + " tokens transferred to " + str(output[0]) + " from pid = " + str(pid)
								blockchainReference = 'https://testnet.florincoin.info/tx/' + str(transaction)
								c.execute("""INSERT INTO transferlogs (primaryIDReference, transferDescription, transferIDConsumed, blockchainReference)
											VALUES (?,?,?,?)""", ( lastid, transferDescription, pid, blockchainReference))

								transferDescription = "$$ balance in id = " + str(pid) + " UPDATED from " + str(temp) + " to " + str(temp-balance)
								blockchainReference = 'https://testnet.florincoin.info/tx/' + str(transaction)
								c.execute("""INSERT INTO transferlogs (primaryIDReference, transferDescription)
											VALUES (?,?)""", ( pid, transferDescription))

								balance = 0
								conn.commit()
							elif balance > temp:
								c.execute("INSERT INTO transactiontable (address, parentid, transferBalance) VALUES (?,?,?)", (output[0], pid, temp ))
								c.execute("UPDATE transactiontable SET transferBalance=? WHERE id=?", (0, pid))

								c.execute("SELECT id FROM transactiontable ORDER BY id DESC LIMIT 1")
								lastid = c.fetchall()[0][0]
								transferDescription = "$$ " + str(temp) + " tokens transferred to " + str(output[0]) + " from pid = " + str(pid)
								blockchainReference = 'https://testnet.florincoin.info/tx/' + str(transaction)
								c.execute("""INSERT INTO transferlogs (primaryIDReference, transferDescription, transferIDConsumed, blockchainReference)
											VALUES (?,?,?,?)""", ( lastid, transferDescription, pid, blockchainReference))

								transferDescription = "$$ balance in id = " + str(pid) + " UPDATED from " + str(temp) + " to " + str(0)
								blockchainReference = 'https://testnet.florincoin.info/tx/' + str(transaction)
								c.execute("""INSERT INTO transferlogs (primaryIDReference, transferDescription)
											VALUES (?,?)""", ( pid, transferDescription))

								balance = balance - temp
								conn.commit()

			elif availableTokens >= commentTransferAmount:
				for output in outputlist:
					if output[0] == inputlist[0][0]:
						continue

					c.execute("SELECT * FROM transactiontable WHERE address=?",(inputlist[0][0],))
					table = c.fetchall()

					pidlst = []
					checksum = 0
					for row in table:
						if checksum >= outputlist[0][1]:
							break
						pidlst.append(row[0])
						checksum = checksum + row[3]

					balance = commentTransferAmount

					for pid in pidlst:
							c.execute("SELECT transferBalance FROM transactiontable WHERE id=?", (pid,))
							temp = c.fetchall()
							temp = temp[0][0]

							if balance <= temp:
								c.execute("INSERT INTO transactiontable (address, parentid, transferBalance) VALUES (?,?,?)", (output[0],pid,balance))
								c.execute("UPDATE transactiontable SET transferBalance=? WHERE id=?", (temp-balance, pid))

								
								c.execute("SELECT id FROM transactiontable ORDER BY id DESC LIMIT 1")
								lastid = c.fetchall()[0][0]
								transferDescription = str(balance) + " tokens transferred to " + str(output[0]) + " from pid = " + str(pid)
								blockchainReference = 'https://testnet.florincoin.info/tx/' + str(transaction)
								c.execute("""INSERT INTO transferlogs (primaryIDReference, transferDescription, transferIDConsumed, blockchainReference)
											VALUES (?,?,?,?)""", ( lastid, transferDescription, pid, blockchainReference))

								transferDescription = "balance in id = " + str(pid) + " UPDATED from " + str(temp) + " to " + str(temp-balance)
								blockchainReference = 'https://testnet.florincoin.info/tx/' + str(transaction)
								c.execute("""INSERT INTO transferlogs (primaryIDReference, transferDescription)
											VALUES (?,?)""", ( pid, transferDescription))

								balance = 0
								conn.commit()
							elif balance > temp:
								c.execute("INSERT INTO transactiontable (address, parentid, transferBalance) VALUES (?,?,?)", (output[0], pid, temp ))
								c.execute("UPDATE transactiontable SET transferBalance=? WHERE id=?", (0, pid))

								c.execute("SELECT id FROM transactiontable ORDER BY id DESC LIMIT 1")
								lastid = c.fetchall()[0][0]
								transferDescription = str(temp) + " tokens transferred to " + str(output[0]) + " from pid = " + str(pid)
								blockchainReference = 'https://testnet.florincoin.info/tx/' + str(transaction)
								c.execute("""INSERT INTO transferlogs (primaryIDReference, transferDescription, transferIDConsumed, blockchainReference)
											VALUES (?,?,?,?)""", ( lastid, transferDescription, pid, blockchainReference))

								transferDescription = "balance in id = " + str(pid) + " UPDATED from " + str(temp) + " to " + str(0)
								blockchainReference = 'https://testnet.florincoin.info/tx/' + str(transaction)
								c.execute("""INSERT INTO transferlogs (primaryIDReference, transferDescription)
											VALUES (?,?)""", ( pid, transferDescription))


								balance = balance - temp
								conn.commit()


#current_index = 19431
root_block_index = 19428
# run loop and pass blockno 
for blockindex in range(root_block_index + 1, current_index):
	print(blockindex)
	dothemagic(blockindex)

conn.commit()
conn.close()