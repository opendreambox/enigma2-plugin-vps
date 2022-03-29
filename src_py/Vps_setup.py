# -*- coding: utf-8 -*-

from Screens.Screen import Screen
from ServiceReference import ServiceReference
from Components.ScrollLabel import ScrollLabel
from Components.ConfigList import ConfigListScreen
from Components.ActionMap import ActionMap
from Components.MultiContent import MultiContentEntryText
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from Components.config import config, getConfigListEntry
from Tools import Directories
from enigma import gFont, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_HALIGN_CENTER, RT_VALIGN_CENTER, RT_WRAP
from time import localtime, strftime
from xml.etree.cElementTree import parse as xml_parse


VERSION = "1.7"

class VPS_Setup(Screen, ConfigListScreen):

	skin = """<screen name="vpsConfiguration" position="center,120" size="1020,670" title="VPS-Plugin">
		<ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="250,40" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/green.png" position="260,5" size="250,40" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/yellow.png" position="510,5" size="250,40" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/blue.png" position="760,5" size="250,40" alphatest="on" />
		<widget source="key_red" render="Label" position="10,5" size="250,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
		<widget source="key_green" render="Label" position="260,5" size="250,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
		<widget source="key_yellow" render="Label" position="510,5" size="250,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#18188b" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
		<widget source="key_blue" render="Label" position="760,5" size="250,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#18188b" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
		<eLabel position="10,50" size="1000,1" backgroundColor="grey" />
		<widget name="config" position="10,60" size="1000,450" enableWrapAround="1" scrollbarMode="showOnDemand" />
		<eLabel position="10,520" size="1000,1" backgroundColor="grey" />
		<widget source="help" render="Label" position="10,530" size="800,130" font="Regular;24" />
	</screen>"""
	
	def __init__(self, session):
		Screen.__init__(self, session)

		#Summary
		self.setup_title = _("VPS Setup Version %s") %VERSION

		self.vps_enabled = getConfigListEntry(_("Enable VPS-Plugin"), config.plugins.vps.enabled)
		self.vps_initial_time = getConfigListEntry(_("Starting time"), config.plugins.vps.initial_time)
		self.vps_margin_after = getConfigListEntry(_("Margin after record (in seconds)"), config.plugins.vps.margin_after)
		self.vps_allow_wakeup = getConfigListEntry(_("Wakeup from Deep-Standby is allowed"), config.plugins.vps.allow_wakeup)
		self.vps_allow_seeking_multiple_pdc = getConfigListEntry(_("Seeking connected events"), config.plugins.vps.allow_seeking_multiple_pdc)
		self.vps_default = getConfigListEntry(_("VPS enabled by default"), config.plugins.vps.vps_default)
		self.vps_instanttimer = getConfigListEntry(_("Enable VPS on instant records"), config.plugins.vps.instanttimer)
		self.vps_showincontext = getConfigListEntry(_("Add VPS-check to channellist context menu"), config.plugins.vps.showincontext)
		
		self.list = []
		self.list.append(self.vps_enabled)
		self.list.append(self.vps_initial_time)
		self.list.append(self.vps_margin_after)
		self.list.append(self.vps_allow_wakeup)
		self.list.append(self.vps_allow_seeking_multiple_pdc)
		self.list.append(self.vps_default)
		self.list.append(self.vps_instanttimer)
		self.list.append(self.vps_showincontext)

		ConfigListScreen.__init__(self, self.list, session = session)
		self["config"].onSelectionChanged.append(self.updateHelp)

		# Initialize Buttons
		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("OK"))
		self["key_yellow"] = StaticText(_("Channels with VPS"))
		self["key_blue"] = StaticText(_("Information"))

		self["help"] = StaticText()

		# Define Actions
		self["actions"] = ActionMap(["SetupActions", "ColorActions"],
			{
				"cancel": self.keyCancel,
				"save": self.keySave,
				"yellow":self.showVpsChannels,
				"blue": self.show_info,
			}
		)
		
		self.onLayoutFinish.append(self.setCustomTitle)

	def showVpsChannels(self):
		self.session.open(VPS_Overview)
		
	def setCustomTitle(self):
		self.setTitle(self.setup_title)
	
	def updateHelp(self):
		cur = self["config"].getCurrent()
		if cur == self.vps_enabled:
			self["help"].text = _("This plugin can determine whether a programme begins earlier or lasts longer. The channel has to provide reliable data.")
		elif cur == self.vps_initial_time:
			self["help"].text = _("If possible, x minutes before a timer starts VPS-Plugin will control whether the programme begins earlier. (0 disables feature)")
		elif cur == self.vps_margin_after:
			self["help"].text = _("The recording will last n seconds longer after the channel sent the stop signal.")
		elif cur == self.vps_default:
			self["help"].text = _("Enable VPS by default (new timers)")
		elif cur == self.vps_allow_wakeup:
			self["help"].text = _("If enabled and necessary, the plugin will wake up the Dreambox from Deep-Standby for the defined starting time to control whether the programme begins earlier.")
		elif cur == self.vps_allow_seeking_multiple_pdc:
			self["help"].text = _("If a programme is interrupted and divided into separate events, the plugin will search for the connected events.")
		elif cur == self.vps_instanttimer:
			self["help"].text = _("When yes, VPS will be enabled on instant records (stop after current event), if the channel supports VPS.")
		elif cur == self.vps_showincontext:
			self["help"].text = _("An entry to check whether channel/channels in bouquet support VPS will be shown in context menu of channel list when activated")

	def show_info(self):
		VPS_show_info(self.session)
	
	def cancelConfirm(self, result):
		if not result:
			return

		for x in self["config"].list:
			x[1].cancel()

		self.close(self.session)

	def keyCancel(self):
		if self["config"].isChanged():
			from Screens.MessageBox import MessageBox

			self.session.openWithCallback(
				self.cancelConfirm,
				MessageBox,
				_("Really close without saving settings?")
			)
		else:
			self.close(self.session)

	def keySave(self):
		for x in self["config"].list:
			x[1].save()

		self.close(self.session)

class VPS_Overview(Screen):
	skin = """<screen name="VPS_Overview" position="center,120" size="820,520" title="VPS-Plugin Overview">
			<widget source="channelList" render="Listbox" position="10,10" size="800,400">
				<convert type="TemplatedMultiContent">
					{
						"templates":
							{
								"default":
									(
										40,
											[
												MultiContentEntryText(pos=(10,0), size=(390,40), flags=RT_HALIGN_LEFT|RT_VALIGN_CENTER|RT_WRAP, font=0, text=0),
												MultiContentEntryText(pos=(400,0), size=(370,40), flags=RT_HALIGN_RIGHT|RT_VALIGN_CENTER|RT_WRAP, font=0, text=1),
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
	
	def __init__(self, session):
		Screen.__init__(self, session)	

		self["actions"] = ActionMap(["OkCancelActions"], 
			{
				"cancel": self.close,
			}, -1)	

		self["channelList"] = List()
		self["channelList"].setBuildFunc(self.buildVpsChannelEntry)
		
		
		self.loadVpsChannels()
		
		self.onLayoutFinish.append(self.setListState)
		
	def setListState(self):
		self["channelList"].setSelectionEnabled(False)

	def loadVpsChannels(self):
		self.vpsChannelList = [("header", _("Channel"), _("Last checked on"))]
		try:
			doc = xml_parse(Directories.resolveFilename(Directories.SCOPE_CONFIG, "vps.xml"))
			xmlroot = doc.getroot()
			
			if xmlroot is not None:
				for xml in xmlroot.findall("channel"):
					has_pdc = xml.get("has_pdc")
					if has_pdc == "1":
						serviceref = xml.get("serviceref").encode("utf-8")
						last_check = xml.get("last_check")
						
						self.vpsChannelList.append(("service", serviceref, last_check ))
		except:
			pass
			
		self["channelList"].setList(self.vpsChannelList)
			
	def buildVpsChannelEntry(self, entrytype, serviceref, last_check):
		if entrytype == "service":
			ref = ServiceReference(serviceref)
		
			servicename = ref.getServiceName().replace('\xc2\x86', '').replace('\xc2\x87', '')
		
			tm = localtime(int(last_check))
			checkdatetime = strftime("%d.%m.%Y, %H:%M", localtime(int(last_check)))
		
			return (servicename, checkdatetime)
		else:
			return (serviceref, last_check )

class VPS_Screen_Info(Screen):
	skin = """<screen name="vpsInfo" position="center,120" size="820,520" title="VPS-Plugin Information">
		<widget name="text" position="10,10" size="800,500" font="Regular;22" />
	</screen>"""
	
	def __init__(self, session):
		Screen.__init__(self, session)
		
		#Summary
		self.info_title = _("VPS-Plugin Information")
		
		self["text"] = ScrollLabel(_("VPS-Plugin can react on delays arising in the startTime or endTime of a programme. VPS is only supported by certain channels!\n\nIf you enable VPS, the recording will only start, when the channel flags the programme as running.\n\nIf you select \"yes (safe mode)\", the recording is definitely starting at the latest at the startTime you defined. The recording may start earlier or last longer.\n\n\nSupported channels\n\nGermany:\n ARD and ZDF\n\nAustria:\n ORF\n\nSwitzerland:\n SF\n\nCzech Republic:\n CT\n\nIf a timer is programmed manually (not via EPG), it is necessary to set a VPS-Time to enable VPS. VPS-Time (also known as PDC) is the first published start time, e.g. given in magazines. If you set a VPS-Time, you have to leave timer name empty."))
		
		self["actions"] = ActionMap(["OkCancelActions", "DirectionActions"], 
			{
				"cancel": self.close,
				"ok": self.close,
				"up": self["text"].pageUp,
				"down": self["text"].pageDown,
			}, -1)
		
		self.onLayoutFinish.append(self.setCustomTitle)
		
	def setCustomTitle(self):
		self.setTitle(self.info_title)
		
	
def VPS_show_info(session):
	session.open(VPS_Screen_Info)
	
