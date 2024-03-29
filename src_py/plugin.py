# -*- coding: utf-8 -*-

from Plugins.Plugin import PluginDescriptor
from os import stat
from Vps import vps_timers
from Vps_setup import VPS_Setup
from Vps_check import VPS_check
from Modifications import register_vps
from enigma import eServiceReference

# Config
from Components.config import config, ConfigYesNo, ConfigSubsection, ConfigInteger, ConfigSelection, configfile

config.plugins.vps = ConfigSubsection()
config.plugins.vps.enabled = ConfigYesNo(default = True)
config.plugins.vps.initial_time = ConfigInteger(default=10, limits=(0, 120))
config.plugins.vps.allow_wakeup = ConfigYesNo(default = False)
config.plugins.vps.allow_seeking_multiple_pdc = ConfigYesNo(default = True)
config.plugins.vps.vps_default = ConfigSelection(choices = [("no", _("No")), ("yes_safe", _("Yes (safe mode)")), ("yes", _("Yes"))], default = "no") 
config.plugins.vps.instanttimer = ConfigSelection(choices = [("no", _("No")), ("yes_safe", _("Yes (safe mode)")), ("yes", _("Yes")), ("ask", _("always ask"))], default = "ask")
config.plugins.vps.infotext = ConfigInteger(default=0)
config.plugins.vps.margin_after = ConfigInteger(default=10, limits=(0, 600)) # in seconds
config.plugins.vps.wakeup_time = ConfigInteger(default=-1)
config.plugins.vps.showincontext = ConfigYesNo(default = False)


recordTimerWakeupAuto = False

def autostart(reason, **kwargs):
	if reason == 0:
		if kwargs.has_key("session"):
			session = kwargs["session"]
			vps_timers.session = session
			vps_timers.checkTimer()

			try:
				from Plugins.Extensions.WebInterface.WebChilds.Toplevel import addExternalChild
				from Plugins.Extensions.WebInterface.WebChilds.Screenpage import ScreenPage
				from twisted.web import static
				from twisted.python import util
				from enigma import eEnv
			except ImportError as ie:
				pass
			else:
				if hasattr(static.File, 'render_GET'):
					class File(static.File):
						def render_POST(self, request):
							return self.render_GET(request)
				else:
					File = static.File

				root = File(eEnv.resolve("${libdir}/enigma2/python/Plugins/SystemPlugins/vps/web-data"))
				root.putChild("web", ScreenPage(session, util.sibpath(__file__, "web"), True))
				addExternalChild(("vpsplugin", root, "VPS-Plugin", "1", False))
		else:
			register_vps()
	
	elif reason == 1:
		vps_timers.shutdown()

		try:		
			if config.plugins.vps.wakeup_time.value != -1 and config.plugins.vps.wakeup_time.value == config.misc.prev_wakeup_time.value:
				# Folgendes wird nur wegen spezieller Anforderungen des Plugins gesetzt.
				# Damit sich Enigma2 so verhält, wie wenn es für eine Aufnahme aus dem Standby aufwacht.
				config.misc.prev_wakeup_time_type.value = 0
				config.misc.prev_wakeup_time_type.save()
				config.misc.isNextRecordTimerAfterEventActionAuto.value = recordTimerWakeupAuto
				config.misc.isNextRecordTimerAfterEventActionAuto.save()
				
				# Da E2 die Configdatei noch vor dem Aufruf von autostart shutdown abspeichert, muss hier nochmal abgespeichert werden.
				configfile.save()
		
		except:
			print "[VPS-Plugin] exception in shutdown handler, probably old enigma2"
		

def setup(session, **kwargs):
	session.openWithCallback(doneConfig, VPS_Setup)

def doneConfig(session, **kwargs):
	vps_timers.checkTimer()

def startSetup(menuid):
	if menuid != "services_recordings":
		return []
	return [(_("VPS Settings"), setup, "vps", 50)]
	
def getNextWakeup():
	global recordTimerWakeupAuto
	t, recordTimerWakeupAuto = vps_timers.nextWakeup()
	config.plugins.vps.wakeup_time.value = t
	config.plugins.vps.save()
	
	return t

def checkVpsAvailability(session, ref, csel, **kwargs):
	inBouquetRootList = isBouquetAndOrRoot(csel)

	if inBouquetRootList:
		session.open(VPS_check, ref, "bouquet")
	else:
		session.open(VPS_check, ref, "service")

def checkconfig(csel):
	isValid = config.plugins.vps.showincontext.value
	current = csel.getCurrentSelection()
	if  current.flags & eServiceReference.isMarker:
		isValid = False
	return isValid

def isBouquetAndOrRoot(csel):
	inBouquet = csel.getMutableList() is not None
	current_root = csel.getRoot()
	current_root_path = current_root and current_root.getPath()
	inBouquetRootList = current_root_path and current_root_path.find('FROM BOUQUET "bouquets.') != -1 #FIXME HACK
	return inBouquetRootList

def Plugins(**kwargs):
	return [
		PluginDescriptor(
			name = "VPS",
			where = [
				PluginDescriptor.WHERE_AUTOSTART,
				PluginDescriptor.WHERE_SESSIONSTART
			],
			fnc = autostart,
			wakeupfnc = getNextWakeup,
			needsRestart = True
		),
		PluginDescriptor(
			name = _("VPS Settings"),
			where = PluginDescriptor.WHERE_MENU,
			fnc = startSetup,
			needsRestart = True,
			description=_("Settings for VPS"),
		),
		PluginDescriptor(
			name = _("Check VPS support"),
			description = _("Check VPS support"),
			where = PluginDescriptor.WHERE_CHANNEL_CONTEXT_MENU,
			fnc = checkVpsAvailability,
			helperfnc=checkconfig,
		),
	]
