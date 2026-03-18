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
    def __init__(self, filename, Retry=7, RetrySleep=1, Timeout=300, ID=None, Host='', Port=37373, Encoder=None, Decoder=None):
        self.Version="0.0.0.1.370"
        self.ulResp=['badpayload','locked','unlocked','notowner','notfound']

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
        self.filename=filename
        self.retryLimit=Retry
        self.retrysleep=RetrySleep
        self.timeout=Timeout
        self.port=Port
        self.host=Host

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

    def Talker(self,msg,casefold=True):
        try:
            ls=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ls.settimeout(self.timeout)
            ls.connect((self.host, self.port))
            sfn=ls.makefile('rw')
            sfn.write(msg)
            sfn.flush()
            buf=None
            end=time.time()+self.timeout
            while buf==None and time.time()<end:
                buf=sfn.readline()
            ls.close()
            if len(buf)!=0:
                if casefold==True:
                    return buf.lower().strip()
                else:
                    return buf.strip()
            else:
                return None
        except Exception as err:
            print("Error",err)
            return None

    # Contact Lock server

    def Retry(self,action,expire,casefold=True):
        payload={ "ID":self.ID, "FileName":self.filename, "Action":action,
                  "Expire":str(expire) }

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
        return jdata

    def Put(self,expire,data):
        return self.RetryData("Put",expire,self.encoder(data))

    def Erase(self):
        return self.RetryData("Erase",0,None)

###
### END Library
###

