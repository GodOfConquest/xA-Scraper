
import os
import os.path
import traceback
import copy
import bs4
import urllib.request
import urllib.parse
import time
import webFunctions as wg
from settings import settings

from natsort import natsorted

import plugins.uploaders.UploadBase

class UploadEh(plugins.uploaders.UploadBase.UploadBase):

	settingsDictKey = "eh"
	pluginName = "Eh.Ul"

	ovwMode = "Check Files"

	numThreads = 1



	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Cookie management sillyness
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------


	def checkLogin(self):

		checkPage = self.wg.getpage(r"https://forums.e-hentai.org/index.php?")
		if "Logged in as" in checkPage:
			self.log.info("Still logged in")
			return
		else:
			self.log.info("Whoops, need to get Login cookie")

		logondict = {
			# Note: Case sensitive!
			"UserName"   : settings["eh"]["username"],
			"PassWord"   : settings["eh"]["password"],
			"referer"    : "https://forums.e-hentai.org/index.php?",
			"CookieDate" : "Log me in",
			"b"          : '',
			"bt"         : '',
			"submit"     : "Log me in"
			}


		getPage = self.wg.getpage(r"https://forums.e-hentai.org/index.php?act=Login&CODE=01", postData=logondict)
		if "Username or password incorrect" in getPage:
			self.log.error("Login failed!")
			with open("pageTemp.html", "wb") as fp:
				fp.write(getPage)
		elif "You are now logged in as:" in getPage:
			self.log.info("Logged in successfully!")

		self.permuteCookies()
		self.wg.saveCookies()

	# So exhen uses some irritating cross-site login hijinks.
	# Anyways, we need to copy the cookies for e-hentai to exhentai,
	# so we iterate over all cookies, and duplicate+modify the relevant
	# cookies.
	def permuteCookies(self):
		self.log.info("Fixing cookies")
		for cookie in self.wg.cj:
			if "ipb_member_id" in cookie.name or "ipb_pass_hash" in cookie.name:

				dup = copy.copy(cookie)
				dup.domain = 'exhentai.org'

				self.wg.addCookie(dup)


	# MOAR checking. We load the root page, and see if we have anything.
	def checkExAccess(self):
		dummy_exPg, handle = self.wg.getpage("http://exhentai.org/", returnMultiple=True)
		return "text" in handle.headers.get("Content-Type")



	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# convenience Methods
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def extractGid(self, inUrl):
		urlQuery = urllib.parse.urlparse(inUrl)[4]
		newGid = urllib.parse.parse_qs(urlQuery)["gid"].pop()
		newGid = int(newGid)
		return newGid

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Actual uploading bits
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------





	def getToProcess(self):

		cur = self.conn.cursor()

		cols = list(settings["ulConf"].keys())
		cols.sort()
		cols = [key+'id' for key in cols]
		cols = ", ".join(cols)

		ret = cur.execute('SELECT id, uploadTime, uploadedItems, galleryId, {cols} FROM {table};'.format(table=settings["dbConf"]["uploadGalleries"], cols=cols))
		rets = ret.fetchall()

		ids = []
		for keyset in rets:
			for key in keyset[4:]:
				if key != None:
					ids.append(key)

		items = {}
		for row in rets:
			site = row[0]
			item = row[1:]
			if not site in items:
				items[site] = item
			else:
				raise ValueError("Duplicate primary keys? Watttttttttttttttttt")

		# print("Items", items)

		opts = ["id={id}".format(id=val) for val in ids]
		opts = " OR ".join(opts)

		ret = cur.execute('SELECT id, lower(artistName) FROM {table} WHERE {condition};'.format(table=settings["dbConf"]["namesDb"], condition=opts))
		rets = ret.fetchall()
		nameLUT = dict(rets)

		return items, nameLUT



	def uploadFromRowId(self, rowId, siteName, aName):

		print("Should process %s, %s, %s" % (rowId, siteName, aName))

	def getExtantGalleries(self):
		ret = []

		pagetext = self.wg.getpage('http://ul.exhentai.org/manage.php', addlHeaders={"Referer" : "http://exhentai.org/"})
		if pagetext == "err":
			raise ValueError("Login cookies damaged. Error!")

		soup = bs4.BeautifulSoup(pagetext)
		items1 = soup.find_all("tr", class_="gtr1")
		items2 = soup.find_all("tr", class_="gtr0")

		items = items1+items2

		for item in items:
			itemTd = item.find("td", class_="gtc1")
			aName = itemTd.get_text().rsplit(" - ", 1)[0]
			aName = aName.rstrip().lstrip().lower()

			itemUrl = itemTd.a["href"]
			urlQuery = urllib.parse.urlparse(itemUrl)[4]
			itemGid = urllib.parse.parse_qs(urlQuery)["gid"].pop()

			ret.append((aName, int(itemGid)))

		return ret


	def createGallery(self, aName, uniques, totalItems):
		# pagetext = self.wg.getpage('http://ul.exhentai.org/manage.php?act=new')
		# soup = bs4.BeautifulSoup(pagetext)

		# form = soup.find("form", action="http://ul.exhentai.org/manage.php?act=new")
		# items = form.find_all("input")
		# formDict = {}
		# for item in items:
		# 	if "name" in item.attrs and "value" in item.attrs:
		# 		formDict[item["name"]] = item["value"]

		# formDict["tos"]

		formDict = {}

		title       = "%s - Collected Works" % aName.title()
		description = """Assorted art from varied sources for artist: %s.

		Auto-Gallery System 0.0001c (barrel-o-bugs version)
		This is an automatically maintained gallery. Please direct any issues/complaints/complements to fake0name@tfwno.gf.

		Items are sorted alphabetically. Sorry, not much I can do about any ordering issues, if there is a problem,
		take it up with the artist (and their poor filenaming practices).

		By SHA-1 duplicate checking, this gallery should contain %s new items, %s duplicates, and is therefore
		a super-set of any previously uploaded galleries. These values only reflect the initial upload state, though, and will miss items
		that have been recompressed/resaved.

		If there is an artist on DeviantArt, HentaiFoundry, FurAffinity, Weasyl, InkBunny or Pixiv you would
		like a mirror of, feel free to ask. I currently have automated systems in place to
		periodically update my local mirror of all four of these sites, and adding
		additional targets to scrape is a trivial matter.

		Updates are limited to at-max once every two weeks, as the rules require. If you see updates more often then that, please
		report the issue, and I'll see about fixing it as soon as possible.
		""" % (aName.title(), uniques, totalItems-uniques)

		formDict["gname"]         = title
		formDict["gname_jpn"]     = ""
		formDict["gfldr"]         = 2
		formDict["gfldrnew"]      = ""
		formDict["comment"]       = description
		formDict["publiccat"]     = 10
		formDict["tos"]           = "on"
		formDict["creategallery"] = "Create+and+Continue"

		# print(formDict)

		pagetext = self.wg.getpage('http://ul.exhentai.org/manage.php?act=new', postData=formDict)

		soup = bs4.BeautifulSoup(pagetext)
		forward = soup.find('p', id='continue')

		newGid = self.extractGid(forward.a['href'])

		print("Created gallery for ", aName)
		return newGid

	def uploadFile(self, gid, filePath):

		gurl = 'http://ul.exhentai.org/manage.php?act=add&gid={gId}'.format(gId=gid)

		with open(filePath, "rb") as fp:
			fcont = fp.read()
		fName = os.path.split(filePath)[-1]
		form = wg.MultiPartForm()
		form.add_field("MAX_FILE_SIZE", '52428800')
		form.add_field("ulact", 'ulmore')
		form.add_file("file01", fName, fcont)

		self.wg.getpage(gurl, binaryForm=form)


	def addUpdateNote(self, rowId, newItems):
		galId = self.getUploadState(rowId)[-1]
		gurl = 'http://ul.exhentai.org/manage.php?act=modify&return=preview&gid={gId}'.format(gId=galId)

		pg = self.wg.getpage(gurl)
		soup = bs4.BeautifulSoup(pg)
		# print(soup)

		galTitle = soup.form.table.find("input", attrs={"name":'gname'})
		print(galTitle['value'])


		description = soup.form.table.textarea.string
		if "Updates:" in description:
			description += "\n"
		else:
			description += "\n\nUpdates:\n"

		description += "{now} - Added {num} new images to gallery.".format(now=time.strftime("%Y-%m-%d"), num=newItems)

		print(description)

		formDict = {}
		formDict["gname"]         = galTitle['value']
		formDict["gname_jpn"]     = ""
		formDict["gfldr"]         = 2
		formDict["gfldrnew"]      = ""
		formDict["comment"]       = description
		formDict["publiccat"]     = 10
		formDict["tos"]           = "on"
		formDict["modifygallery"] = "Confirm+Changes"


		pagetext = self.wg.getpage('http://ul.exhentai.org/manage.php?act=modify&gid={gId}'.format(gId=galId), addlHeaders={"Referer":gurl}, postData=formDict)

		if not "The gallery data was successfully modified." in pagetext:
			print(pagetext)
			raise ValueError("Failed to modify gallery page?")


	def getGalleryStates(self):

		ret = {}

		pagetext = self.wg.getpage('http://ul.exhentai.org/manage.php', addlHeaders={"Referer" : "http://exhentai.org/"})
		if pagetext == "err":
			raise ValueError("Login cookies damaged. Error!")
		soup = bs4.BeautifulSoup(pagetext)

		types = (('unlocked', 'gtable2'), ('locked', 'gtable4'))

		for type, tableId in types:
			ret[type] = []

			table = soup.find('table', id=tableId)

			items1 = table.find_all("tr", class_="gtr1")
			items2 = table.find_all("tr", class_="gtr0")

			items = items1+items2

			for item in items:
				itemTd = item.find("td", class_="gtc1")
				aName = itemTd.get_text().rsplit(" - ", 1)[0]
				aName = aName.rstrip().lstrip().lower()

				itemUrl = itemTd.a["href"]
				urlQuery = urllib.parse.urlparse(itemUrl)[4]
				itemGid = urllib.parse.parse_qs(urlQuery)["gid"].pop()

				ret[type].append(int(itemGid))
		if ret['unlocked'] == ret['locked']:
			raise ValueError("Locked and unlocked?")

		return ret


	def unlockGallery(self, ulRowId):

		self.log.info("RowId to unlock: %s", ulRowId)
		self.log.info("Row is for '%s'", self.getNamesForUlRow(ulRowId))
		galId = self.getUploadState(ulRowId)[-1]
		gurl = 'http://ul.exhentai.org/manage.php?act=add&gid={gId}'.format(gId=galId)
		pg = self.wg.getpage(gurl, addlHeaders={"Referer":'http://ul.exhentai.org'})
		if 'This gallery cannot be added to in its current published state' in pg:
			self.log.info("Gallery locked. Cloning and unlocking")

			params = {
				"qa_unlock":"Clone and Unlock"
			}
			pg = self.wg.getpage(gurl, postData=params)

			if not 'The gallery has been successfully cloned and unlocked' in pg:
				raise ValueError("Gallery not unlocked! Wat?")
			soup = bs4.BeautifulSoup(pg)
			cont = soup.find('p', id="continue")
			newGid = self.extractGid(cont.a['href'])

			self.log.info("New galleryId = %s", newGid)

			self.updateGalleryId(ulRowId, newGid)

		elif 'Upload new files to gallery' in pg:
			self.log.info("Gallery already unlocked")

		else:
			self.log.error("Cannot even access gallery?")
			self.log.error(pg)
			raise ValueError("Cannot unlock gallery?")


	def updateGallery(self, rowId, images):
		lastUl, ulQuantity, galleryId = self.getUploadState(rowId)

		new = 0

		remaining = len(images)
		for image in images:
			if self.haveUploaded(image):
				self.log.info("Skipping '%s'", image)
			else:
				self.uploadFile(galleryId, image)
				self.addUploaded(rowId, image)
				new += 1

			remaining -= 1
			self.log.info("Remaining to upload - %s of %s", remaining, len(images))

		return new

		# print("rowId", rowId, "images", images)

	def checkGallery(self, haveItems, ulTableRowId):

		ret = self.getSiteIds(ulTableRowId)
		# drop all keys which we're not uploading (v == None)
		ret = dict(
					[(k,v) for k,v in ret.items() if v ]
					)


		states = self.getGalleryStates()
		print(states)

		print("Row", ulTableRowId)
		for key, value in ret.items():
			print(self.getByRowId(value))


		for sourceSite, artistRowId in ret.items():
			try:
				images = self.getImagesForId(artistRowId)
			except ValueError:
				self.log.error("Failure getting downloads for artist '%s'!", self.getByRowId(artistRowId))
				self.log.error("Artist has not been downloaded, or cannot find download path!")
				return

			images = natsorted(images)
			dummy_siteName, aName = self.getByRowId(artistRowId)

			haveGalId = self.getGalleryIdById(ulTableRowId)
			print(haveGalId)
			if haveGalId == None:


				numUnique = self.checkIfShouldUpload(images)

				if numUnique > 3:
					newGid = self.createGallery(aName, numUnique, len(images))
					self.insertGalleryId(ulTableRowId, newGid)
					self.updateGallery(ulTableRowId, images)
				else:
					self.log.warn("Do not have sufficent unique items to warrant upload for artist %s!", aName)

			else:

				ulQuantity = len(self.getUploaded(artistRowId))
				if len(images) < ulQuantity+3:
					self.log.info("Do not have enough new content to warrant updating (%s new item(s)). Skipping.", len(images) - ulQuantity)
					return

				newImages = len(images) - ulQuantity

				try:

					galId = self.getUploadState(ulTableRowId)[-1]

					self.log.info("Need to update gallery for '%s' (%s new item(s)).", aName, newImages)
					if galId in states['unlocked']:
						self.log.info("Gallery already unlocked. No need to update.")
					elif galId in states['locked']:
						self.unlockGallery(ulTableRowId)
					else:
						self.log.error("Missing GId %s from locked and unlocked lists!", galId)
						self.log.error("Locked list: %s", states['locked'])
						self.log.error("Unlocked list: %s", states['unlocked'])
						raise KeyError("GalleryID %s not in locked or unlocked lists!" % galId)


					actuallyNew = self.updateGallery(ulTableRowId, images)
					self.addUpdateNote(ulTableRowId, actuallyNew)
					self.setUpdateTimer(ulTableRowId, time.time())
				except ValueError:
					self.log.critical("Update Failed!")
					self.log.critical(traceback.format_exc())
					raise




	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Deduplication stuff
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def syncGalleryIds(self):
		self.log.info("Synchronizing gallery IDs")
		existG = self.getExtantGalleries()

		existG = dict(existG)

		toUl, nameLUT = self.getToProcess()

		for dbId, row in toUl.items():
			ulTime, uploadedItems, isId = row[:3]

			names = [nameLUT[idNo] for idNo in row[3:] if idNo != None]

			for name in existG:



				if name in names:
					if isId != existG[name]:
						print("Bad GalleryId!", isId, existG[name])
						self.updateGalleryId(dbId, existG[name])

				if not name in existG:
					print("Failed to cross-link!")
					print(name)
					print(names)
					print(existG)
					print(name in existG)
					raise KeyError




	def checkIfHashExists(self, hashS):
		pagetext = self.wg.getpage('http://exhentai.org/?f_shash=%s' % hashS)
		if "No hits found" in pagetext:
			return False
		return True

	def checkIfShouldUpload(self, fileList):
		uniques = 0
		nonuniq = 0
		toScan = len(fileList)
		for fileN in fileList:

			fHash = self.getHashOfFile(fileN)
			if not self.checkIfHashExists(fHash):
				uniques += 1
				self.log.info("Unique item '%s', '%s', '%s'", uniques, nonuniq, fileN)
			else:
				nonuniq += 1
				self.log.info("Non-unique item '%s', '%s', '%s'", uniques, nonuniq, fileN)

			toScan -= 1
			self.log.info("Remaining to check - %s of %s", toScan, len(fileList))
			time.sleep(2)


		return uniques




	def processTodo(self, listIn, ulFilter):

		existingGalleries = self.getExtantGalleries()

		# print("Existing galleries", existingGalleries)
		for itemName, itemGid in existingGalleries:
			self.log.info("Have gallery %s, %s", itemName, itemGid)



		listIn, nameLUT = listIn


		for ulTableRowId, data in listIn.items():
			lastUl = data[0]

			if lastUl < (time.time() - 60*60*24*28):
				try:
					self.checkGallery(existingGalleries, ulTableRowId)
				except Exception:
					self.log.error("Exception!")
			else:

				self.log.info("Item '%s' (artist(s) '%s') updated within the last 3 weeks. Skipping", ulTableRowId, self.getNamesForUlRow(ulTableRowId))




	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Task management
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------


	def go(self, ulFilter=[], toDoList=None, ctrlNamespace=None):
		if ctrlNamespace == None:
			raise ValueError("You need to specify a namespace!")
		self.manager = ctrlNamespace

		try:
			self.wg.cj.clear("exhentai.org")
		except KeyError:
			print("Keyerror = Wat")




		self.statusMgr.updateRunningStatus(self.settingsDictKey, True)
		startTime = time.time()
		self.statusMgr.updateLastRunStartTime(self.settingsDictKey, startTime)
		self.checkInitPrimaryDb()

		self.checkLogin()

		haveEx = self.checkExAccess()
		if not haveEx:

			self.wg.cj.clear("exhentai.org")
			self.wg.cj.clear("e-hentai.org")
			raise ValueError("Logged in, but cannot access ex?")

		self.syncGalleryIds()


		if not toDoList:
			toDoList = self.getToProcess()


		self.processTodo(toDoList, ulFilter)


		self.statusMgr.updateRunningStatus(self.settingsDictKey, False)
		runTime = time.time()-startTime
		self.statusMgr.updateLastRunDuration(self.settingsDictKey, runTime)


	@classmethod
	def run(cls, managedNamespace):
		instance = cls()
		instance.go(ctrlNamespace=managedNamespace)

