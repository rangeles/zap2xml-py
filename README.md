# zap2xml-py
A very simple script to fetch EPG data from gracenote.com and write it to XMLTV format.

## Notes

### 2025 Jul 3 - Ron Angeles

One of the original stated aims was to keep to standard libaries and, honestly, it is an admirable aim. Today, I've broken that aim. Moving forward with this fork, I'll be using `requests` and `requests-cache`. `requests` is considered by many, with me included, to be a defacto standard for HTTP requests. And `requests-cache` is a nice layer on top which handles caching more robustly than the current implementation, or any implementation that I could come up with.

### 2020 Jun 14 - arantius

Around June 2020 the `zap2xml.pl` I had stopped working.  It generated HTTP requests that gave only 400 responses.  I tried to patch it, to the point that it got OK responses, but parsed no data from them.  The zap2it site must have changed.  I thought they had an API, but apparently this tool has always scraped the internal JSON feed, intended just for the web site?

So re-write from scratch.  Simplest possible form I can, so the fewest things need to change if the site ever does again.  The goal is to feed guide data into Tvheadend.

The zap2it site, at least for my area/OTA, will give "400 Bad Request" errors *for certain times* of certain days.  Even their own site does this!  This is the error that recently started tripping up `zap2xml.pl`.  So this tool simply ignores 400 errors, continuing to gather the data available for other time windows.

Written to have only standard library dependencies.