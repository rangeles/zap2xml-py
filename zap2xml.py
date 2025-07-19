#!/usr/bin/env python
# Copyright (c) 2020 arantius
# Copyright (c) 2025 Ron Angeles
# SPDX-License-Identifier: MIT

import argparse
import datetime
import logging
import pathlib
from requests_cache import CachedSession
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET

logging.basicConfig()
logger = logging.getLogger(__name__)
session = CachedSession(backend='filesystem', stale_if_error=True,
  ignored_parameters=['aid'])

def get_args():
  parser = argparse.ArgumentParser(
    description='Fetch TV data from zap2it.',
    epilog='This tool is noisy to stdout; '
      'with cron use chronic from moreutils.')
  parser.add_argument(
    '--aid', dest='zap_aid', type=str, default='gapzap',
    help='Raw zap2it input parameter.  (Affiliate ID?)')
  parser.add_argument(
    '-c', '--country', dest='zap_country', type=str, default='USA',
    help='Country identifying the listings to fetch.')
  parser.add_argument(
    '-d', '--delay', dest='delay', type=int, default=5,
    help='Delay, in seconds, between server fetches.')
  parser.add_argument(
    '--device', dest='zap_device', type=str, default='-',
    help='Raw zap2it input parameter.  (?)')
  parser.add_argument(
    '--headend-id', dest='zap_headendId', type=str, default='lineupId',
    help='Raw zap2it input parameter.  (?)')
  parser.add_argument(
    '--is-override', dest='zap_isOverride', type=bool, default=True,
    help='Raw zap2it input parameter.  (?)')
  parser.add_argument(
    '--language', dest='zap_languagecode', type=str, default='en',
    help='Raw zap2it input parameter.  (Language.)')
  parser.add_argument(
    '--pref', dest='zap_pref', type=str, default='',
    help='Raw zap2it input parameter.  (Preferences?)')
  parser.add_argument(
    '--timespan', dest='zap_timespan', type=int, default=3,
    help='Raw zap2it input parameter.  (Hours of data per fetch?)')
  parser.add_argument(
    '--timezone', dest='zap_timezone', type=str, default='',
    help='Raw zap2it input parameter.  (Time zone?)')
  parser.add_argument(
    '--user-id', dest='zap_userId', type=str, default='-',
    help='Raw zap2it input parameter.  (?)')
  parser.add_argument(
    '-z', '--zip', '--postal', dest='zap_postalCode', type=str, required=True,
    help='The zip/postal code identifying the listings to fetch.')
  parser.add_argument(
    '--fetch-days', dest='fetch_days', type=int, default=7,
    help='Days ahead when fetching listings')
  parser.add_argument(
    '--channel-naming', dest='channel_naming', type=str, default='original',
    choices=['original', 'callsign'],
    help='Set the channel naming strategy')
  parser.add_argument(
    '--logging', dest='logging', type=int, default=logging.INFO,
    choices=[logging.WARNING, logging.INFO, logging.DEBUG],
    help='Set the logging level (30 = warning, 20 = info, 10 = debug)')
  parser.add_argument(
    '--cache-expiry', dest='cache_expiry', type=int, default=24,
    help='Cache expiry (hours). Expect new net request to be issued.')
  parser.add_argument(
    '--cache-hold', dest='cache_hold', type=int, default=72,
    help='Cache hold (hours). Expect cache to delete afterwards.')
  return parser.parse_args()


def sub_el(parent, name, text=None, **kwargs):
  el = ET.SubElement(parent, name, **kwargs)
  if text: el.text = text
  return el

def channel_name(channel, strategy):
  if strategy == 'callsign':
    return channel['callSign']
  else:
    return 'I%s.%s.zap2it.com' % (channel['channelNo'], channel['channelId'])

def main():
  args = get_args()
  logging.getLogger().setLevel(args.logging)
  session.settings.expire_after = datetime.timedelta(hours=args.cache_expiry)
  base_qs = {k[4:]: v for (k, v) in vars(args).items() if k.startswith('zap_')}
  done_channels = False
  err = 0
  previous_from_cache = True
  # Start time parameter is now rounded down to nearest `zap_timespan`, in s.
  zap_time = int(time.time())
  zap_time_window = args.zap_timespan * 3600
  zap_time = zap_time - (zap_time % zap_time_window)
  logger.debug('Nearest timespan aligned timestamp %d', zap_time)

  out = ET.Element('tv')
  out.set('source-info-url', 'http://tvlistings.gracenote.com/')
  out.set('source-info-name', 'gracenote.com')
  out.set('generator-info-name', 'zap2xml.py')

  # Fetch data in `zap_timespan` chunks.
  for i in range(int(args.fetch_days * 24 / args.zap_timespan)):
    i_time = zap_time + (i * zap_time_window)

    qs = base_qs.copy()
    qs['lineupId'] = '%s-%s-DEFAULT' % (args.zap_country, args.zap_headendId)
    qs['time'] = i_time

    if not previous_from_cache:
      time.sleep(args.delay)
    logger.info('Fetching %s local', datetime.datetime.fromtimestamp(i_time))
    result = session.get('https://tvlistings.gracenote.com/api/grid', params=qs,
      headers={'Accept': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    previous_from_cache = result.from_cache

    d = {'channels': []}
    if result.ok:
      d = result.json()
    elif result.status_code == 400:
      logging.warning("Got a HTTP 400 error! Ignoring it.")
    else:
      result.raise_for_status()

    if not done_channels and d['channels']:
      done_channels = True
      for c_in in d['channels']:
        c_out = sub_el(out, 'channel',
          id=channel_name(c_in, args.channel_naming))
        sub_el(c_out, 'display-name',
          text='%s %s' % (c_in['channelNo'], c_in['callSign']))
        sub_el(c_out, 'display-name', text=c_in['channelNo'])
        sub_el(c_out, 'display-name', text=c_in['callSign'])
        c_thumb = urllib.parse.urlparse(c_in['thumbnail'], scheme='https')
        c_thumb = c_thumb._replace(query='')
        sub_el(c_out, 'icon', src=c_thumb.geturl())

    for c in d['channels']:
      c_id = channel_name(c, args.channel_naming)
      for event in c['events']:
        prog_in = event['program']
        tm_start = datetime.datetime.fromisoformat(event['startTime'])
        tm_end = datetime.datetime.fromisoformat(event['endTime'])
        prog_out = sub_el(out, 'programme',
          start=tm_start.strftime('%Y%m%d%H%M%S %z'),
          stop=tm_end.strftime('%Y%m%d%H%M%S %z'),
          channel=c_id)

        for (k_in, k_out) in (
            ('title', 'title'),
            ('shortDesc', 'desc'),
            ):
          if prog_in[k_in]:
            sub_el(prog_out, k_out, lang='en', text=prog_in[k_in])

        if event['rating']:
          r = ET.SubElement(prog_out, 'rating')
          sub_el(r, 'value', text=event['rating'])

        if 'filter-movie' in event['filter'] and prog_in['releaseYear']:
          sub_el(
            prog_out, 'sub-title', lang='en',
            text='Movie: ' + prog_in['releaseYear'])
        elif prog_in['episodeTitle']:
          sub_el(
            prog_out, 'sub-title', lang='en', text = prog_in['episodeTitle'])

        sub_el(prog_out, 'length', units='minutes', text=event['duration'])

        if prog_in['season'] and prog_in['episode']:
          s_ = int(prog_in['season'], 10)
          e_ = int(prog_in['episode'], 10)
          sub_el(
            prog_out, 'episode-num', system='common',
            text='S%02dE%02d' % (s_, e_))
          sub_el(
            prog_out, 'episode-num', system='xmltv_ns',
            text='%d.%d.' % (int(s_)-1, int(e_)-1))

        if 'New' in event['flag'] and 'live' not in event['flag']:
          sub_el(prog_out, 'new')

        for f in event['filter']:
          f=f.replace('filter-', '')
          if f == 'family':
            sub_el(prog_out, 'category', lang='en',
              text='Children\'s / Youth programs')
          elif f == 'movie':
            sub_el(prog_out, 'category', lang='en',
              text='Movie / Drama')
          elif f == 'news':
            sub_el(prog_out, 'category', lang='en',
              text='News / Current affairs')
          elif f == 'talk':
            sub_el(prog_out, 'category', lang='en',
              text='Talk show')
          else:
            sub_el(prog_out, 'category', lang='en', text=f.capitalize())

        if event['thumbnail']:
          sub_el(prog_out, 'icon',
            src='https://zap2it.tmsimg.com/assets/%s.jpg' % event['thumbnail'])

  out_path = pathlib.Path(__file__).parent.joinpath('xmltv.xml')
  with open(out_path.absolute(), 'wb') as f:
    f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
    f.write(ET.tostring(out, encoding='UTF-8'))

  session.cache.delete(older_than=datetime.timedelta(hours=args.cache_hold))
  sys.exit(err)


if __name__ == '__main__':
  main()
