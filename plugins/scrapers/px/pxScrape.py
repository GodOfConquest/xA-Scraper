
import os
import os.path
import traceback
import re
import bs4
import urllib.request
import urllib.parse
from settings import settings
import flags

import plugins.scrapers.ScraperBase

class GetPX(plugins.scrapers.ScraperBase.ScraperBase):

	settingsDictKey = "px"
	pluginName     = "PxGet"

	urlBase         = "http://www.pixiv.net/"
	ovwMode         = "Check Files"

	numThreads      = 5


	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Cookie Management
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def checkCookie(self):

		userID = re.search(r"<Cookie PHPSESSID=[0-9a-f_]*? for \.pixiv\.net/>", "%s" % self.wg.cj, re.IGNORECASE)
		if userID:
			return True, "Have Pixiv Cookie:\n	%s" % (userID.group(0))

		return False, "Do not have Pixiv Cookies"

	def getCookie(self):
		self.log.info("Pixiv Getting cookie")


		logondict = {"mode"    : "login",
					"pixiv_id" : settings[self.settingsDictKey]["username"],
					"pass"     : settings[self.settingsDictKey]["password"],
					"skip"     : "1"}

		pagetext = self.wg.getpage('http://www.pixiv.net/login.php', postData = logondict, addlHeaders={'Referer': 'http://www.pixiv.net/login.php'})
		# print(pagetext)
		if re.search("Logout", pagetext):
			return True, "Logged In"
		else:
			return False, "Login Failed"


	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Individual page scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def getManga(self, artistName, mangaAddr, dlPath, sourceUrl):
		self.log.info("Params = %s, %s, %s, %s", artistName, mangaAddr, dlPath, sourceUrl)
		titleRE = re.compile("<title>(.*?)</title>", re.IGNORECASE)

		successed = True

		# print mangaAddr,

		mangaPgCtnt = self.wg.getpage(mangaAddr, addlHeaders={'Referer': sourceUrl})			# Spoof the referrer to get the big image version

		if mangaPgCtnt == "Failed":
			self.log.info("cannot get manga page")

		else:
			titleReResult = titleRE.search(mangaPgCtnt)

			if titleReResult:
				self.log.info("Found file Title : %s" % (titleReResult.group(1)))
				mangaTitle = titleReResult.group(1)
				mangaTitle = re.sub('[\\/:*?"<>|]', "", mangaTitle)
			else:
				mangaTitle = None

			soup = bs4.BeautifulSoup(mangaPgCtnt)
			imageTags = soup.find_all("img", {"data-filter" : "manga-image"})

			linkSet = set()
			for imTag in imageTags:
				linkSet.add((imTag["data-src"], imTag["data-index"]))


			regx4 = re.compile("http://.+/")				# FileName RE

			self.log.info("Found %s page manga!" % len(linkSet))
			if len(linkSet) < 1:
				self.log.error("No Images on page?")
				return "Failed", ""

			for link, indice in linkSet:
				filename = regx4.sub("" , link)
				filename = filename.rsplit("?")[0]

				if mangaTitle != None:
					pass
					# self.log.info("%s - %s" % (regx4.sub("" , link), mangaTitle))


				filePath = os.path.join(dlPath, filename)
				if not self._checkFileExists(filePath):

					imgdath = self.wg.getpage(link, addlHeaders={'Referer': mangaAddr})							# Request Image

					if imgdath == "Failed":
						self.log.error("cannot get manga page")
						successed = False

					else:
						self.log.info("Successfully got: " + filename)
						#print os.access(imPath, os.W_OK), imPath
						#print "Saving"
						writeErrors = 0
						while writeErrors < 3:
							try:
								with open(filePath, "wb") as fp:
									fp.write(imgdath)
								break
							except:
								self.log.critical(traceback.format_exc())
								writeErrors += 1
						else:
							self.log.critical("Could not save file - %s " % filePath)
							successed = False

						#(self, artist, pageUrl, fqDlPath, seqNum=0):

						self.log.info("Successfully got: " + link)
						self._updatePreviouslyRetreived(artistName, sourceUrl, filePath, indice)

				else:
					self.log.info("%s Exists, skipping..." % filename)



			self.log.info("Total %s " % len(linkSet))
			if successed:
				return "Ignore", None

			else:
				return "Failed", ""

		raise RuntimeError("How did this ever execute?")



	def _getContentUrlFromPage(self, soupIn):

		pass


	def _extractTitleDescription(self, soupin):

		infoContainer = soupin.find(class_="work-info")
		if infoContainer:
			itemTitle = infoContainer.find("h1", class_="title")
			if itemTitle:
				itemTitle = itemTitle.get_text()
			itemCaption = infoContainer.find("p", class_="caption")
			if itemCaption:
				itemCaption = itemCaption.get_text()
			print("title = ", itemTitle)
			print("caption = ", itemCaption)
		else:
			itemTitle = ""
			itemCaption = ""

		return itemTitle, itemCaption

	def _getArtPage(self, dlPathBase, artPageUrl, artistName):

		'''
		Pixiv does a whole lot of referrer sniffing. They block images, and do page redirects if you don't submit the correct referrer.
		Also, I *think* they will block flooding, so that's the reason for the delays everywhere.
		'''

		imgurl = ""
		mpgctnt = ""


		self.log.info("Waiting...")

		self.log.info("Getting = %s" % artPageUrl)
		refL = artPageUrl


		basePageCtnt = self.wg.getpage(refL)

		if basePageCtnt == "Failed" or not basePageCtnt:
			self.log.info("cannot get manga test page")

		else:
			try:
				baseSoup = bs4.BeautifulSoup(basePageCtnt)
				mainSection = baseSoup.find('div', attrs={"class" : "works_display"})
				link = "%s%s" % ("http://www.pixiv.net/", mainSection.find("a")["href"])

			except:
				self.lot.error("link - %s", link)
				self.lot.error("Mainsection - %s", mainSection)
				self.lot.error("Soup - %s", baseSoup)

				traceback.print_exc()

				return "Failed", ""

			if link.find("manga") + 1:
				self.log.info("Multipage/Manga link")
				return self.getManga(artistName, link, dlPathBase, artPageUrl)
			else:

				titleRE = re.compile("<title>(.*?)</title>", re.IGNORECASE)

				mpgctnt = self.wg.getpage(link, addlHeaders={'Referer': refL})			# Spoof the referrer to get the big image version

				if mpgctnt == "Failed":
					self.log.info("cannot get page")
					return "Failed", ""

				print("Page length = ", len(mpgctnt))
				soup = bs4.BeautifulSoup(mpgctnt)
				imgPath = soup.find("img")


				if imgPath:
					self.log.info("%s%s" % ("Found Image URL : ", imgPath["src"]))

					imgurl = imgPath["src"]

				regx4 = re.compile("http://.+/")				# FileName RE
				fname = regx4.sub("" , imgurl)

				titleReResult = titleRE.search(mpgctnt)

				if titleReResult:
					self.log.info("%s%s" % ("Found file Title : ", titleReResult.group(1)))

				imgTitle = fname		# No imagename on page

				itemTitle, itemCaption = self._extractTitleDescription(baseSoup)


				if imgurl == "" :
					self.log.error("OH NOES!!! No image on page = " + link)

					return "Failed", ""										# Return Fail
				else:

					# fname = "%s.%s" % (fname, ftype)
					fname = fname.rsplit("?")[0] 		# Sometimes there is some PHP stuff tacked on the end of the Image URL. Split on the indicator("?"), and throw away everything after it.

					self.log.info("			Filename = " + fname)
					self.log.info("			Page Image Title = " + imgTitle)
					self.log.info("			FileURL = " + imgurl)

					filePath = os.path.join(dlPathBase, fname)
					if not self._checkFileExists(filePath):

						imgdath = self.wg.getpage(imgurl, addlHeaders={'Referer': link})							# Request Image

						if imgdath == "Failed":
							self.log.info("cannot get image")
							return "Failed", ""
						self.log.info("Successfully got: " + fname)
						# print fname
						try:
							with open(filePath, "wb") as fp:
								fp.write(imgdath)
						except:
							self.log.critical("cannot save image")
							self.log.critical(traceback.print_exc())
							self.log.critical("cannot save image")

							return "Failed", ""

						self.log.info("Successfully got: " + imgurl)
						self.log.info("Saved to path: " + filePath)
						return "Succeeded", filePath, itemCaption, itemTitle
					else:
						self.log.info("Exists, skipping... (path = %s)", filePath)
						return "Exists", filePath, itemCaption, itemTitle

		raise RuntimeError("How did this ever execute?")

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Gallery Scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _getTotalArtCount(self, artist):
		basePage = "http://www.pixiv.net/member_illust.php?id=%s" % artist
		page = self.wg.getSoup(basePage)

		mainDiv = page.find("div", class_="layout-a")
		if not mainDiv:
			raise LookupError("Could not retreive artist item quantity!")
		countSpan = mainDiv.find("span", class_="count-badge")
		if not countSpan:
			raise LookupError("Could not retreive artist item quantity!")

		text = countSpan.text.split()[0]
		text = ''.join([char for char in text if char in '0123456789'])
		return int(text)


	def _getItemsOnPage(self, inSoup):

		links = set()

		imgItems = inSoup.find_all("li", class_="image-item")
		for tag in imgItems:
			url = urllib.parse.urljoin(self.urlBase, tag.a["href"])
			links.add(url)

		return links


	def _getGalleries(self, artist):


		# re string is "該当ユーザーのアカウントは停止されています。" escaped, so the encoding does not mangle it.
		# It translates to "This account has been suspended"
		suspendedAcctRe = re.compile("\xe8\xa9\xb2\xe5\xbd\x93\xe3\x83\xa6\xe3\x83\xbc\xe3\x82\xb6\xe3\x83\xbc\xe3\x81\xae\xe3\x82\xa2\xe3\x82\xab\xe3\x82\xa6\xe3\x83\xb3\xe3\x83\x88\xe3\x81\xaf\xe5\x81\x9c\xe6\xad\xa2\xe3\x81\x95\xe3\x82\x8c\xe3\x81\xa6\xe3\x81\x84\xe3\x81\xbe\xe3\x81\x99\xe3\x80\x82")


		iterCounter = 0


		artlinks = set()

		while 1:
			turl = "http://www.pixiv.net/member_illust.php?id=%s&p=%s" % (artist, iterCounter+1)
			self.log.info("Getting = " + turl)
			mpgctnt = self.wg.getpage(turl)
			if mpgctnt == "Failed":
				self.log.info("Cannot get Page")
				return set()
			if suspendedAcctRe.search(mpgctnt):
				self.log.critical("Account has been suspended. You should probably remove it from your favorites")
				self.log.critical("Account # %s" % artist)
				self.log.critical("Gallery URL - %s" % turl)
				return set()

			soup = bs4.BeautifulSoup(mpgctnt)
			new = self._getItemsOnPage(soup)
			new = new - artlinks

			if not len(new) or not flags.run:
				break

			artlinks |= new

			if iterCounter > 500:
				self.log.critical("This account seems to have too many images, or is defunct.")
				self.log.critical("Account: %s" % artist)

				artlinks = set()
				break

			iterCounter += 1

		self.log.info("Found %s links" % (len(artlinks)))


		if ((iterCounter * 20) - len(artlinks)) > 20:
			self.log.warning("We seem to have found less than 20 links per page. are there missing files?")
			self.log.warning("Found %s links on %s pages. Should have found %s - %s links" % (len(artlinks), iterCounter, (iterCounter - 1) * 20, iterCounter * 20))

		return artlinks



	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Target management and indirection
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def getNameList(self):

		self.log.info("Getting list of favourite artists.")

		breakFlag = True
		counter = 1
		content = ""
		resultList = set()
		nameRE = re.compile(r'<a href="member\.php\?id=(\d*?)"')

		while 1:
			breakFlag = True
			pageURL = "http://www.pixiv.net/bookmark.php?type=user&rest=show&p=%d" % (counter)
			content = self.wg.getpage(pageURL)
			if content == "Failed":
				self.log.info("cannot get image")
				return "Failed"

			temp = nameRE.findall(content)
			new = set(temp)
			new = new - resultList

			counter += 1


			if not len(new) or not flags.run:			# Break when none of the new names were original
				break

			resultList |= new

			self.log.info("Names found so far - %s", len(resultList))

		self.log.info("Found %d Names" % len(resultList))

		return resultList
