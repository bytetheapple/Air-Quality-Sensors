#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################


import indigo
import json
import sys
import requests
import math

class llPair :
	def __init__(self, lat, lon):
		self.lat = lat
		self.lon = lon
		self.flat = float(lat)
		self.flon = float(lon)
		
		
	def calculateDistance (self, lat2, lon2):	
			#R = 6371000 # metres
			R = 3958.755866 # miles
			phi1 = math.radians(self.flat)
			phi2 = math.radians(float(lat2))
			deltaPhi = math.radians(float(lat2)-self.flat)
			deltaGamma = math.radians(float(lon2)-self.flon)

			a = math.sin(deltaPhi/2) * math.sin(deltaPhi/2) + math.cos(phi1) * math.cos(phi2) * math.sin(deltaGamma/2) * math.sin(deltaGamma/2)
			c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

			d = R * c 
			return(d)

		
class virtParam:
	def __init__(self, ave, closest):
		self.ave = ave
		self.closest = closest

################################
# convert and AQI number to a health alert code (text)
################################
class aqiConversion:
	def __init__(self):
		self.conversionTable = []
		alertCodes =["Healthy",'Moderate', "Unhealthy for Sensitive Groups", 'Unhealth', 'Very Unhealthy', 'Very Unhealthy', ' Hazardous', ' Hazardous', ' Hazardous', ' Hazardous']
		for code in alertCodes:
			for i in range(50):
				self.conversionTable.append(code)


################################
# Class that calculates an AQI score based on a pm2.5 particle concentraion
# Details about AQI calculations and fomula can be found here:		
# https://forum.airnowtech.org/t/the-aqi-equation/169	
# the pm2.5 concentration is truncated to one decimal place
# the AQI result is rounded to he nearest whole number
################################
class aqiCalculator:
	def __init__(self):
		self.pm2_5Lo = [0.0, 12.1, 35.5,55.5, 150.5, 250.5]
		self.pm2_5Hi =[12.0, 35.4, 55.4, 150.4, 250.4, 500.4]
		self.aqiLo = [0,51,101,151,201,300]
		self.aqiHi = [50,100,150,200,300,500]
	
	def truncate(self, number, dec):
		factor = 10.0**dec
		return(math.trunc(number*factor)/factor)

	##############################################
	#Details about AQI calculations and fomula can be found here:		
	# https://forum.airnowtech.org/t/the-aqi-equation/169	
	# the pm2.5 concentration is truncated to one decimal place
	# the AQI result is rounded to he nearest whole number
	#######################################
	def aqiCalc(self,pm2_5):
		pm2_5 = self.truncate(pm2_5,1)
		i=0
		while pm2_5 >= self.pm2_5Lo[i]:
			 i = i+1
		i = i-1
		numerator = (self.aqiHi[i]-self.aqiLo[i])
		denominator = (self.pm2_5Hi[i]-self.pm2_5Lo[i])
		scale = pm2_5 -self.pm2_5Lo[i]
		aqi = (numerator/denominator)*scale + self.aqiLo[i]
		aqi = round(aqi)
		return(aqi)


class airNowRecord:
	def __init__(self, parameterName, aqi, reportingArea, valid):
		self.validData = valid
		self.parameterName = parameterName
		self.aqi = aqi
		self.reportingArea = reportingArea
		
class purpleAirRecord:
	def __init__(self, label, iD, parentId, temp_f, humidity, pm2_5_cf_1, lat, lon, valid ):
		self.label = label
		self.id = iD
		self.parentId = parentId
		self.temp_f = temp_f
		self.humidity = humidity
		self.pm2_5_cf_1 = pm2_5_cf_1
		self.lat = lat
		self.lon = lon
		self.validData = valid 		


class purpleAirApi:
	def __init__(self):
		self.baseUrl = "https://www.purpleair.com/json"
	
	def getData(self, stationID=None):
		results =[]
		urlExtension =""
		if stationID != None:
			urlExtension = ("?show=%s" % (stationID))
		target_url =  ( self.baseUrl + urlExtension) 
		params =[]
		res = requests.get(target_url, params, verify=True)
		if res.status_code == 200:
			recordList = res.json()
			for record in recordList['results']:
				
				if  record.has_key('Lat') and record.has_key('Lon'):
					paRecord = purpleAirRecord(record['Label'], record['ID'], None, None, None, None, record['Lat'], record['Lon'],True)
					if record.has_key('ParentID'):
						paRecord.parentId = record['ParentID']
					if record.has_key('pm2_5_cf_1'):
						paRecord.pm2_5_cf_1 = record['pm2_5_cf_1']
					if record.has_key('temp_f'):
						paRecord.temp_f = record['temp_f']
					if record.has_key('humidity'):
						paRecord.humidity = record['humidity']
					
					results.append(paRecord)


		else:
			indigo.server.log('Purple Air API Failed')
			paRecord = purpleAirRecord(None, None, None, None, None, None, None, None, False)
			results.append(paRecord)
			
		return(results)


class airNowApi:
	def __init__(self):
		self.target_url =  "https://www.airnowapi.org/aq/observation/latLong/current/?"		
		self.APIkey = "B2CF15FF-7D10-4963-A662-604CA6CAFD98"
		
	def getData(self,location):
		params ={'distance':'1000', 'format':'json', 'latitude':str(location.lat), 'longitude': str(location.lon),"API_KEY":self.APIkey}
		res = requests.get(self.target_url, params, verify=True)
		
		results = airNowRecord(None, None, None, False)
		if res.status_code == 200:
			record = res.json()			
			for recordDict in record:
				if recordDict['ParameterName'] == "PM2.5":
					results = airNowRecord(recordDict['ParameterName'],recordDict['AQI'], recordDict['ReportingArea'], True)
		else:
			indigo.server.log('AirNow API Failed')
		return(results)

	
################################################################################
class Plugin(indigo.PluginBase):
########################################
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		super(Plugin, self).__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
		self.debug = False
		self.sampleInterval = 20
		self.numNearest = 5
		self.aqiCalculator = aqiCalculator()
		self.paAPI = purpleAirApi()
		self.anAPI = airNowApi()
			
	
	def startup(self):
		self.logger.info(u"Startup called")



#######################
# Utility Functions
#######################	
	def sli(self, somethingToDisplay):
		self.logger.info(somethingToDisplay)	


#######################
# Validation Functions
#######################	

	#######################
	# Validation of the plugin configuration dialog
	# The only thing entered in that dialog is the current location
	#######################	
	def validatePrefsConfigUi(self, valuesDict):
		return(self.validateLocationData(valuesDict))
		
		
	#######################
	# Called to validate all device configurations
	#######################			
	def validateDeviceConfigUi(self, valuesDict, typeId, devId):
		errorDict = {}
		# Since a new location is being specified, make sure that any existing sensor list file for this device is deleted
		self.purgeNearestList(devId)
		if typeId == "virtualSensor" or typeId == 'airNowSensor':
			if valuesDict["nearestSensor"] == False:
				return(self.validateLocationData(valuesDict))
			else:
				#Nearest sensor is being selected, so use the user's location as entered when the plugin was configured
				valuesDict['latDegrees'] = self.pluginPrefs['latDegrees']
				valuesDict['longDegrees'] = self.pluginPrefs['longDegrees']
				valuesDict["latLongFormat"] == "DD"				
				return(self.validateLocationData(valuesDict))

		elif typeId == "sensor":
			if valuesDict['nearestSensor'] == True:
				valuesDict['stationID'] = None
				return(True,valuesDict)
			else:
				return(self.validateStationID(valuesDict))			


						
	#######################
	# Validation location data is a function that validates that valid GPS
	# coordinates were entered depending on the speecified format 
	#######################		
	def validateStationID(self, valuesDict):	
		result = True
		errorDict = indigo.Dict()
		if valuesDict["idOrName"] == "ID":			
			if valuesDict["stationID"] == "":
				errorDict["stationID"] = "Need to specify a valid PurpleAir Staion ID"
				result = False
		elif valuesDict['idOrName'] == 'Name':
			if valuesDict["stationName"] == "":
				errorDict["stationName"] = "Need to specify a valid PurpleAir Staion Name"
				result = False		
				
					
		if result == True:	
			return(result, valuesDict)			
		else:
			return(result, valuesDict, errorDict)


				

	#######################
	# Validation location data is a function that validates that valid GPS
	# coordinates were entered depending on the speecified format 
	#######################		
	def validateLocationData(self, valuesDict):	
		result = True
		errorDict = indigo.Dict()

		if valuesDict["latLongFormat"] == "DMS":			
			if valuesDict["latDMSDegrees"] == "":
				errorDict["latDMSDegrees"] = "Need to enter a number"
				result = False
			if valuesDict["longDMSDegrees"] == "":
				errorDict["longDMSDegrees"] = "Need to enter a number"
				result = False
			
			if valuesDict["latSeconds"] == "":
				errorDict["latSeconds"] = "Need to enter a number"
				result = False
			if valuesDict["latMinutes"] == "":
				errorDict["latMinutes"] = "Need to enter a number"
				result = False
			
			if valuesDict["longSeconds"] == "":
				errorDict["longSeconds"] = "Need to enter a number"
				result = False
			if valuesDict["longMinutes"] == "":
				errorDict["longMinutes"] = "Need to enter a number"
				result = False
				
			if result == True:
				dmsDict ={"degrees" : valuesDict['latDMSDegrees'], "minutes" : valuesDict["latMinutes"], "seconds":valuesDict["latSeconds"] }
				valuesDict['latDegrees'] = self.convertDMS2D(dmsDict)
				dmsDict ={"degrees":valuesDict['longDMSDegrees'], "minutes":valuesDict["longMinutes"], "seconds":valuesDict["longSeconds"] }
				valuesDict['longDegrees'] = self.convertDMS2D(dmsDict)							
				valuesDict["latLongFormat"] == "DD"
			
		elif valuesDict["latLongFormat"] == "DD":
			if valuesDict["latDegrees"] == "":
				errorDict["latDegrees"] = "Need to enter a number"
				result = False
			if valuesDict["longDegrees"] == "":
				errorDict["longDegrees"] = "Need to enter a number"
				result = False
						
			if result == True:				
				dMS = self.convertD2DMS(float(valuesDict["latDegrees"]))
				valuesDict["latDMSDegrees"] = dMS["degrees"]
				valuesDict["latMinutes"] = dMS["minutes"]
				valuesDict["latSeconds"] = dMS["seconds"]
		
				dMS = self.convertD2DMS(float(valuesDict["longDegrees"]))
				valuesDict["longDMSDegrees"] = dMS["degrees"]
				valuesDict["longMinutes"] = dMS["minutes"]
				valuesDict["longSeconds"] = dMS["seconds"]
				
		else:
			errorDict["latLongFormat"] = "Need to select Decimal Degrees or DMS Format"
			result = False
		
		if result == True:	
			return(result, valuesDict)			
		else:
			return(result, valuesDict, errorDict)
	



	def convertDMS2D(self, dmsDict):
		result = str(abs(float(dmsDict['degrees'])) + float(dmsDict['minutes'])/60 + float(dmsDict['seconds'])/3600)
		if float(dmsDict['degrees']) < 0:
			result = str(-float(result))	
		return(result)	


	def convertD2DMS(self, degs):		
		results = {}
		degrees = abs(degs)				
		minutes = math.floor(degrees%1.0*60)
		results['minutes'] = str(int(minutes))
		results['seconds'] = str(int(round((degrees%1.0*60)%1.0*60, 0)))
		degrees = math.floor(degrees)
		if  degs< 0:
			degrees = -degrees				
		results['degrees'] = str(int(math.floor(degrees)))
		return (results)

############### End of Validation Methods







#	def getData(self, stationID=None):
#		urlExtension =""
#		if stationID != None:
#			urlExtension = ("?show=%s" % (stationID))
#		target_url =  ("https://www.purpleair.com/json" + urlExtension) 
#		params =[]
#		res = requests.get(target_url, params, verify=True)
#		if res.status_code == 200:
#			return(res.json())
#
#		else:
#			indigo.server.log('Purple Air API Failed')
#			return(None)
	
#	def getAirnowData(self,location):
#		target_url =  "https://www.airnowapi.org/aq/observation/latLong/current/?" 
#		params ={'distance':'1000', 'format':'json', 'latitude':str(location.lat), 'longitude': str(location.lon),"API_KEY":"B2CF15FF-7D10-4963-A662-604CA6CAFD98"}
#		res = requests.get(target_url, params, verify=True)
#		rtn = res.json()
#		return(rtn)

	
	def findNearest(self, sensorList, numNearest, loc, onlyParents):
		closest = []
		self.sli("sensorList Length: " + str(len(sensorList)))			
		if len(sensorList) > 0:
			if sensorList[0].validData == True:
				for i in range(numNearest):
					closest.append({"Name":None, "ID":None, "Distance":1000000000})
			#closest = [{"Name":None, "Distance":1000000000}, {"Name":None, "Distance":1000000000}, {"Name":None, "Distance":1000000000}]
			
				for record in sensorList:
					if not (record.parentId != None and onlyParents == True):
		#				if record.has_key('Lat') and record.has_key('Lon'):
							
							newDis = loc.calculateDistance (record.lat, record.lon)

							for i in range(numNearest):
								if newDis <= closest[i]["Distance"]:
									if closest[i]['Name'] == record.label:
										
										break
									else:	
										newRec = {"Name":record.label, "ID": record.id, "Distance":newDis}
										closest.insert(i, newRec)
										closest.pop(numNearest)
										
										break
		return(closest)
		
	
	def createNearestList(self, dev, num):
		self.logger.info("Creating NearestList")
		if dev.deviceTypeId == "virtualSensor":
			loc = llPair(dev.pluginProps["latDegrees"], dev.pluginProps["longDegrees"]) 
			paRecordList = self.paAPI.getData(None)
			nearestList = self.findNearest(paRecordList, num, loc, True)
		elif dev.deviceTypeId == "sensor":
			nearestList = self.validateSensor(dev)

		if len(nearestList) > 0:
			dev.updateStateOnServer("sensorList", json.dumps(nearestList))
		return(nearestList)
	
	def purgeNearestList(self,devId):
		if devId != 0: # device already exists
			self.sli("dev ID: " + str(devId))
			for dev in indigo.devices.itervalues("self"):
				if dev.id == devId:
					dev.updateStateOnServer("sensorList", "")
			
		
	
	def validateSensor(self, dev):
		nearestList = []
		if dev.pluginProps["nearestSensor"] == True:
			loc = llPair(self.pluginPrefs["latDegrees"], self.pluginPrefs["longDegrees"]) 
			paRecordList = self.getData(None)			
			nearestList = self.findNearest(paRecordList, 1, loc, True)
			
		
		elif dev.pluginProps['idOrName'] == 'ID':
			paRecordList = self.getData(dev.pluginProps["stationID"])
			self.logger.info("Sensor by ID returned " + str(len(paRecordList['results'])))
			if paRecordList[0].validData == True:
				nearestList.append({"Name":paRecordList[0].label, "ID": dev.pluginProps["stationID"], "Distance":0})
					
		elif dev.pluginProps['idOrName'] == 'Name':
			paRecordList = self.getData(None)
			if paRecordList[0].validData == True:
				for record in paRecordList:
					if record.label == dev.pluginProps['stationName']:
						nearestList.append({"Name":record.label, "ID": record.id, "Distance":0})
						break			
		if len(nearestList) != 1 :
			self.logger.info("Sensor: " + dev.name + "incorrectly configured")
			self.logger.info("ID ="+str(dev.pluginProps["stationID"] ))
			self.logger.info("Name ="+ str(dev.pluginProps["stationName"] ))
		else:
			currentPluginProps = dev.pluginProps
			currentPluginProps['stationID'] = nearestList[0]['ID']
			currentPluginProps['stationName'] = nearestList[0]['Name']
			dev.replacePluginPropsOnServer(currentPluginProps)
		return(nearestList)
	

		
		
	def getNearestList(self,dev, num):
		if dev.states['sensorList'] != "":
			nearestList = json.loads(dev.states['sensorList'])
		else:
			nearestList = self.createNearestList(dev,num)
		return(nearestList)

##################################			
# Update routines.   Called periodically to pull the data from 
# the internet and update the state of each sensor
##################################
	def updateVirtualSensor(self, dev):
		sensorList = self.getNearestList(dev, self.numNearest)
		if len(sensorList) != 0: 
			dev.updateStateOnServer("sensorAveTemp", self.aveAndClosest(sensorList, 'temp_f').ave, decimalPlaces = 1)
			dev.updateStateOnServer("sensorAveHumidity", self.aveAndClosest(sensorList, 'humidity').ave, decimalPlaces = 1)
			pm25cf1ave = self.aveAndClosest(sensorList, 'pm2_5_cf_1').ave
			dev.updateStateOnServer("sensorAvePm25", pm25cf1ave, decimalPlaces = 1)
			pm25AQI = self.aqiCalculator.aqiCalc(pm25cf1ave)
			dev.updateStateOnServer("sensorAvePm25AQI", pm25AQI, decimalPlaces = 1)
			dev.updateStateOnServer("aqiHazardCode", self.convertAQI2AlertLevel(pm25AQI) )


			
	def updateSensor(self, dev):
		sensorList = self.getNearestList(dev, 1)
		if len(sensorList) != 0: 
			dev.updateStateOnServer("sensorAveTemp", self.aveAndClosest(sensorList, 'temp_f').ave, decimalPlaces = 1)
			dev.updateStateOnServer("sensorAveHumidity", self.aveAndClosest(sensorList, 'humidity').ave, decimalPlaces = 1)
			pm25cf1ave = self.aveAndClosest(sensorList, 'pm2_5_cf_1').ave
			dev.updateStateOnServer("sensorAvePm25", pm25cf1ave, decimalPlaces = 1)		
			pm25AQI = self.aqiCalculator.aqiCalc(pm25cf1ave)
			dev.updateStateOnServer("sensorAvePm25AQI", pm25AQI, decimalPlaces = 1)
			dev.updateStateOnServer("aqiHazardCode", self.convertAQI2AlertLevel(pm25AQI) )


	
	def updateAirnowSensor(self, dev):
		loc = llPair(dev.pluginProps["latDegrees"], dev.pluginProps["longDegrees"]) 
		anRecord =self.anAPI.getData(loc) 
		if anRecord.validData == True:
			dev.updateStateOnServer("AQI", anRecord.aqi, decimalPlaces = 1)		
			dev.updateStateOnServer("reportingArea", anRecord.reportingArea, decimalPlaces = 1)
			dev.updateStateOnServer("aqiHazardCode", self.convertAQI2AlertLevel(anRecord.aqi) )
				
	def aveAndClosest(self, sensorList, tag):
		values = []
		for sensor in sensorList:
			result = self.paAPI.getData(sensor["ID"])
			if tag == 'pm2_5_cf_1':
				if len(result) == 2:					
					if result[0].pm2_5_cf_1 != None:
						pm2_50 = result[0].pm2_5_cf_1 
						if result[1].pm2_5_cf_1 != None:							
							pm2_51 = result[0].pm2_5_cf_1
							avepm2_5_cf_1 = (float(pm2_50) + float(pm2_51))/2.0
							if result[0].humidity != None:
							
								RH = float(result[0].humidity)
								###########							
								# Correction calculation to bring PurpleAir sensor in line with AirNow EPA sensor valuses:
								# PM2.5 corrected= 0.52*[PA_cf1(avgAB)] - 0.085*RH +5.71
								#  https://cfpub.epa.gov/si/si_public_record_report.cfm?dirEntryId=349513&Lab=CEMM&simplesearch=0&showcriteria=2&sortby=pubDate&timstype=&datebeginpublishedpresented=08/25/2018
								values.append(.52*avepm2_5_cf_1 - .085*RH + 5.71)
			elif tag == 'humidity':
				for paRecord in result:
					if paRecord.humidity != None:
						values.append(float(paRecord.humidity))	
			elif tag == 'temp_f':
				for paRecord in result:
					if paRecord.temp_f != None:
						values.append(float(paRecord.temp_f))	
						
		if len(values) !=0:									
			results = virtParam(round(sum(values)/len(values),1), round(values[0],1))
		else:
			results = virtParam(0,0)
		self.sleep(1)
		return(results)


	def convertAQI2AlertLevel(self, aqi):		
		convert = aqiConversion()
		return(convert.conversionTable[int(aqi)])
		
		
		
	

			
	def runConcurrentThread(self):
		try:
			while True:
				for dev in indigo.devices.iter("self"):
					if dev.deviceTypeId == "virtualSensor":
						self.updateVirtualSensor(dev)
					elif dev.deviceTypeId == "sensor":
						self.updateSensor(dev)
					elif dev.deviceTypeId =='airNowSensor':
						self.updateAirnowSensor(dev)
				self.sleep(self.sampleInterval)
		except self.StopThread:
			pass	# Optionally catch the StopThread exception and do any needed cleanup.

	########################################
	#def deviceStartComm(self, dev):
	# Called when communication with the hardware should be established.
	# Here would be a good place to poll out the current states from the
	# thermostat. If periodic polling of the thermostat is needed (that
	# is, it doesn't broadcast changes back to the plugin somehow), then
	# consider adding that to runConcurrentThread() above.
	def deviceStartComm(self, dev):
		self.logger.info("deviceStartComm " + dev.name )
		dev.stateListOrDisplayStateIdChanged()
		return

	def deviceStopComm(self, dev):
		# Called when communication with the hardware should be shutdown.
		pass

