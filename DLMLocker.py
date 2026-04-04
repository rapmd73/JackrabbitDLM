#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Jackrabbit DLM
# 2021 Copyright © Robert APM Darin
# All rights reserved unconditionally.

import sys
sys.path.append('/home/JackrabbitDLM')
import os
import datetime
import time
import random
import socket
import json
import secrets

# Reusable file locks
#
# fw=Locker(filename)
# fw.Lock()
# ( do somwething )
# fw.Unlock()

# { "ID":"DEADBEEF", "FileName":"testData", "Action":"Lock", "Expire":"300" }

class Locker:
    # Initialize the file name
    def __init__(self, filename, Retry=7, RetrySleep=1, Timeout=300, ID=None, Host='', Port=37373, Encoder=None, Decoder=None, name=None, identity=None):
        self.VERSION="0.0.0.1.380"
        self.ulResp=['badpayload','locked','unlocked','notowner','notfound','version']

        # Encoding String
        self.ALPHABET='1aA2bB3cC4dD5eE6fF7gG8hH9iI0jJ!kK@lL#mM$nN%oO^pP&qQ*rR(sS)tT/uU?vV=wW+xX;yY:zZ'
        self.BASELEN=len(self.ALPHABET)

        # Pre-calculate for speed (O(1) lookups)
        self.ENCODE_TABLE=[self.ALPHABET[b//self.BASELEN]+self.ALPHABET[b%self.BASELEN] for b in range(256)]
        self.DECODE_TABLE={self.ALPHABET[b//self.BASELEN]+self.ALPHABET[b%self.BASELEN]: b for b in range(256)}

        # Set up default en/decorder
        self.encoder=Encoder if Encoder else self.dlmEncode
        self.decoder=Decoder if Decoder else self.dlmDecode

        if ID==None:
            self.ID=self.GetID()
        else:
            self.ID=ID
        self.name=name
        self.identity=identity
        self.filename=filename
        self.retryLimit=Retry
        self.retrysleep=RetrySleep
        self.timeout=Timeout
        self.port=Port
        self.host=Host
        if self.host=='':
            self.host='127.0.0.1'
        self.Error=None

    def dlmEncode(self,data_bytes):
        if isinstance(data_bytes, str):
            data_bytes = data_bytes.encode('utf-8')

        return "".join(self.ENCODE_TABLE[b] for b in data_bytes)

    def dlmDecode(self,encoded_str):
        if not encoded_str:
            return b""
        return bytes(self.DECODE_TABLE[encoded_str[i:i+2]] for i in range(0, len(encoded_str), 2))

    # Generate an ID String

    def GetID(self):
        random.seed(time.time())
        l=random.randrange(37,73)
        return secrets.token_urlsafe(l)

    # Contact the Locker Server and WAIT for response. NOT thread safe.

    def Talker(self, msg, casefold=True):
        self.Error=None
        try:
            # 1. create_connection() handles the 115 error internally.
            # It blocks ONLY until connected or self.timeout is hit.
            ls = socket.create_connection((self.host, self.port), timeout=self.timeout)

            # 2. Use makefile for easy line-based reading.
            sfn = ls.makefile('rw', buffering=1)

            sfn.write(msg + '\n') # Ensure newline for readline to work
            sfn.flush()

            # 3. No while loop needed; readline() respects the socket timeout.
            buf = sfn.readline()

            # 4. Clean up before returning
            sfn.close()
            ls.close()

            if buf:
                res = buf.strip()
                return res.lower() if casefold else res
            return None

        except (socket.timeout, OSError) as err:
            self.Error=str(err)
            return None

    # Contact Lock server

    def Retry(self,action,expire,casefold=True):
        payload={ "ID":self.ID, "FileName":self.filename, "Action":action,
                  "Expire":str(expire) }

        if self.name or self.identity:
            payload['Name']=self.name
            payload['Identity']=self.identity

        outbuf=json.dumps(payload)+'\n'

        retry=0
        done=False
        while not done:
            buf=self.Talker(outbuf,casefold)
            if buf==None:
                if retry>self.retryLimit:
                    return 'failure'
                retry+=1
                time.sleep(self.retrysleep)
            else:
                if len(buf)!=0:
                    # Received JSON, brak done and get status
                    try:
                        bData=json.loads(buf)
                        s='Status'
                        if casefold:
                            s='status'
                        buf=bData[s]
                    except:
                        buf=None
                    if casefold==True and buf!=None:
                        buf=buf.lower()
                    if buf!=None and buf in self.ulResp:
                        done=True
                    else:
                        time.sleep(self.retrysleep)
                else:
                    time.sleep(self.retrysleep)
        return buf

    def RetryData(self,action,expire,data):
        payload={ "ID":self.ID, "FileName":self.filename, "Action":action,
                  "Expire":str(expire), "DataStore":data }

        if self.name or self.identity:
            payload['Name']=self.name
            payload['Identity']=self.identity

        outbuf=json.dumps(payload)+'\n'

        retry=0
        done=False
        while not done:
            buf=self.Talker(outbuf,casefold=False)
            if buf==None:
                if retry>self.retryLimit:
                    return 'failure'
                retry+=1
                time.sleep(self.retrysleep)
            else:
                if len(buf)!=0:
                    done=True
                else:
                    time.sleep(self.retrysleep)
        return buf

    # Lock the file

    def Lock(self,expire=300):
        return self.Retry("Lock",expire,casefold=True)

    # Check if the item is locked. Will aquire if not. Single pass, no loop

    def IsLocked(self,expire=300):
        payload={ "ID":self.ID, "FileName":self.filename, "Action":"Lock",
                  "Expire":str(expire) }

        if self.name or self.identity:
            payload['Name']=self.name
            payload['Identity']=self.identity

        outbuf=json.dumps(payload)+'\n'

        buf=self.Talker(outbuf,casefold=True)
        if buf==None:
            return 'failure'

        try:
            bData=json.loads(buf)
        except:
            return None

        buf=None
        if 'status' in bData:
            buf=bData['status']
        return buf

    # Unlock the file

    def Unlock(self):
        return self.Retry("Unlock",0)

    # In order to decode the DataStore, this function MUST convert to a
    # json payload.

    def Get(self):
        data=self.RetryData("Get",0,None)

        # crude, but effective
        try:
            jdata=json.loads(data)
        except:
            return None

        if jdata is not None and 'DataStore' in jdata:
            jdata['DataStore']=self.decoder(jdata['DataStore'])
            if isinstance(jdata['DataStore'],bytes):
                jdata['DataStore']=jdata['DataStore'].decode('utf-8')

        return jdata

    def Put(self,expire,data):
        return self.RetryData("Put",expire,self.encoder(data))

    def Erase(self):
        return self.RetryData("Erase",0,None)

    # Get running version

    def Version(self):
        data=self.RetryData("Version",0,None)
        sv='Error'
        try:
            data=json.loads(data)
        except:
            pass

        if 'ID' in data:
            sv=data['ID']
        lv=self.VERSION
        v=f"{sv}:{lv}"
        return v

    # If JackrabbitDLM is loaded, the string will be in the return

    def IsDLM(self):
        v=self.Version()
        if 'JackrabbitDLM' in v:
            return True
        return False

###
### END Library
###

