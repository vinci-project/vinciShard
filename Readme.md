# VINCI-shard API documentation
This is a description of the API for the interaction between nodes implemented over TCP and HTTP transport. The document is intended for developers and researchers of block-technologies.   

## Data Types - types used in the transmitted data structures.    

* *"String"* is a string value of arbitrary content, which is specified by the type of data structure in which it is used. It consists of an ordered set of Unicode characters enclosed in double quotes. All the data types described below are represented by the "String" type when transmitted over the network.   

* *"Timestamp"* - date in Unix-time format (10 characters without separator). Used to indicate the time of the transaction, the creation of a block, and so on.   

* *"Float"* is a floating-point number. It is represented as a "String" using the '.' Character as the separator of the integer and fractional part. An indication of up to 8 digits after the delimiter is allowed.   

* *"Int"* is an unsigned integer.  

* *"IPv4"* is an ip address in IPv4 format in the form of four decimal numbers with a value between 0 and 255, separated by periods. It is represented as "String".  

* *"Digital signature"* is a digital signature obtained with the Secp2561k1 algorithm (the hash function is Blake2b with digest size = 32 bytes).  

* *"Hash"* is the result of executing Blake2b hash function  with digest size = 32 bytes.  

* *"Address"* is a public key representing the address of the sender / recipient. A public key can be obtained from a private key generated using the Secp256k1 algorithm. The public key must be presented in compressed format as a string of hex values.  


* *"Version"* - the current version of the software used - is set in the form of two decimal numbers separated by a period. It is represented as "String".

## Data Format - format of transmitted data.

When transferring data between nodes, a JavaScript-based JSON (JavaScript Object Notation) text format is used. It is acceptable to use containers of the following type:
* A *map* is an unordered set of key pairs: a value enclosed in braces "{}". The key is described by a string, the symbol ":" stands between it and the value. Key-value pairs are separated from each other by commas.  

* An *array* is an ordered set of values. The array is enclosed in square brackets "[]". Values are separated by commas.

The following types of data keys are used:   

| Key Name | Description |
| :---: | --- |
|TT| The first field is necessarily any transaction that specifies its type. The data type is "String"|
|SENDER| Address of the sender of the transaction. The data type is "Address"|
|RECEIVER| Address of the recipient of the transaction. The data type is "Address"|
|ADDRESS| Address for using in votes requesting. The data type is "Address"|
|TTOKEN| Type of token used in this transaction. The data type is "String"|
|CTOKEN| Number of tokens used in this transaction. The data type is "Float"|
|TST| Time of the transaction. The data type is "Timestamp"|
|SIGNATURE| Digital signature of data. The data type is "Digital signature"|
|STEM_SIGNATURE| Digital signature of data made by Stem node. The data type is "Digital signature"|
|NBH| Number of the block to be generated. The data type is "Int"|
|IPADDR| Ip address in IPv4 format. The data type is "IPv4"|
|VERSION| Current version of the software. The data type is "Version"|
|TRANSACTIONS| An array of "ST" format transactions|
|TCOUNT| Number of transactions. The data type is "Int" |
|SIGNATURES| An array of digital signatures of the "SIGNATURE" format|
|HASH| Hash value from the "BLOCK" data. The data type is "Hash" |
|SIGNPB| Digital signature of a pre-commited block of the form "SIGNATURE". The data type is "Digital signature"|
|CLEAN_LIST| Map with a data set in which the data type "Address" is used as the key and the value of the type is "IPv4"|
|BHEIGHT| Current height of the blockchain. The data type is "Int"|
|EVIDENCE_BLOCK| Block height. The data type is "Int" |
|EVIDENCE_TRANSACTION| Evidence transaction. Data format "ST"|
|VOTES| Votes count. Data format "Int"|

The possible values ​​of the "TT" field are:

| Short Name | FulL Name | Description |
| :---: | :---: | --- |
|ST| Simple Transaction | Simplest transaction of transfer of funds|
|CT| Choose Transaction | The node selection transaction that forms the next block|
|AT| Applicant Transaction | Transaction for applying for participation in the network|
|VT| Vote Transaction | Transaction for voting|
|UAT| Unregister Applicant Transaction | Transaction for unregistering previous applicant transaction|
|UVT| Unregister Vote Transaction | Transaction for unregistering previous vote transaction|
|AB| Applicant Block | Transaction for distribution of the candidate block for inclusion in the network of participants of the network. It is both a unit of data for the chain of blockage |
|CB| Commit Block | Transaction to send the block to the stem node|
|BL| Block | Transaction for mass mailing of the block to the network validators|
|SG| Signature | Transaction for voting for the current candidate block|
|PF| Purifier | Transaction of the beginning of a new validation period|
|CP| Complaint | Transaction with evidence of a detected error when working with "ST" transactions|

"BLOCK" is a JSON data object that has fields of the following type:
* "VERSION"
* "SENDER"
* "BHEIGHT"
* "HASH"
* "TCOUNT"
* "TRANSACTIONS"
* "SIGNATURES"
* "TST"
* "SIGNATURE"
* "STEM_SIGNATURE"


## Signing and verification schemes - schemes for signing data and verifying the digital signature for transactions and the type of "BLOCK".
To sign the data it is necessary to form a block of the required type in JSON format without the "SIGNATURE" key. The resulting string should be used in sep256k1 (the hash function is Blake2b with digest size = 32 bytes) as the input data, and the signing itself is done with a private key corresponding to the public key, which is indicated in the "SENDER" field. The received signature should be included in the field "SIGNATURE".
To verify the digital signature, you need to extract the "SIGNATURE" field and remove it from the JSON line. The resulting string should be used in sep256k1 (the hash function is Blake2b with digest size = 32 bytes) as the input data, and the verification itself should be performed with the public key indicated in the "SENDER" field.

To form and verify the digital signature of data type "BLOCK", you must always clear the value of the "SIGNATURES" field.

## Timestamp rules - rules for processing the transaction time.
For transactions of type "ST" the deviation from the current world time is 180 seconds. Otherwise, the transaction is invalid and is rejected.
For transactions of type "CBR" the deviation from the current world time is 3 seconds. Otherwise, the transaction is invalid and is rejected.
For other types of transactions, the deviation from the current world time is 10 seconds.

## Transaction parsing rules.
When processing transactions, the following algorithm determines their validity. If errors are detected at any step of the scan, the transaction is discarded without continuing any further checks.
1. General verification of the correctness of filling the JSON structure without analyzing the data contained in it.
2. Extract the "VERSION" field and determine the compatibility of the source and destination versions of the data. If the versions are incompatible, the transaction is rejected.
3. Extract the field "TT" and define the type of transaction. If this type of transaction does not exist in this version of the software, it is rejected.
4. Check for the presence of necessary data fields for this type of transaction and the absence of extraneous fields. If violations are detected, the transaction is rejected.
5. Determining the validity of data field types. In case of violations, the transaction is rejected.
6. Check timestamp.
7. Verify the digital signature of transaction data. If the check fails, the transaction is rejected.
8. Further checks are specific to each type of transaction.

### Transaction Types
The value fields can be represented in any order.

1. *ST* - simple transaction is the simplest transaction of transfer of funds. Allows you to set the type of the token to be transmitted and the number of tokens. Upon receipt of a request for funds transfer from the system client, the node distributes this transaction to all current validators. It has the following mandatory fields:
 * "TT"
 * "VERSION"
 * "SENDER"
 * "RECEIVER"
 * "TTOKEN"
 * "CTOKEN"
 * "TST"
 * "SIGNATURE"


2. *CT* - choose transaction - the transaction for selecting the node that forms the next block. This transaction is used by the stems node and sent to all current validators.
It has the following mandatory fields:
 * "TT"
 * "VERSION"
 * "SENDER"
 * "NBH" is the number of the next block that the selected node should create
 * "TST"
 * "SIGNATURE"   


3. *AT* is the transaction for the application for participation in the network. This type of transaction is used by anyone who wants to become a member of the next validation period.
It has the following mandatory fields:
 * "TT"
 * "VERSION"
 * "SENDER"
 * "IPADDR" - IPv4 address of the validator
 * "TST"
 * "SIGNATURE"


4. *VT* is the transaction for voting. This type of transaction is used by anyone who wants to vote for a node.
It has the following mandatory fields:
 * "TT"
 * "VERSION"
 * "SENDER"
 * "RECEIVER"
 * "VOTES"
 * "TST"
 * "SIGNATURE"


5. *UAT* is the transaction for unregistering previous Applicant Transaction.
It has the following mandatory fields:
 * "TT"
 * "VERSION"
 * "SENDER"
 * "TST"
 * "SIGNATURE"


6. *UVT* is the transaction for unregistering previous Vote Transaction.
It has the following mandatory fields:
 * "TT"
 * "VERSION"
 * "SENDER"
 * "RECEIVER"
 * "TST"
 * "SIGNATURE"


7. *AB* - applicant block - transaction of distribution of the candidate block for inclusion in the network of participants of the network.
It has the following mandatory fields:
 * "TT"
 * "VERSION"
 * "SENDER"
 * "BLOCK" - the formed block with an empty field "SIGNATURES"
 * "TST"
 * "SIGNATURE"


8. *CB* - commit block - transaction to send the block to the stem node. This type of transaction uses a validator, chosen by the stems node to form the current block.
It has the following mandatory fields:
 * "TT"
 * "VERSION"
 * "SENDER"
 * "BLOCK" - the formed block with the filled field "SIGNATURES
 * "TST"
 * "SIGNATURE"


9. *BL* - block - transaction for mass mailing of the block to the network validators. The n-node uses this type of transaction after receiving from the validator a transaction of type "CB". Transaction indicates that the transferred block is included in the block. It is both a unit of data for the chain of blockage.
It has the following mandatory fields:
 * "TT"
 * "VERSION"
 * "SENDER"
 * "BLOCK"
 * "TST"
 * "SIGNATURE"


10. *SG* - signature - transaction for voting for the current candidate block. When a transaction of type "CB" is received, each validator checks its validity and, if successful, sends a transaction in response to it as a confirmation of the absence of errors.
It has the following mandatory fields:
 * "TT"
 * "VERSION"
 * "SENDER"
 * "HASH" - hash value of data of type "BLOCK"
 * "SIGNPB" - a digital signature of data type "BLOCK"
 * "TST"
 * "SIGNATURE"

11. *PF* - purifier - transaction of the beginning of a new validation period. With this type of transaction, the active validators define the new composition of the current validation period.
It has the following mandatory fields:
 * "TT"
 * "VERSION"
 * "SENDER"
 * "CLEAN_LIST"
 * "BHEIGHT" - block number from which a new validation period begins
 * "TST"
 * "SIGNATURE"


12. *CP* - complaint - transaction with evidence of the detected error when working with "ST" transactions. This type of transaction is used by validators when errors are detected in the work of other validators and is broadcasted to all active validators of the current validation period.
It has the following mandatory fields:
 * "TT"
 * "VERSION"
 * "SENDER"
 * "EVIDENCE_BLOCK"
 * "EVIDENCE_TRANSACTION"
 * "TST"
 * "SIGNATURE"

## REST API Documentation
Description of REST API for requesting data from active validators over the HTTP protocol.

### Wallet API

**Endpoint name:** /wallet/transaction  
**Description:** Endpoint for making simple transactions. Body of POST request should contains transaction json object  
**Method:** POST  
**Parameters:**
* NONE

**Possible answers:**

| Answer | Answer code | Description |
| --- | :---: | --- |
| StatusOk 						                      | 200 | OK
| StatusNotEnoughFundsForCommission              | 601 | NOT ENOUGH FUNDS FOR COMMISSION
| StatusTranNotFound                             | 602 | TRANSACTION NOT FOUND
| StatusInternalServerError                      | 603 | SOMETHING BAD HAPPEND
| StatusUnknownTranType                          | 604 | UNKNOWN TRANSACTION TYPE
| StatusAttrNotFound_TT                          | 605 | CAN NOT FIND ATTRIBUTE - TT
| StatusAttrNotFound_VERSION                     | 606 | CAN NOT FIND ATTRIBUTE - VERSION
| StatusAttrNotFound_SENDER                      | 607 | CAN NOT FIND ATTRIBUTE - SENDER
| StatusAttrNotFound_RECEIVER                    | 608 | CAN NOT FIND ATTRIBUTE - RECEIVER
| StatusAttrNotFound_TTOKEN                      | 609 | CAN NOT FIND ATTRIBUTE - TTOKEN
| StatusAttrNotFound_CTOKEN                      | 610 | CAN NOT FIND ATTRIBUTE - CTOKEN
| StatusAttrNotFound_TST                         | 611 | CAN NOT FIND ATTRIBUTE - TST
| StatusAttrNotFound_SIGNATURE                   | 612 | CAN NOT FIND ATTRIBUTE - SIGNATURE
| StatusWrongAttr_TT                             | 618 | WRONG ATTRIBUTE - TT
| StatusWrongAttr_VERSION                        | 619 | WRONG ATTRIBUTE - VERSION
| StatusWrongAttr_SENDER                         | 620 | WRONG ATTRIBUTE - SENDER
| StatusWrongAttr_RECEIVER                       | 621 | WRONG ATTRIBUTE - RECEIVER
| StatusWrongAttr_TST                            | 622 | WRONG ATTRIBUTE - TST
| StatusWrongAttr_CTOKEN                         | 623 | WRONG ATTRIBUTE - CTOKEN
| StatusWrongAttr_Signature                      | 624 | WRONG ATTRIBUTE - SIGNATURE
| StatusSignVerifyError                          | 625 | CAN'T VERIFY SIGNATURE
| StatusDontSendYourself                         | 626 | YOU CAN'T SEND YOURSELF
| StatusTranFailed                               | 627 | TRANSACTION FAILED
| StatusWrongDataFormat                          | 629 | WRONG DATA FORMAT
| StatusWrongAttr_TTOKEN                         | 630 | WRONG ATTRIBUTE - TTOKEN
| StatusWrongAttr_IPADDR                         | 632 | WRONG ATTRIBUTE - IPADDR
| StatusWrongAttr_VOTES                          | 632 | WRONG ATTRIBUTE - VOTES




___

**Endpoint name:** /wallet/getBalance  
**Description:** Endpoint for requesting user balance. You can request multiple balances  
**Method:** GET    
**Parameters:**
* "TTOKEN"
* "SENDER"   

**Possible answers:**

| Answer | Answer code | Description |
| --- | :---: | --- |
| StatusOk 						                      | 200 | OK
| StatusAttrNotFound_SENDER                      | 607 | CAN NOT FIND ATTRIBUTE - SENDER
| StatusAttrNotFound_TTOKEN                      | 609 | CAN NOT FIND ATTRIBUTE - TTOKEN
| StatusWrongAttr_SENDER                         | 619 | WRONG ATTRIBUTE - SENDER

**Request example:**
```http
http://x.x.x.x:port/wallet/getBalance?TTOKEN=VNC&SENDER=022a461b6a62d520860c92e178cf56132885852421f30e1e37b031e6f7547613fc&SENDER=0342bc360605da84c52ec998e3517acc052e73ebb9627f18085c41abdc4264d5c6&SENDER=03afdc85ab80b9263f82d43eb5059eb18b0bcc38ce371ff266af40717699c20d52

```
**Answer example:**
```json
{"BALANCE":{"022a461b6a62d520860c92e178cf56132885852421f30e1e37b031e6f7547613fc":"0","0342bc360605da84c52ec998e3517acc052e73ebb9627f18085c41abdc4264d5c6":"0","03afdc85ab80b9263f82d43eb5059eb18b0bcc38ce371ff266af40717699c20d52":"0"}}
```
___

**Endpoint name:** /wallet/tranStatus  
**Description:** Endpoint for checking transaction status  
**Method:** GET  
**Parameters:**
* "KEY"

**Possible answers:**

| Answer | Answer code | Description |
| --- | :---: | --- |
| StatusOk 						    | 200 | OK
| StatusTranNotFound                | 602 | TRANSACTION NOT FOUND
| StatusAttrNotFound_KEY                         | 613 | CAN NOT FIND ATTRIBUTE - KEY
| StatusWrongAttr_KEY                            | 617 | WRONG ATTRIBUTE - KEY
| StatusTranFailed                  | 627 | TRANSACTION FAILED

**Request example:**
```http
http://x.x.x.x:port/wallet/tranStatus?KEY=444ad77714df3cec21c2ea5b96a65d1e07bc1e8f519d8bdf30f19c9e446f78ff

```

___

### Blockchain API


**Endpoint name:** /blockchain/getBHeight  
**Description:** Endpoint for requesting current blockchain height  
**Method:** GET  
**Parameters:**
* NONE

**Possible answers:**

| Answer | Answer code | Description |
| --- | :---: | --- |
| StatusOk 						    | 200 | OK

**Request example:**
```http
http://x.x.x.x:port/blockchain/getBHeight
```
**Answer example:**
```json
{"BHEIGHT":"28"}
```
___

**Endpoint name:** /blockchain/getTran  
**Description:** Endpoint for getting transaction by key  
**Method:** GET  
**Parameters:**
* "KEY"

**Possible answers:**

| Answer | Answer code | Description |
| --- | :---: | --- |
| StatusOk 						    | 200 | OK
| StatusAttrNotFound_KEY                         | 613 | CAN NOT FIND ATTRIBUTE - KEY
| StatusWrongAttr_KEY                            | 617 | WRONG ATTRIBUTE - KEY
| StatusDataNotFound                             | 628 | DATA NOT FOUND

**Request example:**
```http
http://x.x.x.x:port/blockchain/getTran?KEY=08abb325729edbaad5acd52a28477dea00e0f844dca2531bfa072950ac747938
```
**Answer example:**
```json
{
  "TT": "ST",
  "SENDER": "0323f264fd64a684db1e36a2c97b58867e0625f797008206216576fea2114bdbca",
  "RECEIVER": "02cf4d38c80a3a4571a9ee7c6c8cc3961ff684e9b7e52622b8aaf16f5d1974fd87",
  "TTOKEN": "VNC",
  "CTOKEN": "2.9130000000000003",
  "TST": "1540475286",
  "SIGNATURE": "d5df7eb718cca4c5bba066d8655abacf15dfd0c4c244fe1d450cf1831854ece144cf4b5e83d3203bf2b4ecf77401e7596485982e48a7b4ad31f04d89f6ce71aa01"
}
```

___

**Endpoint name:** /blockchain/getBlock  
**Description:** Endpoint for getting block by height  
**Method:** GET  
**Parameters:**
* "BHEIGHT"

**Possible answers:**

| Answer | Answer code | Description |
| --- | :---: | --- |
| StatusOk 						    | 200 | OK
| StatusDataNotFound           | 627 | DATA NOT FOUND
| StatusWrongAttr_BHEIGHT                        | 631 | WRONG ATTRIBUTE - BHEIGHT
| StatusAttrNotFound_BHEIGHT                     | 634 | CAN NOT FIND ATTRIBUTE - BHEIGHT

**Request example:**
```http
http://x.x.x.x:port/blockchain/getBlock?BHEIGHT=28
```
**Answer example:**
```json
{
    "TT": "BL",
    "SENDER": "0323f264fd64a684db1e36a2c97b58867e0625f797008206216576fea2114bdbca",
    "VERSION": "1.0",
    "TCOUNT": 0,
    "BHEIGHT": 1,
    "TRANSACTIONS": [],
    "SIGNATURE": "5d52370ba4bb7db1c420ec50065b7e8ff8316dacea016d2b436e105c8deabe264852d704f4f647fcf045cb732fd52e63e0447dfcbdacb37a5ef969d6175c016a01"
}
```

___

**Endpoint name:** /blockchain/getVersion  
**Description:** Endpoint for getting version of node software  
**Method:** GET  
**Parameters:**
* NONE

**Possible answers:**

| Answer | Answer code | Description |
| --- | :---: | --- |
| StatusOk 						    | 200 | OK

**Request example:**
```http
http://x.x.x.x:port/blockchain/getVersion
```
**Answer example:**
```json
{"VERSION": "0.1.0"}
```

___

**Endpoint name:** /blockchain/getNodes  
**Description:** Endpoint for getting current nodes (twigs and stem) of shard  
**Method:** GET  
**Parameters:**
* NONE

**Possible answers:**

| Answer | Answer code | Description |
| --- | :---: | --- |
| StatusOk 						    | 200 | OK

**Request example:**
```http
http://x.x.x.x:port/blockchain/getNodes
```
**Answer example:**
```json
{
  "NLIST": [
    {
      "ADDRESS": "x.x.x.x",
      "TYPE": "1",
      "PUBLICKEY": "0323f264fd64a684db1e36a2c97b58867e0625f797008206216576fea2114bdbca"
    }
  ]
}
```
