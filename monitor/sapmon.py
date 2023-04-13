#!/usr/bin/env python3
# 
#       SapMonitor payload deployed on collector VM
#
#       License:        GNU General Public License (GPL)
#       (c) 2019        Microsoft Corp.
#

from abc import ABC, abstractmethod
import argparse
from azure_storage_logging.handlers import QueueStorageHandler
from azure.mgmt.storage import StorageManagementClient
from azure.common.credentials import BasicTokenAuthentication
import base64
from datetime import date, datetime, timedelta
import decimal
import hashlib
import hmac
import http.client as http_client
import json
import logging
import logging.config
import os
import pyhdb
import re
import requests
import sys
import traceback

###############################################################################

PAYLOAD_VERSION                   = "0.6.5"
PAYLOAD_DIRECTORY                 = os.path.dirname(os.path.realpath(__file__))
STATE_FILE = f"{PAYLOAD_DIRECTORY}/sapmon.state"
TIME_FORMAT_LOG_ANALYTICS         = "%a, %d %b %Y %H:%M:%S GMT"
TIME_FORMAT_JSON                  = "%Y-%m-%dT%H:%M:%S.%fZ"
DEFAULT_CONSOLE_LOG_LEVEL         = logging.INFO
DEFAULT_FILE_LOG_LEVEL            = logging.INFO
DEFAULT_QUEUE_LOG_LEVEL           = logging.DEBUG
LOG_FILENAME = f"{PAYLOAD_DIRECTORY}/sapmon.log"
KEYVAULT_NAMING_CONVENTION        = "sapmon-kv-%s"
STORAGE_ACCOUNT_NAMING_CONVENTION = "sapmonsto%s"
STORAGE_QUEUE_NAMING_CONVENTION   = "sapmon-que-%s"

###############################################################################

LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": True,
    "formatters": {
        "detailed": {
            "format": "[%(process)d] %(asctime)s %(levelname).1s %(funcName)s:%(lineno)d %(message)s",
        },
        "simple": {
            "format": "%(levelname)-8s %(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "level": DEFAULT_CONSOLE_LOG_LEVEL,
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "detailed",
            "level": DEFAULT_FILE_LOG_LEVEL,
            "filename": LOG_FILENAME,
            "maxBytes": 10000000,
            "backupCount": 10,
        },
    },
    "root": {
        "level": logging.DEBUG,
        "handlers": ["console", "file"],
    }
}

###############################################################################

ERROR_GETTING_AUTH_TOKEN       = 10
ERROR_SETTING_KEYVAULT_SECRET  = 20
ERROR_KEYVAULT_NOT_FOUND       = 21
ERROR_GETTING_LOG_CREDENTIALS  = 22
ERROR_GETTING_HANA_CREDENTIALS = 23
ERROR_HANA_CONNECTION          = 30

###############################################################################

sapmonContentTypes = {
   "HANA": "SapHanaCheck"
}

class SapmonCheck(ABC):
   """
   Implements a monitoring check inside SAP Monitor
   """
   version       = ""
   name          = ""
   description   = ""
   customLog     = ""
   frequencySecs = 0
   state         = {}
   def __init__(self, version, name, description, customLog, frequencySecs, enabled=True):
      self.version       = version
      self.name          = name
      self.description   = description
      self.customLog     = customLog
      self.frequencySecs = frequencySecs
      self.state         = {
         "isEnabled":    enabled,
         "lastRunLocal": None,
      }

   @abstractmethod
   def run(self):
      pass

   @abstractmethod
   def updateState(self):
      pass

class SapHanaCheck(SapmonCheck):
   """
   Implements a SAP HANA-specific monitoring check
   """
   COL_SERVER_UTC      = "_SERVER_UTC"
   COL_TIMESERIES_UTC  = "_TIMESERIES_UTC"
   COL_CONTENT_VERSION = "CONTENT_VERSION"
   COL_SAPMON_VERSION  = "SAPMON_VERSION"
   TIME_FORMAT_HANA    = "%Y-%m-%d %H:%M:%S.%f"

   prefix             = "HANA"
   isTimeSeries       = False
   colIndex           = {}
   lastResult         = []
   def __init__(self, hanaOptions, **kwargs):
      super().__init__(**kwargs)
      self.query                  = hanaOptions["query"]
      self.isTimeSeries           = hanaOptions.get("isTimeSeries", False)
      self.colTimeGenerated       = self.COL_TIMESERIES_UTC if self.isTimeSeries else self.COL_SERVER_UTC
      self.initialTimespanSecs    = hanaOptions.get("initialTimespanSecs", 0)
      self.state["lastRunServer"] = None

   def prepareSql(self):
      """
      Prepare the SQL statement based on the check-specific query
      """
      logger.info("preparing SQL statement")
      # insert logic to get server UTC time (_SERVER_UTC)
      sqlTimestamp = f", '{self.version}' AS {self.COL_CONTENT_VERSION}, '{PAYLOAD_VERSION}' AS {self.COL_SAPMON_VERSION}, CURRENT_UTCTIMESTAMP AS {self.COL_SERVER_UTC} FROM DUMMY,"
      logger.debug(f"sqlTimestamp={sqlTimestamp}")
      sql = self.query.replace(" FROM", sqlTimestamp, 1)
      # if time series, insert time condition
      if self.isTimeSeries:
         if lastRunServer := self.state.get("lastRunServer", None):
            if not isinstance(lastRunServer, datetime):
               logger.error(
                   f"lastRunServer={str(lastRunServer)} has not been de-serialized into a valid datetime object"
               )
               return None
            try:
               lastRunServerUtc = f"'{lastRunServer.strftime(self.TIME_FORMAT_HANA)}'"
            except:
               logger.error(
                   f"could not format lastRunServer={str(lastRunServer)} into HANA format"
               )
               return None
            logger.info(
                f"time series query for check {self.prefix}_{self.name} has been run at {lastRunServerUtc}, filter out only new records since then"
            )
         else:
            logger.info("time series query for check %s_%s has never been run, applying initalTimespanSecs=%d" % \
                  (self.prefix, self.name, self.initialTimespanSecs))
            lastRunServerUtc = "ADD_SECONDS(NOW(), i.VALUE*(-1) - %d)" % self.initialTimespanSecs
         logger.debug(f"lastRunServerUtc = {lastRunServerUtc}")
         sql = sql.replace("{lastRunServerUtc}", lastRunServerUtc, 1)
         logger.debug(f"sql={sql}")
            # sys.exit()
      return sql

   def run(self, hana):
      """
      Run this SAP HANA-specific check
      """
      logger.info("running HANA SQL query")
      if sql := self.prepareSql():
         self.colIndex, self.lastResult = hana.runQuery(sql)
         self.updateState(hana)
      return self.convertResultIntoJson()

   def calculateResultHash(self):
      """
      Calculate the MD5 hash of a result set
      """
      logger.info("calculating SQL result hash")
      resultHash = None
      if len(self.lastResult) == 0:
         logger.debug("SQL result is empty")
      else:
         try:
            resultHash = hashlib.md5(str(self.lastResult).encode("utf-8")).hexdigest()
            logger.debug(f"resultHash={resultHash}")
         except Exception as e:
            logger.error(f"could not calculate result hash ({e})")
      return resultHash

   def convertResultIntoJson(self):
      """
      Convert the last query result into a JSON-formatted string (as required by Log Analytics)
      """
      logger.info("converting result set into JSON")
      logData  = []
      jsonData = "{}"
      for r in self.lastResult:
         logItem = {
             c: r[self.colIndex[c]]
             for c in self.colIndex.keys() if c == self.colTimeGenerated
             or not c.startswith("_") and c != "DUMMY"
         }
         logData.append(logItem)
      try:
         resultJson = json.dumps(logData, sort_keys=True, indent=4, cls=_JsonEncoder)
         logger.debug(f"resultJson={resultJson}")
      except Exception as e:
         logger.error(f"could not encode logItem={logItem} into JSON ({e})")
      return resultJson

   def updateState(self, hana):
      """
      Update the internal state of this check (including last run times)
      """
      logger.info(f"updating internal state of check {self.prefix}_{self.name}")
      self.state["lastRunLocal"] = datetime.utcnow()
      if len(self.lastResult) == 0:
         logger.info("SQL result is empty")
         return False
      self.state["lastRunServer"] = self.lastResult[0][self.colIndex[self.COL_SERVER_UTC]]
      self.state["lastResultHash"] = self.calculateResultHash()
      logger.info("internal state successfully updated")
      return True

###############################################################################

class SapHana:
   """
   Provide access to a HANA Database (HDB) instance
   """
   TIMEOUT_HANA_SECS = 5

   connection = None
   cursor     = None
   def __init__(self, host = None, port = None, user = None, password = None, hanaDetails = None):
      logger.info("initializing HANA instance")
      if hanaDetails:
         self.host     = hanaDetails["HanaHostname"]
         self.port     = hanaDetails["HanaDbSqlPort"]
         self.user     = hanaDetails["HanaDbUsername"]
         self.password = hanaDetails["HanaDbPassword"]
      else:
         self.host     = host
         self.port     = port
         self.user     = user
         self.password = password

   def connect(self):
      """
      Connect to a HDB instance
      """
      self.connection = pyhdb.Connection(
         host = self.host,
         port = self.port,
         user = self.user,
         password = self.password,
         timeout = self.TIMEOUT_HANA_SECS,
         )
      self.connection.connect()
      self.cursor = self.connection.cursor()

   def disconnect(self):
      """
      Close an open HDB connection
      """
      self.connection.close()

   def runQuery(self, sql):
      """
      Execute a SQL query
      """
      self.cursor.execute(sql)
      colIndex = {col[0] : idx for idx, col in enumerate(self.cursor.description)}
      return colIndex, self.cursor.fetchall()

###############################################################################

class REST:
   """
   Provide access to a REST endpoint
   """
   @staticmethod
   def sendRequest(endpoint, method = requests.get, params = {}, headers = {}, timeout = 5, data = None, debug = False):
      if debug:
         http_client.HTTPConnection.debuglevel = 1
         logging.basicConfig()
         logging.getLogger().setLevel(logging.DEBUG)
         requests_log = logging.getLogger("requests.packages.urllib3")
         requests_log.setLevel(logging.DEBUG)
         requests_log.propagate = True
      try:
         response = method(
            endpoint,
            params  = params,
            headers = headers,
            timeout = timeout,
            data    = data,
            )
         if response.status_code == requests.codes.ok:
            contentType = response.headers.get("content-type")
            if contentType and contentType.find("json") >= 0:
               return json.loads(response.content.decode("utf-8"))
            else:
               return response.content
         else:
            print(response.content) # poor man's logging
            response.raise_for_status()
      except Exception as e:
         logger.error(f"could not send HTTP request ({e})")
         return None

###############################################################################

class AzureInstanceMetadataService:
   """
   Provide access to the Azure Instance Metadata Service (IMS) inside the VM
   """
   uri     = "http://169.254.169.254/metadata"
   params  = {"api-version": "2018-02-01"}
   headers = {"Metadata": "true"}

   @staticmethod
   def _sendRequest(endpoint, params = {}, headers = {}):
      params.update(AzureInstanceMetadataService.params)
      headers.update(AzureInstanceMetadataService.headers)
      return REST.sendRequest(
          f"{AzureInstanceMetadataService.uri}/{endpoint}",
          params=params,
          headers=headers,
      )

   @staticmethod
   def getComputeInstance(operation):
      """
      Get the compute instance for the current VM via IMS
      """
      logger.info("getting compute instance")
      computeInstance = None
      try:
         computeInstance = AzureInstanceMetadataService._sendRequest(
             "instance",
             headers={
                 "User-Agent": f"SAP Monitor/{PAYLOAD_VERSION} ({operation})"
             },
         )["compute"]
         logger.debug(f"computeInstance={computeInstance}")
      except Exception as e:
         logging.error(f"could not obtain instance metadata ({e})")
      return computeInstance

   @staticmethod
   def getAuthToken(resource, msiClientId = None):
      """
      Get an authentication token via IMDS
      """
      logger.info(
          f'getting auth token for resource={resource}{f", msiClientId={msiClientId}" if msiClientId else ""}'
      )
      authToken = None
      try:
         authToken = AzureInstanceMetadataService._sendRequest(
            "identity/oauth2/token",
            params = {"resource": resource, "client_id": msiClientId}
            )["access_token"]
      except Exception as e:
         logger.critical(f"could not get auth token ({e})")
         sys.exit(ERROR_GETTING_AUTH_TOKEN)
      return authToken

###############################################################################

class AzureKeyVault:
   """
   Provide access to an Azure KeyVault instance
   """
   params  = {"api-version": "7.0"}

   def __init__(self, kvName, msiClientId = None):
      logger.info(f"initializing KeyVault {kvName}")
      self.kvName  = kvName
      self.uri = f"https://{kvName}.vault.azure.net"
      self.token   = AzureInstanceMetadataService.getAuthToken("https://vault.azure.net", msiClientId)
      self.headers = {
          "Authorization": f"Bearer {self.token}",
          "Content-Type": "application/json",
      }

   def _sendRequest(self, endpoint, method = requests.get, data = None):
      """
      Easy access to KeyVault REST endpoints
      """
      response = REST.sendRequest(
         endpoint,
         method  = method,
         params  = self.params,
         headers = self.headers,
         data    = data,
         )
      if response and "value" in response:
         return (True, response["value"])
      return (False, None)

   def setSecret(self, secretName, secretValue):
      """
      Set a secret in the KeyVault
      """
      logger.info(f"setting KeyVault secret for secretName={secretName}")
      success = False
      try:
         (success, response) = self._sendRequest(
             f"{self.uri}/secrets/{secretName}",
             method=requests.put,
             data=json.dumps({"value": secretValue}),
         )
      except Exception as e:
         logger.critical(f"could not set KeyVault secret ({e})")
         sys.exit(ERROR_SETTING_KEYVAULT_SECRET)
      return success

   def getSecret(self, secretId):
      """
      Get the current version of a specific secret in the KeyVault
      """
      logger.info(f"getting KeyVault secret for secretId={secretId}")
      secret = None
      try:
         (success, secret) = self._sendRequest(secretId)
      except Exception as e:
         logger.error(f"could not get KeyVault secret for secretId={secretId} ({e})")
      return secret

   def getCurrentSecrets(self):
      """
      Get the current versions of all secrets inside the customer KeyVault
      """
      logger.info("getting current KeyVault secrets")
      secrets = {}
      try:
         (success, kvSecrets) = self._sendRequest(f"{self.uri}/secrets")
         logger.debug(f"kvSecrets={kvSecrets}")
         for k in kvSecrets:
            id = k["id"].split("/")[-1]
            secrets[id] = self.getSecret(k["id"])
      except Exception as e:
         logger.error(f"could not get current KeyVault secrets ({e})")
      return secrets

   def exists(self):
      """
      Check if a KeyVault with a specified name exists
      """
      logger.info(f"checking if KeyVault {self.kvName} exists")
      try:
         (success, response) = self._sendRequest(f"{self.uri}/secrets")
      except Exception as e:
         logger.error(f"could not determine is KeyVault {kvName} exists ({e})")
      if success:
         logger.info(f"KeyVault {self.kvName} exists")
      else:
         logger.info(f"KeyVault {self.kvName} does not exist")
      return success

###############################################################################

class AzureLogAnalytics:
   """
   Provide access to an Azure Log Analytics WOrkspace
   """
   def __init__(self, workspaceId, sharedKey):
      logger.info("initializing Log Analytics instance")
      self.workspaceId = workspaceId
      self.sharedKey   = sharedKey
      self.uri = f"https://{workspaceId}.ods.opinsights.azure.com/api/logs?api-version=2016-04-01"
      return

   def ingest(self, logType, jsonData, colTimeGenerated):
      """
      Ingest JSON payload as custom log to Log Analytics
      """
      def buildSig(content, timestamp):
         stringHash  = """POST
%d
application/json
x-ms-date:%s
/api/logs""" % (len(content), timestamp)
         bytesHash   = bytes(stringHash, encoding="utf-8")
         decodedKey  = base64.b64decode(self.sharedKey)
         encodedHash = base64.b64encode(hmac.new(
            decodedKey,
            bytesHash,
            digestmod=hashlib.sha256).digest()
         )
         stringHash = encodedHash.decode("utf-8")
         return f"SharedKey {self.workspaceId}:{stringHash}"

      logger.info("ingesting telemetry into Log Analytics")
      timestamp = datetime.utcnow().strftime(TIME_FORMAT_LOG_ANALYTICS)
      headers = {
         "content-type":  "application/json",
         "Authorization": buildSig(jsonData, timestamp),
         "Log-Type":      logType,
         "x-ms-date":     timestamp,
         "time-generated-field": colTimeGenerated,
      }
      logger.debug(f"data={jsonData}")
      response = None
      try:
         response = REST.sendRequest(
            self.uri,
            method  = requests.post,
            headers = headers,
            data    = jsonData,
            )
      except Exception as e:
         logger.error(f"could not ingest telemetry into Log Analytics ({e})")
      return response

###############################################################################

class AzureStorageQueue():
    accountName = None
    name = None
    token = {}
    subscriptionId = None
    resourceGroup = None
    def __init__(self, sapmonId, msiClientID, subscriptionId, resourceGroup):
        """
        Retrieve the name of the storage account and storage queue
        """
        self.accountName = STORAGE_ACCOUNT_NAMING_CONVENTION % sapmonId
        self.name = STORAGE_QUEUE_NAMING_CONVENTION % sapmonId
        tokenResponse = AzureInstanceMetadataService.getAuthToken(resource="https://management.azure.com/", msiClientId=msiClientID)
        self.token["access_token"] = tokenResponse
        self.subscriptionId = subscriptionId
        self.resourceGroup = resourceGroup

    def getAccessKey(self):
        """
        Get the access key to the storage queue
        """
        storageclient = StorageManagementClient(credentials=BasicTokenAuthentication(self.token), subscription_id=self.subscriptionId)
        storageKeys = storageclient.storage_accounts.list_keys(resource_group_name=self.resourceGroup, account_name=self.accountName)
        if storageKeys is None or len(storageKeys.keys) <= 0 :
           print("Could not retrive storage keys of the storage account{0}".format(self.accountName))
           return None
        return storageKeys.keys[0].value
################################################################################

class _Context(object):
   """
   Internal context handler
   """
   hanaInstances   = []
   availableChecks = []

   def __init__(self, operation):
      logger.info("initializing context")
      self.vmInstance = AzureInstanceMetadataService.getComputeInstance(operation)
      self.vmTags = dict(map(lambda s : s.split(':'), self.vmInstance["tags"].split(";")))
      logger.debug(f"vmTags={self.vmTags}")
      self.sapmonId = self.vmTags["SapMonId"]
      logger.debug(f"sapmonId={self.sapmonId} ")
      self.azKv = AzureKeyVault(KEYVAULT_NAMING_CONVENTION % self.sapmonId, self.vmTags.get("SapMonMsiClientId", None))
      if not self.azKv.exists():
         sys.exit(ERROR_KEYVAULT_NOT_FOUND)
      self.initChecks()
      self.readStateFile()
      self.addQueueLogHandler()
      return
 
   def addQueueLogHandler(self):
      global logger
      try:
         storageQueue = AzureStorageQueue(sapmonId=self.sapmonId, msiClientID=self.vmTags.get("SapMonMsiClientId", None),subscriptionId=self.vmInstance["subscriptionId"],resourceGroup=self.vmInstance["resourceGroupName"])
         storageKey = storageQueue.getAccessKey()
         queueStorageLogHandler = QueueStorageHandler(account_name=storageQueue.accountName,
                                                   account_key=storageKey,
                                                   protocol="https",
                                                   queue=storageQueue.name)
         queueStorageLogHandler.level = DEFAULT_QUEUE_LOG_LEVEL
         formatter = logging.Formatter(LOG_CONFIG["formatters"]["detailed"]["format"])
         queueStorageLogHandler.setFormatter(formatter)
      except Exception:
         logger.error(
             f"could not add handler for the storage queue logging: {traceback.format_exc()} "
         )
         return
      logger.addHandler(queueStorageLogHandler)
      return

   def initChecks(self):
      """
      Initialize all sapmonChecks (pre-delivered via JSON files)
      """
      logger.info("initializing monitoring checks")
      for filename in os.listdir(PAYLOAD_DIRECTORY):
         if not filename.endswith(".json"):
            continue
         contentFullPath = f"{PAYLOAD_DIRECTORY}/{filename}"
         logger.debug(f"contentFullPath={contentFullPath}")
         try:
            with open(contentFullPath, "r") as file:
               data = file.read()
            jsonData = json.loads(data)
         except Exception as e:
            logger.error(f"could not load content file {contentFullPath} ({e})")
         contentType = jsonData.get("contentType", None)
         if not contentType:
            logging.error(
                f"content type not specified in content file {contentFullPath}, skipping"
            )
            continue
         contentVersion = jsonData.get("contentVersion", None)
         if not contentVersion:
            logging.error(
                f"content version not specified in content file {contentFullPath}, skipping"
            )
            continue
         checks = jsonData.get("checks", [])
         if contentType not in sapmonContentTypes:
            logging.error(
                f"unknown content type {contentType}, skipping content file {contentFullPath}"
            )
            continue
         for checkOptions in checks:
            try:
               logging.info(f"instantiate check of type {contentType}")
               checkOptions["version"] = contentVersion
               logging.debug(f"checkOptions={checkOptions}")
               check = eval(sapmonContentTypes[contentType])(**checkOptions)
               self.availableChecks.append(check)
            except Exception as e:
               logger.error(f"could not instantiate new check of type {contentType} ({e})")
      logger.info("successfully loaded %d monitoring checks" % len(self.availableChecks))
      return

   def readStateFile(self):
      """
      Get most recent state from a local file
      """
      logger.info("reading state file")
      jsonData = {}
      try:
         logger.debug(f"STATE_FILE={STATE_FILE}")
         with open(STATE_FILE, "r") as file:
            data = file.read()
         jsonData = json.loads(data, object_hook=_JsonDecoder.datetimeHook)
      except FileNotFoundError as e:
         logger.warning(f"state file {STATE_FILE} does not exist")
      except Exception as e:
         logger.error(f"could not read state file {STATE_FILE} ({e})")
      for c in self.availableChecks:
         sectionKey = f"{c.prefix}_{c.name}"
         if sectionKey in jsonData:
            logger.debug(f"parsing section {sectionKey}")
            section = jsonData.get(sectionKey, {})
            for k in section.keys():
               c.state[k] = section[k]
         else:
            logger.warning(f"section {sectionKey} not found in state file")
      logger.info("successfully parsed state file")
      return True

   def writeStateFile(self):
      """
      Persist current state into a local file
      """
      logger.info("writing state file")
      success  = False
      jsonData = {}
      try:
         logger.debug(f"STATE_FILE={STATE_FILE}")
         for c in self.availableChecks:
            sectionKey = f"{c.prefix}_{c.name}"
            jsonData[sectionKey] = c.state
         with open(STATE_FILE, "w") as file:
            json.dump(jsonData, file, indent=3, cls=_JsonEncoder)
         success = True
      except Exception as e:
         logger.error(f"could not write state file {STATE_FILE} ({e})")
      return success

   def fetchHanaPasswordFromKeyVault(self, passwordKeyVault, passwordKeyVaultMsiClientId):
      """
      Fetch HANA password from a separate KeyVault.
      """
      vaultNameSearch = re.search("https://(.*).vault.azure.net", passwordKeyVault)
      logger.debug(f"vaultNameSearch={vaultNameSearch}")
      kv = AzureKeyVault(vaultNameSearch[1], passwordKeyVaultMsiClientId)
      logger.debug(f"kv={kv}")
      return kv.getSecret(passwordKeyVault)

   def parseSecrets(self):
      """
      Read secrets from customer KeyVault and store credentials in context.
      """
      def sliceDict(d, s):
         return {k: v for k, v in iter(d.items()) if k.startswith(s)}

      def fetchHanaPasswordFromKeyVault(self, passwordKeyVault, passwordKeyVaultMsiClientId):
         vaultNameSearch = re.search('https://(.*).vault.azure.net', passwordKeyVault)
         logger.debug(f"vaultNameSearch={vaultNameSearch}")
         kv = AzureKeyVault(vaultNameSearch[1], passwordKeyVaultMsiClientId)
         logger.debug(f"kv={kv}")
         return kv.getSecret(passwordKeyVault)

      logger.info("parsing secrets")
      secrets = self.azKv.getCurrentSecrets()

      # extract HANA instance(s) from secrets
      hanaSecrets = sliceDict(secrets, "SapHana-")
      for h in hanaSecrets.keys():
         hanaDetails = json.loads(hanaSecrets[h])
         if not hanaDetails["HanaDbPassword"]:
            logger.info("no HANA password provided; need to fetch password from separate KeyVault")
            try:
               password = self.fetchHanaPasswordFromKeyVault(
                  hanaDetails["HanaDbPasswordKeyVaultUrl"],
                  hanaDetails["PasswordKeyVaultMsiClientId"])
               hanaDetails["HanaDbPassword"] = password
               logger.debug("retrieved HANA password successfully from KeyVault")
            except Exception as e:
               logger.critical(
                   f"could not fetch HANA password (instance={h}) from KeyVault ({e})"
               )
               sys.exit(ERROR_GETTING_HANA_CREDENTIALS)
         try:
            hanaInstance = SapHana(hanaDetails = hanaDetails)
         except Exception as e:
            logger.error(f"could not create HANA instance {h}) ({e})")
            continue
         self.hanaInstances.append(hanaInstance)

      # extract Log Analytics credentials from secrets
      try:
         laSecret = json.loads(secrets["AzureLogAnalytics"])
      except Exception as e:
         logger.critical(f"could not fetch Log Analytics credentials ({e})")
         sys.exit(ERROR_GETTING_LOG_CREDENTIALS)
      self.azLa = AzureLogAnalytics(
         laSecret["LogAnalyticsWorkspaceId"],
         laSecret["LogAnalyticsSharedKey"]
         )
      return

###############################################################################

class _JsonEncoder(json.JSONEncoder):
   """
   Helper class to serialize datetime and Decimal objects into JSON
   """
   def default(self, o):
      if isinstance(o, decimal.Decimal):
         return float(o)
      elif isinstance(o, (datetime, date)):
         return datetime.strftime(o, TIME_FORMAT_JSON)
      return super(_JsonEncoder, self).default(o)

class _JsonDecoder(json.JSONDecoder):
   """
   Helper class to de-serialize JSON into datetime and Decimal objects
   """
   def datetimeHook(self):
      for (k, v) in self.items():
         try:
            self[k] = datetime.strptime(v, TIME_FORMAT_JSON)
         except Exception as e:
            pass
      return self

###############################################################################

def getPayloadDir():
   return os.path.dirname(os.path.realpath(__file__))

def onboard(args):
   """
   Store credentials in the customer KeyVault
   (To be executed as custom script upon initial deployment of collector VM)
   """
   logger.info("starting onboarding payload")

   # Credentials (provided by user) to the existing HANA instance
   hanaSecretName = f"SapHana-{args.HanaDbName}"
   logger.debug(f"hanaSecretName={hanaSecretName}")
   hanaSecretValue = json.dumps({
      "HanaHostname":                args.HanaHostname,
      "HanaDbName":                  args.HanaDbName,
      "HanaDbUsername":              args.HanaDbUsername,
      "HanaDbPassword":              args.HanaDbPassword,
      "HanaDbPasswordKeyVaultUrl":   args.HanaDbPasswordKeyVaultUrl,
      "HanaDbSqlPort":               args.HanaDbSqlPort,
      "PasswordKeyVaultMsiClientId": args.PasswordKeyVaultMsiClientId,
      })
   logger.info("storing HANA credentials as KeyVault secret")
   try:
      ctx.azKv.setSecret(hanaSecretName, hanaSecretValue)
   except Exception as e:
      logger.critical(f"could not store HANA credentials in KeyVault secret ({e})")
      sys.exit(ERROR_SETTING_KEYVAULT_SECRET)

   # Credentials (created by HanaRP) to the newly created Log Analytics Workspace
   laSecretName = "AzureLogAnalytics"
   logger.debug(f"laSecretName={laSecretName}")
   laSecretValue = json.dumps({
      "LogAnalyticsWorkspaceId": args.LogAnalyticsWorkspaceId,
      "LogAnalyticsSharedKey":   args.LogAnalyticsSharedKey,
      })
   logger.info("storing Log Analytics credentials as KeyVault secret")
   try:
      ctx.azKv.setSecret(laSecretName, laSecretValue)
   except Exception as e:
      logger.critical(
          f"could not store Log Analytics credentials in KeyVault secret ({e})"
      )
      sys.exit(ERROR_SETTING_KEYVAULT_SECRET)

   hanaDetails = json.loads(hanaSecretValue)
   if not hanaDetails["HanaDbPassword"]:
      logger.info("no HANA password provided; need to fetch password from separate KeyVault")
      hanaDetails["HanaDbPassword"] = ctx.fetchHanaPasswordFromKeyVault(
         hanaDetails["HanaDbPasswordKeyVaultUrl"],
         hanaDetails["PasswordKeyVaultMsiClientId"])

   # Check connectivity to HANA instance
   logger.info("connecting to HANA instance to run test query")
   try:
      hana = SapHana(hanaDetails = hanaDetails)
      hana.connect()
      hana.runQuery("SELECT 0 FROM DUMMY")
      hana.disconnect()
   except Exception as e:
      logger.critical(f"could not connect to HANA instance and run test query ({e})")
      sys.exit(ERROR_HANA_CONNECTION)

   logger.info("onboarding payload successfully completed")
   return

def monitor(args):
   """
   Actual SAP Monitor payload:
   - Obtain credentials from KeyVault secrets
   - For each DB tenant of the monitored HANA instance:
     - Connect to DB tenant via SQL
     - Execute monitoring statements
     - Emit metrics as custom log to Azure Log Analytics
   (To be executed as cronjob after all resources are deployed.)
   """
   logger.info("starting monitor payload")
   ctx.parseSecrets()
   # TODO(tniek) - proper handling of source connection types
   for h in ctx.hanaInstances:
      try:
         h.connect()
      except Exception as e:
         logger.critical(f"could not connect to HANA instance ({e})")
         sys.exit(ERROR_HANA_CONNECTION)

      for c in ctx.availableChecks:
         if not c.state["isEnabled"]:
            logger.info(f"check {c.prefix}_{c.name} has been disabled, skipping")
            continue
         lastRunLocal = c.state["lastRunLocal"]
         logger.debug("lastRunLocal=%s; frequencySecs=%d; currentLocal=%s" % \
            (lastRunLocal, c.frequencySecs, datetime.utcnow()))
         if lastRunLocal and \
            lastRunLocal + timedelta(seconds=c.frequencySecs) > datetime.utcnow():
            logger.info(f"check {c.prefix}_{c.name} is not due yet, skipping")
            continue
         logger.info(f"running check {c.prefix}_{c.name}")
         resultJson = c.run(h)
         ctx.azLa.ingest(c.customLog, resultJson, c.colTimeGenerated)
      ctx.writeStateFile()

      try:
         h.disconnect()
      except Exception as e:
         logger.error(f"could not disconnect from HANA instance ({e})")

   logger.info("monitor payload successfully completed")
   return

def initLogger(args):
   global logger
   if args.verbose:
      LOG_CONFIG["handlers"]["console"]["formatter"] = "detailed"
      LOG_CONFIG["handlers"]["console"]["level"] = logging.DEBUG
   logging.config.dictConfig(LOG_CONFIG)
   logger = logging.getLogger(__name__)

def main():
   global ctx, logger
   parser = argparse.ArgumentParser(description="SAP Monitor Payload")
   parser.add_argument("--verbose", action="store_true", dest="verbose", help="run in verbose mode") 
   subParsers = parser.add_subparsers(title="actions", help="Select action to run")
   subParsers.required = True
   subParsers.dest = "command"
   onbParser = subParsers.add_parser("onboard", description="Onboard payload", help="Onboard payload by adding credentials into KeyVault")
   onbParser.set_defaults(func=onboard, command="onboard")
   onbParser.add_argument("--HanaHostname", required=True, type=str, help="Hostname of the HDB to be monitored")
   onbParser.add_argument("--HanaDbName", required=True, type=str, help="Name of the tenant DB (empty if not MDC)")
   onbParser.add_argument("--HanaDbUsername", required=True, type=str, help="DB username to connect to the HDB tenant")
   onbParser.add_argument("--HanaDbPassword", required=False, type=str, help="DB user password to connect to the HDB tenant")
   onbParser.add_argument("--HanaDbPasswordKeyVaultUrl", required=False, type=str, help="Link to the KeyVault secret containing DB user password to connect to the HDB tenant")
   onbParser.add_argument("--HanaDbSqlPort", required=True, type=int, help="SQL port of the tenant DB")
   onbParser.add_argument("--LogAnalyticsWorkspaceId", required=True, type=str, help="Workspace ID (customer ID) of the Log Analytics Workspace")
   onbParser.add_argument("--LogAnalyticsSharedKey", required=True, type=str, help="Shared key (primary) of the Log Analytics Workspace")
   onbParser.add_argument("--PasswordKeyVaultMsiClientId", required=False, type=str, help="MSI Client ID used to get the access token from IMDS")
   monParser  = subParsers.add_parser("monitor", description="Monitor payload", help="Execute the monitoring payload")
   monParser.set_defaults(func=monitor)
   args = parser.parse_args()
   initLogger(args)
   ctx = _Context(args.command)
   args.func(args)

logger = None
ctx    = None
if __name__ == "__main__":
   main()

