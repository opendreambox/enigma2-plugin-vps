# -*- coding: utf-8 -*-

from enigma import eTimer, eConsoleAppContainer, getBestPlayableServiceReference, eServiceReference, eEPGCache, eServiceCenter,gFont, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_HALIGN_CENTER, RT_VALIGN_CENTER, RT_WRAP
from Screens.Screen import Screen
from ServiceReference import ServiceReference
from Components.ActionMap import ActionMap
from Components.MultiContent import MultiContentEntryText
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from Components.ScrollLabel import ScrollLabel
from Screens.MessageBox import MessageBox
from Screens.ChoiceBox import ChoiceBox
from Tools.BoundFunction import boundFunction
from Tools.XMLTools import stringToXML
from Tools import Directories
from time import time
from Components.config import config
from Vps import vps_exe, vps_timers
import NavigationInstance
from xml.etree.cElementTree import parse as xml_parse

check_pdc_interval_available = 3600*24*30*12
check_pdc_interval_unavailable = 3600*24*30*2

class VPS_check_PDC:
	def __init__(self):
		self.checked_services = { }
		self.load_pdc()
	
	def load_pdc(self):
		try:
			doc = xml_parse(Directories.resolveFilename(Directories.SCOPE_CONFIG, "vps.xml"))
			xmlroot = doc.getroot()
			
			if xmlroot is not None:
				for xml in xmlroot.findall("channel"):
					serviceref = xml.get("serviceref").encode("utf-8")
					has_pdc = xml.get("has_pdc")
					last_check = xml.get("last_check")
					default_vps = xml.get("default_vps")
					self.checked_services[serviceref] = { }
					self.checked_services[serviceref]["last_check"] = int(last_check)
					self.checked_services[serviceref]["has_pdc"] = int(has_pdc)
					if default_vps and default_vps != "None":
						self.checked_services[serviceref]["default_vps"] = int(default_vps)
					else:
						self.checked_services[serviceref]["default_vps"] = 0
		except:
			pass
	
	def save_pdc(self):
		list = []
		list.append('<?xml version="1.0" ?>\n')
		list.append('<pdc_available>\n')
		
		now = time()
		for ch in self.checked_services:
			if (self.checked_services[ch]["last_check"] < (now - check_pdc_interval_available)) and self.checked_services[ch]["default_vps"] != 1:
				continue
			list.append('<channel')
			list.append(' serviceref="' + stringToXML(ch) + '"')
			list.append(' has_pdc="' + str(int(self.checked_services[ch]["has_pdc"])) + '"')
			list.append(' last_check="' + str(int(self.checked_services[ch]["last_check"])) + '"')
			list.append(' default_vps="' + str(int(self.checked_services[ch]["default_vps"])) + '"')
			list.append('></channel>\n')
		
		list.append('</pdc_available>\n')
		
		file = open(Directories.resolveFilename(Directories.SCOPE_CONFIG, "vps.xml"), "w")
		for x in list:
			file.write(x)
		file.close()
	
	def check_service(self, service):
		service_str = service.toCompareString()
		
		try:
			if self.checked_services[service_str] is not None:
				return self.checked_services[service_str]["has_pdc"], self.checked_services[service_str]["last_check"], self.checked_services[service_str]["default_vps"]
			else:
				return -1, 0, 0
		except:
			return -1, 0, 0
	
	def setServicePDC(self, service, state, default_vps):
		service_str = service.toCompareString()
		
		if state == -1 and default_vps == 0:
			try:
				del self.checked_services[service_str]
			except:
				pass
		else:
			self.checked_services[service_str] = { }
			self.checked_services[service_str]["has_pdc"] = state
			self.checked_services[service_str]["last_check"] = time()
			self.checked_services[service_str]["default_vps"] = default_vps
		
		self.save_pdc()
		
	def recheck(self, has_pdc, last_check):
		return not ((has_pdc == 1 and last_check > (time() - check_pdc_interval_available)) or (has_pdc == 0 and last_check > (time() - check_pdc_interval_unavailable)))

Check_PDC = VPS_check_PDC()

# Prüfen, ob PDC-Descriptor vorhanden ist.
class VPS_check(Screen):
	skin = """<screen name="vpsCheck" position="center,center" size="820,630" title="VPS-Plugin">
		<widget source="infotext" render="Label" position="10,10" size="800,40" font="Regular;25" valign="center" halign="center" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-1,-1" />
		<widget source="channelList" render="Listbox" position="10,60" size="800,560">
			<convert type="TemplatedMultiContent">
				{
					"templates":
						{
							"default":
								(
									40,
										[
											MultiContentEntryText(pos=(10,0), size=(490,40), flags=RT_HALIGN_LEFT|RT_VALIGN_CENTER|RT_WRAP, font=0, text=0),
											MultiContentEntryText(pos=(500,0), size=(270,40), flags=RT_HALIGN_RIGHT|RT_VALIGN_CENTER|RT_WRAP, font=0, text=1),
										]
								),
						},
					"fonts": 
						[
							gFont("Regular", 28),
						]
				}
			</convert>
		</widget>
	</screen>"""
	
	def __init__(self, session, service, mode="timer"):
		Screen.__init__(self, session)
		
		self["infotext"] = StaticText(_("VPS-Plugin checks if the channel supports VPS ..."))
		self["channelList"] = List()
		
		self["actions"] = ActionMap(["OkCancelActions"], 
			{
				"cancel": boundFunction(self.finish, True),
			}, -1)
		
		self.mode = mode
		self.program = eConsoleAppContainer()
		self.dataAvail_conn = self.program.dataAvail.connect(self.program_dataAvail)
		self.appClosed_conn = self.program.appClosed.connect(self.program_closed)
		self.check = eTimer()
		self.check_conn = self.check.timeout.connect(self.doCheck)
		self.execTimer = eTimer()
		self.execTimer_conn = self.execTimer.timeout.connect(self.program_kill)
		self.simulate_recordService = None
		self.last_serviceref = None
		self.calledfinished = False
		self.serviceName = ""
		self.channelList = []
		
		if mode == "bouquet":
			self.bouquetServices = [ ]
			servicelist = eServiceCenter.getInstance().list(service)
			
			if servicelist is not None:
				while True:
					service = servicelist.getNext()
					if not service.valid():
						break
					if service.flags & (eServiceReference.isDirectory | eServiceReference.isMarker): #ignore non playable services
						continue
					self.bouquetServices.append(service)
			self.checkBouquetServices()
		else:	
			if service is None: # or service.getPath():
				self.close()
				return
		
			self.service = service
			self.has_pdc, self.last_check, self.default_vps = Check_PDC.check_service(self.service)
			self.check.start(50, True)

		self.onLayoutFinish.append(self.setListState)
		
	def setListState(self):
		self["channelList"].setSelectionEnabled(False)

	def checkBouquetServices(self):
		if len(self.bouquetServices):
			self.calledfinished = False
			service = self.bouquetServices.pop(0)

			self.service = service
			self.has_pdc, self.last_check, self.default_vps = Check_PDC.check_service(self.service)
			self.check.start(50, True)
		else:
			text = self["infotext"].getText()
			text += _("Finished")
			self["infotext"].setText(text)
			
	
	def doCheck(self):
		if not Check_PDC.recheck(self.has_pdc, self.last_check):
			self.finish()
			return
		
		self.demux = -1
		if self.simulate_recordService is None:
			self.simulate_recordService = NavigationInstance.instance.recordService(self.service, True)
			if self.simulate_recordService:
				res = self.simulate_recordService.start()
				if res != 0 and res != -1:
					# Fehler aufgetreten (kein Tuner frei?)
					NavigationInstance.instance.stopRecordService(self.simulate_recordService)
					self.simulate_recordService = None
					
					if self.last_serviceref is not None:
						self.finish()
						return
					else:
						cur_ref = NavigationInstance.instance.getCurrentlyPlayingServiceReference()
						if cur_ref and not cur_ref.getPath():
							self.last_serviceref = cur_ref
							NavigationInstance.instance.playService(None)
							self.check.start(1500, True)
							return
				else: # hat geklappt
					self.check.start(1000, True)
					return
		else:
			stream = self.simulate_recordService.stream()
			if stream:
				streamdata = stream.getStreamingData()
				if (streamdata and ('demux' in streamdata)):
					self.demux = streamdata['demux']
			if self.demux != -1:
				self.startProgram()
				return
		
		if self.simulate_recordService is not None:
			NavigationInstance.instance.stopRecordService(self.simulate_recordService)
			self.simulate_recordService = None
		if self.last_serviceref is not None:
			NavigationInstance.instance.playService(self.last_serviceref)
		self.finish()
	
	def startProgram(self):
		sid = self.service.getData(1)
		tsid = self.service.getData(2)
		onid = self.service.getData(3)
		demux = "/dev/dvb/adapter0/demux" + str(self.demux)
		
		if sid != 0 and tsid != 0 and onid != 0:
			cmd = vps_exe + " "+ demux +" 10 "+ str(onid) +" "+ str(tsid) +" "+ str(sid) +" 0"
		
			# start a timer to kill the command after 3 seconds. this is for cases where nothing is returned
			self.execTimer.startLongTimer(3)
			self.program.execute(cmd)
		else:
			# call program_closed to set PDC to unknown
			self.program_closed(0)

	def program_kill(self):
		if self.program.running():
			self.program.sendCtrlC()
	
	def program_closed(self, retval):
		if not self.calledfinished:
			self.setServicePDC(-1)
			self.finish()
		else:
			self.finish()
			
	def program_dataAvail(self, str):
		lines = str.split("\n")
		for line in lines:
			if line == "PDC_AVAILABLE" and not self.calledfinished:
				self.calledfinished = True
				self.setServicePDC(1)
			elif line == "NO_PDC_AVAILABLE" and not self.calledfinished:
				self.calledfinished = True
				self.setServicePDC(0)
	
	def setInfoMessage(self):
		if self.has_pdc == 1:
			text = _("supported")
		elif self.has_pdc == 0:
			text = _("not supported")
		else:
			text = _("unknown")
		servicename = ServiceReference(self.service).getServiceName().replace('\xc2\x86', '').replace('\xc2\x87', '')	
		self.channelList.append(( servicename, text ))
		self["channelList"].updateList(self.channelList)

		if self.mode == "bouquet":
			self.checkBouquetServices()
		else:
			text = self["infotext"].getText()
			text += _("finished")
			self["infotext"].setText(text)			
	
	def setServicePDC(self, state):
		Check_PDC.setServicePDC(self.service, state, self.default_vps)
		self.has_pdc = state
		
	def finish(self, userTriggered=False):
		self.calledfinished = True
		self.check.stop()
		self.execTimer.stop()
		
		if self.simulate_recordService is not None:
			NavigationInstance.instance.stopRecordService(self.simulate_recordService)
			self.simulate_recordService = None
		
		if self.last_serviceref is not None:
			NavigationInstance.instance.playService(self.last_serviceref)
		
		if self.mode == "timer":
			self.ask_user()
		else:
			if not userTriggered:
				self.setInfoMessage()
			else:
				self.close()	
	
	def ask_user(self):
		pass

class VPS_check_PDC_Screen(VPS_check):
	def __init__(self, session, service, timer_entry, manual_timer = True):
		self.timer_entry = timer_entry
		self.manual_timer = manual_timer
		VPS_check.__init__(self, session, service)
	
	def ask_user(self):
		if self.manual_timer:
			if self.has_pdc == 1: # PDC vorhanden
				self.close()
			elif self.has_pdc == 0: # kein PDC
				#nachfragen
				self.session.openWithCallback(self.finish_callback, MessageBox, _("The selected channel doesn't support VPS for manually programmed timers!\n Do you really want to enable VPS?"), default = False)
			else: # konnte nicht ermitteln
				self.session.openWithCallback(self.finish_callback, MessageBox, _("The VPS-Plugin couldn't check if the selected channel supports VPS for manually programmed timers!\n Do you really want to enable VPS?"), default = False)
		else:
			if self.has_pdc == 1: # PDC vorhanden
				self.close()
			else:
				choiceList = [(_("No"), 0), (_("Yes"), 1), (_("Yes, don't ask again"), 2)]
				self.session.openWithCallback(self.finish_callback2, ChoiceBox, title = _("VPS-Plugin couldn't check if the selected channel supports VPS.\n Do you really want to enable VPS?"), list = choiceList)
	
	def finish_callback(self, result):
		if not result:
			self.timer_entry.timerentry_vpsplugin_enabled.value = "no"
			self.timer_entry.createSetup("config")
			self.timer_entry.timerentry_vpsplugin_dontcheck_pdc = False
			#self.timer_entry["config"].setCurrentIndex(self.timer_entry["config"].getCurrentIndex() + 1)
		
		self.close()
	
	def finish_callback2(self, result):
		if result is None or result[1] == 0:
			self.finish_callback(False)
			return
		
		elif result[1] == 2:
			Check_PDC.setServicePDC(self.service, self.has_pdc, 1) # nicht mehr nachfragen
		
		self.close()

class VPS_check_on_instanttimer(VPS_check):
	def __init__(self, session, service, timer):
		self.timer = timer
		VPS_check.__init__(self, session, service)

	def ask_user(self):
		choiceList = [(_("No"), 0), (_("Yes (safe mode)"), 1), (_("Yes"), 2)]
		
		if self.has_pdc == 1:
			if config.plugins.vps.instanttimer.value == "yes":
				self.enable_vps()
			elif config.plugins.vps.instanttimer.value == "yes_safe":
				self.enable_vps_safe()
			else:
				self.session.openWithCallback(self.finish_callback, ChoiceBox, title = _("The channel may support VPS\n Do you want to enable VPS?"), list = choiceList)
		else:
			self.session.openWithCallback(self.finish_callback, ChoiceBox, title = _("VPS-Plugin couldn't check if the channel supports VPS.\n Do you want to enable VPS anyway?"), list = choiceList)
			
	def enable_vps(self):
		self.timer.vpsplugin_enabled = True
		self.timer.vpsplugin_overwrite = True
		vps_timers.checksoon()
		self.close()

	def enable_vps_safe(self):
		self.timer.vpsplugin_enabled = True
		self.timer.vpsplugin_overwrite = False
		vps_timers.checksoon()
		self.close()
	
	def finish_callback(self, result):
		if result is None or result[1] == 0:
			self.close()
		elif result[1] == 1:
			self.enable_vps_safe()
		else:
			self.enable_vps()

