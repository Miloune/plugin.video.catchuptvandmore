# -*- coding: utf-8 -*-
# Copyright: (c) JUL1EN094, SPM, SylvainCecchetto
# Copyright: (c) 2016, SylvainCecchetto
# GNU General Public License v2.0+ (see LICENSE.txt or https://www.gnu.org/licenses/gpl-2.0.txt)

# This file is part of Catch-up TV & More

from __future__ import unicode_literals
from builtins import str
import re

from codequick import Listitem, Resolver, Route
import urlquick

from resources.lib import resolver_proxy, web_utils
from resources.lib.menu_utils import item_post_treatment

try:
    from html import unescape
except ImportError:
    from six.moves.html_parser import HTMLParser
    HTML_PARSER = HTMLParser()
    unescape = HTML_PARSER.unescape


# TODO
# Get First-diffusion (date of replay Video)
# Add search button

URL_ROOT = 'https://www.publicsenat.fr'

# The website is now a WordPress site exposing a REST API: replays are 'show'
# posts attached to a 'program' taxonomy term.
URL_API = URL_ROOT + '/wp-json/wp/v2'

URL_DAILYMOTION_LIVE = 'https://api.dailymotion.com/user/publicsenat/videos'

PER_PAGE = 20


@Route.register
def list_programs(plugin, item_id, page='1', **kwargs):
    """
    Build the replay programs listing (the 'program' taxonomy, most active
    first).
    """
    resp = urlquick.get(URL_API + '/program',
                        params={'per_page': PER_PAGE, 'page': page,
                                'orderby': 'count', 'order': 'desc'},
                        max_age=-1)

    for program in resp.json():
        item = Listitem()
        item.label = unescape(program['name'])
        item.set_callback(list_videos,
                          item_id=item_id,
                          program_id=program['id'],
                          page='1')
        item_post_treatment(item)
        yield item

    total_pages = int(resp.headers.get('X-WP-TotalPages', '1'))
    if int(page) < total_pages:
        yield Listitem.next_page(item_id=item_id, page=str(int(page) + 1))


@Route.register
def list_videos(plugin, item_id, program_id, page='1', **kwargs):
    resp = urlquick.get(URL_API + '/show',
                        params={'program': program_id, 'per_page': PER_PAGE,
                                'page': page, 'orderby': 'date',
                                'order': 'desc'},
                        max_age=-1)

    for episode in resp.json():
        item = Listitem()
        item.label = unescape(episode['title']['rendered'])
        item.info['date'] = episode.get('date', '')[:10]
        item.set_callback(get_video_url,
                          item_id=item_id,
                          video_url=episode['link'])
        item_post_treatment(item, is_playable=True, is_downloadable=True)
        yield item

    total_pages = int(resp.headers.get('X-WP-TotalPages', '1'))
    if int(page) < total_pages:
        yield Listitem.next_page(item_id=item_id, program_id=program_id,
                                 page=str(int(page) + 1))


@Resolver.register
def get_video_url(plugin,
                  item_id,
                  video_url,
                  download_mode=False,
                  **kwargs):

    resp = urlquick.get(video_url,
                        headers={'User-Agent': web_utils.get_random_ua()},
                        max_age=-1)
    video_id = re.compile(
        r"""dailymotion\.com/embed/video/([^"'?&]+)""").findall(resp.text)[0]
    return resolver_proxy.get_stream_dailymotion(plugin, video_id,
                                                 download_mode)


@Resolver.register
def get_live_url(plugin, item_id, **kwargs):

    # The website now builds the (new) Dailymotion player client-side, so the
    # live video id is no longer in the page: ask Dailymotion's public API for
    # the current live of the Public Sénat account. The live is
    # domain-restricted, hence the embedder.
    resp = urlquick.get(URL_DAILYMOTION_LIVE,
                        params={'filters': 'live', 'fields': 'id', 'limit': 1},
                        max_age=-1)
    video_id = resp.json()['list'][0]['id']
    return resolver_proxy.get_stream_dailymotion(plugin, video_id, False,
                                                 embeder=URL_ROOT)
