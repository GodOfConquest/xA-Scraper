xA-Scraper
============

This is a automated tool for scraping content from a number of art sites:

- DeviantArt
- FurAffinity
- HentaFoundry
- Pixiv



It also has grown a lot of other functions over time. It has a fairly complex,
interactive web-interface for browsing the local gallery mirrors, and a tool
for uploading galleries to aggregation sites (currently exhentai) is
in progress.

It has a lot in common with my other scraping system, [MangaCMS](https://github.com/fake-name/MangaCMS/). They both use
the same software stack (CherryPy, Pyramid, Mako, BS4). This is actually an older project, but I did not decide to release
it before now.

Dependencies:

 - CherryPy
 - Pyramid
 - Mako
 - BeautifulSoup 4

Currently, there are some aspects that need work. The artist selection system is currently a bit broken, as I was
in the process of converting it from being based on text-files to being stored in the database. Currently, there isn't a clean way to remove artists from the scrape list, though you can add or modify them.


